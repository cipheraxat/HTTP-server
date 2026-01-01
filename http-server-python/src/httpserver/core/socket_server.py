"""
=============================================================================
LOW-LEVEL TCP SOCKET SERVER
=============================================================================

This module implements the foundational TCP socket server that handles
the basic socket lifecycle. Think of it as the "ears" of our HTTP server -
it listens for incoming connections and accepts them.

=============================================================================
SOCKET FUNDAMENTALS (Recap from main.py)
=============================================================================

A socket is an ENDPOINT for network communication. The operating system
provides sockets as an abstraction over network hardware.

SOCKET LIFECYCLE (Server Side):
────────────────────────────────

    1. socket()    Create a socket file descriptor
                   └─ Returns an integer (fd) that the OS uses to track it
                   
    2. bind()      Associate the socket with an IP:PORT
                   └─ "Reserve" this address for our server
                   
    3. listen()    Mark socket as a "listening" socket
                   └─ OS starts queueing incoming connections
                   └─ backlog = max queue size before refusing
                   
    4. accept()    Wait for and accept an incoming connection
                   └─ BLOCKS until a client connects
                   └─ Returns a NEW socket just for that client
                   └─ Original socket keeps listening!
                   
    5. close()     Release the socket resources
                   └─ Sends FIN packet to close TCP connection

                    ┌───────────────────────┐
                    │   Listening Socket    │ ◄── Created once at startup
                    │   (Server Socket)     │     Bound to 0.0.0.0:8080
                    └───────────┬───────────┘     Never sends/receives data
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
    ┌───────────┐         ┌───────────┐         ┌───────────┐
    │ Client    │         │ Client    │         │ Client    │
    │ Socket 1  │         │ Socket 2  │         │ Socket 3  │
    └───────────┘         └───────────┘         └───────────┘
    Each accept() creates a new socket for that specific client

=============================================================================
SOCKET OPTIONS EXPLAINED
=============================================================================

SO_REUSEADDR:
─────────────
Allows reusing a local address immediately after the server stops.

Without this, you'd see "Address already in use" for ~60 seconds after
restarting the server. This happens because TCP keeps the socket in
TIME_WAIT state to handle any delayed packets.

    server.stop()
    server.start()  # Error: Address already in use!
    
With SO_REUSEADDR:
    server.stop()
    server.start()  # Works immediately!

SO_REUSEPORT:
─────────────
Allows MULTIPLE sockets to bind to the same address.

This is useful for:
- Load balancing across processes
- Zero-downtime deployments (new process starts before old stops)

    Process 1: bind(0.0.0.0:8080)  ✓
    Process 2: bind(0.0.0.0:8080)  ✓  (Kernel distributes connections)

TCP_NODELAY:
────────────
Disables Nagle's algorithm for lower latency.

Nagle's algorithm buffers small packets to send fewer, larger ones.
This is great for throughput but bad for latency.

    With Nagle (default):
        send("H") → waits
        send("e") → waits
        send("l") → waits
        send("l") → waits
        send("o") → finally sends "Hello"
    
    Without Nagle (TCP_NODELAY):
        send("H") → sends immediately
        send("e") → sends immediately
        ...

For HTTP, we want low latency, so we disable Nagle.

=============================================================================
SIGNAL HANDLING FOR GRACEFUL SHUTDOWN
=============================================================================

When you press Ctrl+C or run `docker stop`, the OS sends a SIGNAL to
your process. We need to catch these signals to shut down gracefully.

SIGINT (2):   Sent when user presses Ctrl+C
SIGTERM (15): Sent by docker stop, systemd stop, kill command

Without signal handling:
    Ctrl+C → Process killed immediately
    └─ Active requests are dropped mid-response
    └─ Database connections left open
    └─ Temporary files not cleaned up

With signal handling:
    Ctrl+C → Signal caught by handler
    └─ Stop accepting new connections
    └─ Wait for active requests to complete
    └─ Clean up resources properly
    └─ Exit cleanly

=============================================================================
"""

import socket
import signal
import logging
import threading
from typing import Optional, Callable, Tuple

from ..config import ServerConfig
from .connection import Connection


logger = logging.getLogger(__name__)


class SocketServer:
    """
    Low-level TCP socket server.
    
    Manages socket lifecycle and connection acceptance.
    Designed to be used by higher-level HTTP server.
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      SocketServer Internals                          │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │    __init__()        Store config, initialize state                  │
    │        │                                                             │
    │        ▼                                                             │
    │    start()           Main entry point                                │
    │        │                                                             │
    │        ├──► _create_socket()   Create & configure socket             │
    │        │        │                                                    │
    │        │        └──► socket()   Create TCP socket                    │
    │        │        └──► setsockopt()  Set SO_REUSEADDR, TCP_NODELAY    │
    │        │                                                             │
    │        ├──► bind()            Bind to IP:PORT                        │
    │        ├──► listen()          Start accepting queue                  │
    │        ├──► _setup_signals()  Install SIGTERM/SIGINT handlers       │
    │        │                                                             │
    │        └──► _accept_loop()    Main loop (blocks here!)              │
    │                 │                                                    │
    │                 └──► while running:                                  │
    │                         accept()  Wait for connection                │
    │                         Connection()  Wrap client socket             │
    │                         callback(conn)  Hand off to HTTP server      │
    │                                                                      │
    │    shutdown()        Stop the server                                 │
    │        │                                                             │
    │        └──► _running = False                                         │
    │        └──► _shutdown_event.set()                                    │
    │                                                                      │
    │    _cleanup()        Clean up resources                              │
    │        └──► Restore signal handlers                                  │
    │        └──► Close socket                                             │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘
    
    Features:
    - Configurable socket options
    - Signal handling (SIGTERM, SIGINT)
    - Graceful shutdown support
    - Non-blocking accept with select
    
    Usage:
        def handle_connection(conn: Connection):
            # Handle the connection
            pass
        
        server = SocketServer(config)
        server.start(handle_connection)  # Blocks until shutdown
    """
    
    def __init__(self, config: ServerConfig):
        """
        Initialize the socket server.
        
        Args:
            config: Server configuration containing host, port, backlog, etc.
        
        Note: This does NOT start the server or create the socket.
              The socket is created lazily in start().
        """
        self.config = config
        
        # The actual socket object (created in start())
        self._socket: Optional[socket.socket] = None
        
        # Server state
        self._running = False
        
        # Threading event for coordinating shutdown
        # Other threads can wait on this to know when server stops
        self._shutdown_event = threading.Event()
        
        # Save original signal handlers so we can restore them
        # This is important if someone embeds our server in a larger app
        self._original_handlers: dict = {}
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    @property
    def address(self) -> Tuple[str, int]:
        """Get the server's bound address (IP, port)."""
        return (self.config.host, self.config.port)
    
    def _create_socket(self) -> socket.socket:
        """
        Create and configure the server socket.
        
        This is where we set up all the socket options that affect
        how our server behaves at the TCP level.
        
        Returns:
            Configured socket ready for binding.
        """
        # ─────────────────────────────────────────────────────────────────
        # CREATE TCP SOCKET
        # ─────────────────────────────────────────────────────────────────
        # socket.socket(address_family, socket_type, protocol=0)
        #
        # AF_INET = IPv4 addresses (e.g., 192.168.1.1)
        # SOCK_STREAM = TCP (reliable, ordered, connection-based)
        #
        # This returns a file descriptor (integer) that the OS uses
        # to track this socket. All future operations use this fd.
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # ─────────────────────────────────────────────────────────────────
        # SOCKET OPTIONS
        # ─────────────────────────────────────────────────────────────────
        # setsockopt(level, option, value)
        #
        # level = what protocol level to set the option at
        #   SOL_SOCKET = General socket options
        #   IPPROTO_TCP = TCP-specific options
        #
        # SO_REUSEADDR: Allow reuse of local addresses
        # Why: Avoids "Address already in use" when restarting server
        # The socket enters TIME_WAIT for ~60s after close() to handle
        # delayed packets. SO_REUSEADDR lets us bind anyway.
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # SO_REUSEPORT: Allow multiple sockets to bind to same port
        # Why: Enables load balancing across processes
        # Not available on all platforms (Windows doesn't have it)
        
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass  # Not available on Windows
        
        # TCP_NODELAY: Disable Nagle's algorithm
        # Why: Lower latency for HTTP (we want responses sent immediately)
        # Nagle buffers small packets to reduce network overhead, but
        # this adds latency. For interactive protocols like HTTP, we
        # prefer lower latency over slightly better throughput.
        
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        # ─────────────────────────────────────────────────────────────────
        # SOCKET TIMEOUT
        # ─────────────────────────────────────────────────────────────────
        # Set timeout on accept() so we can periodically check if
        # we should shut down. Without this, accept() blocks forever.
        #
        # This creates a pattern:
        #   while running:
        #       try:
        #           accept()  # Blocks for 1 second max
        #       except timeout:
        #           continue  # Check running flag, loop again
        
        sock.settimeout(1.0)
        
        return sock
    
    def _setup_signals(self):
        """
        Setup signal handlers for graceful shutdown.
        
        Unix signals are how the OS communicates with processes.
        We catch these to shut down gracefully instead of being killed.
        
        SIGTERM (15):
            - Sent by: docker stop, systemd stop, kill <pid>
            - Default behavior: Terminate process
            - Our behavior: Graceful shutdown
        
        SIGINT (2):
            - Sent by: Ctrl+C in terminal
            - Default behavior: Terminate process  
            - Our behavior: Graceful shutdown
        
        Note: SIGKILL (9) cannot be caught - instant death!
              That's why docker stop waits 10s before SIGKILL.
        """
        def shutdown_handler(signum, frame):
            """
            Called when we receive SIGTERM or SIGINT.
            
            Args:
                signum: The signal number (e.g., 15 for SIGTERM)
                frame: The current stack frame (we don't use it)
            """
            # Convert signal number to name for logging
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating shutdown...")
            self.shutdown()
        
        # Save original handlers so we can restore them later
        # This is important if our server is embedded in another app
        self._original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, shutdown_handler)
        self._original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, shutdown_handler)
    
    def _restore_signals(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        self._original_handlers.clear()
    
    def start(self, connection_handler: Callable[[Connection], None]):
        """
        Start accepting connections.
        
        This method BLOCKS until shutdown() is called.
        
        Args:
            connection_handler: Callback function that receives each new
                               connection. This is where the HTTP server
                               will do request parsing and routing.
        
        The flow:
        
            HTTPServer.run()
                └──► SocketServer.start(self._handle_connection)
                         │
                         ├──► Create socket
                         ├──► Bind to address
                         ├──► Listen for connections
                         │
                         └──► Accept loop (BLOCKS HERE)
                                  │
                                  └──► For each connection:
                                          connection_handler(conn)
        """
        # Create and bind socket
        self._socket = self._create_socket()
        
        try:
            # ─────────────────────────────────────────────────────────────
            # BIND: Associate socket with address
            # ─────────────────────────────────────────────────────────────
            # bind() tells the OS: "When packets arrive for this IP:PORT,
            # deliver them to this socket."
            #
            # Common errors:
            # - Address already in use: Another process has this port
            # - Permission denied: Ports < 1024 require root (use 8080!)
            
            self._socket.bind((self.config.host, self.config.port))
        except OSError as e:
            logger.error(f"Failed to bind to {self.config.host}:{self.config.port}: {e}")
            raise
        
        # ─────────────────────────────────────────────────────────────────
        # LISTEN: Start accepting connections
        # ─────────────────────────────────────────────────────────────────
        # listen(backlog) tells the OS to start queueing connections.
        #
        # backlog = how many connections to queue before refusing new ones
        # If the queue is full, new connections get "Connection refused"
        #
        # A good backlog value is 128-1024 depending on expected load.
        # Too low = connections refused under load
        # Too high = wasted memory (each queued connection uses some)
        
        self._socket.listen(self.config.backlog)
        
        self._running = True
        self._shutdown_event.clear()
        
        # Setup signal handlers
        self._setup_signals()
        
        logger.info(f"Server listening on {self.config.host}:{self.config.port}")
        
        try:
            self._accept_loop(connection_handler)
        finally:
            self._cleanup()
    
    def _accept_loop(self, connection_handler: Callable[[Connection], None]):
        """
        Main loop for accepting connections.
        
        This is where the server spends most of its time, waiting for
        new connections to arrive.
        
        ┌─────────────────────────────────────────────────────────────────┐
        │                     Accept Loop Flow                             │
        ├─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │   while self._running:                                           │
        │       │                                                          │
        │       ├──► accept()                                              │
        │       │       │                                                  │
        │       │       ├── BLOCKS until connection arrives                │
        │       │       │   (or timeout after 1 second)                   │
        │       │       │                                                  │
        │       │       └── Returns (client_socket, client_address)        │
        │       │                                                          │
        │       ├──► Create Connection wrapper                             │
        │       │       └── Adds buffering, timeout, state tracking       │
        │       │                                                          │
        │       └──► connection_handler(conn)                              │
        │               └── HTTPServer submits to thread pool              │
        │                                                                  │
        │   (Loop continues until self._running becomes False)             │
        │                                                                  │
        └─────────────────────────────────────────────────────────────────┘
        
        Args:
            connection_handler: Callback for each new connection.
        """
        while self._running:
            try:
                # ─────────────────────────────────────────────────────────
                # ACCEPT: Wait for a connection
                # ─────────────────────────────────────────────────────────
                # accept() blocks until a client connects.
                # Returns a NEW socket just for this client, plus their address.
                #
                # The original socket keeps listening - accept() doesn't
                # consume it. This is how one server handles many clients.
                #
                # client_address is a tuple: (ip_address, port)
                # Example: ("192.168.1.50", 54321)
                
                client_socket, client_address = self._socket.accept()
                
                logger.debug(f"Accepted connection from {client_address[0]}:{client_address[1]}")
                
                # ─────────────────────────────────────────────────────────
                # WRAP IN CONNECTION OBJECT
                # ─────────────────────────────────────────────────────────
                # The raw socket is awkward to work with:
                # - No buffering (you might read half a request)
                # - No timeout management
                # - No state tracking
                #
                # Connection wraps it with a nicer API for HTTP handling.
                
                conn = Connection(
                    socket=client_socket,
                    address=client_address,
                    buffer_size=self.config.buffer_size,
                    timeout=self.config.timeout,
                    keep_alive_timeout=self.config.keep_alive_timeout,
                    max_request_size=self.config.max_request_size,
                )
                
                # Hand off to HTTP server (which adds to thread pool)
                connection_handler(conn)
                
            except socket.timeout:
                # ─────────────────────────────────────────────────────────
                # TIMEOUT IS NORMAL!
                # ─────────────────────────────────────────────────────────
                # We set a 1-second timeout so we can check self._running
                # periodically. Without this, accept() would block forever
                # and we couldn't shut down cleanly.
                #
                # This is the "polling" pattern for interruptible blocking.
                continue
            
            except OSError as e:
                # Socket error - usually means we're shutting down
                if self._running:
                    logger.error(f"Accept error: {e}")
                break
    
    def shutdown(self):
        """
        Initiate graceful shutdown.
        
        This method can be called from:
        - Signal handler (Ctrl+C or SIGTERM)
        - Another thread
        - The main thread after some condition
        
        It's safe to call multiple times - it's idempotent.
        """
        logger.info("Shutting down socket server...")
        self._running = False
        self._shutdown_event.set()  # Wake up anyone waiting
    
    def _cleanup(self):
        """Clean up resources on shutdown."""
        # Restore original signal handlers
        self._restore_signals()
        
        # Close the listening socket
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass  # Already closed
            self._socket = None
        
        logger.info("Socket server stopped")
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the server to shut down.
        
        Useful for tests or when you need to coordinate with shutdown
        from another thread.
        
        Args:
            timeout: Maximum time to wait in seconds. None = wait forever.
        
        Returns:
            True if shutdown completed, False if timeout.
        """
        return self._shutdown_event.wait(timeout)
