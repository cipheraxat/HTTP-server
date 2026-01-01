"""
=============================================================================
CONNECTION MANAGEMENT
=============================================================================

This module handles individual client connections, wrapping the raw socket
with a higher-level API suitable for HTTP request/response handling.

=============================================================================
TCP IS A BYTE STREAM, NOT A MESSAGE PROTOCOL!
=============================================================================

This is one of the MOST IMPORTANT concepts in network programming:

    TCP does NOT preserve message boundaries.

When you send data over TCP, it might arrive in different chunks than
you sent it. TCP only guarantees that bytes arrive IN ORDER and INTACT.

EXAMPLE:
─────────

    Client sends:
        send("Hello")
        send("World")
    
    Server might receive ANY of these:
        recv() → "HelloWorld"      (both combined)
        recv() → "Hel"             (partial)
        recv() → "loWorld"         (rest of first + second)
        recv() → "Hello"           (first message)
        recv() → "World"           (second message, separately)

This happens because:
1. TCP buffers data before sending (Nagle's algorithm)
2. Network splits data into packets
3. Packets take different routes, arrive at different times
4. OS kernel buffers received data

FOR HTTP, THIS MEANS:
─────────────────────

    Client sends HTTP request:
        GET /api/users HTTP/1.1\r\n
        Host: localhost\r\n
        \r\n

    Server might receive:
        First recv():  "GET /api/use"    (incomplete!)
        Second recv(): "rs HTTP/1.1\r\n" (rest)
        Third recv():  "Host: ..."       (headers)

We MUST buffer received data and look for protocol delimiters
(like \r\n\r\n for HTTP headers) to know when we have a complete message.

=============================================================================
HTTP MESSAGE STRUCTURE
=============================================================================

An HTTP request looks like this:

    ┌─────────────────────────────────────────────────────────────────┐
    │  REQUEST LINE                                                    │
    │  ─────────────────────────────────────────────────────────────  │
    │  GET /api/users?page=1 HTTP/1.1\r\n                             │
    │  └─────┘ └────────────────────┘ └──────────┘                    │
    │  Method        Path + Query       Version                        │
    ├─────────────────────────────────────────────────────────────────┤
    │  HEADERS                                                         │
    │  ─────────────────────────────────────────────────────────────  │
    │  Host: localhost:8080\r\n                                       │
    │  User-Agent: curl/7.64.1\r\n                                    │
    │  Accept: application/json\r\n                                   │
    │  Content-Length: 42\r\n         ← Tells us body length!        │
    │  \r\n                           ← Empty line = end of headers   │
    ├─────────────────────────────────────────────────────────────────┤
    │  BODY (optional)                                                 │
    │  ─────────────────────────────────────────────────────────────  │
    │  {"name": "Alice", "email": "alice@example.com"}                │
    │  └──────────────────────────────────────────────┘               │
    │              Exactly Content-Length bytes                        │
    └─────────────────────────────────────────────────────────────────┘

Reading a complete request:
1. Read until we see \r\n\r\n (end of headers)
2. Parse Content-Length from headers
3. Read exactly Content-Length more bytes (the body)

=============================================================================
KEEP-ALIVE CONNECTIONS
=============================================================================

HTTP/1.1 defaults to persistent connections. One TCP connection can
serve MULTIPLE requests:

    ┌─────────────────────────────────────────────────────────────────┐
    │                    Without Keep-Alive (HTTP/1.0)                 │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │   Request 1:   TCP Connect → Send → Receive → TCP Close        │
    │   Request 2:   TCP Connect → Send → Receive → TCP Close        │
    │   Request 3:   TCP Connect → Send → Receive → TCP Close        │
    │                                                                  │
    │   Each request pays the cost of TCP 3-way handshake (~1.5 RTT) │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                    With Keep-Alive (HTTP/1.1)                    │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │   TCP Connect                                                    │
    │       │                                                          │
    │       ├── Request 1: Send → Receive                              │
    │       ├── Request 2: Send → Receive                              │
    │       ├── Request 3: Send → Receive                              │
    │       │                                                          │
    │   TCP Close (or timeout)                                         │
    │                                                                  │
    │   Only one handshake for multiple requests!                      │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘

The Connection class supports keep-alive by:
1. Tracking how many requests have been handled
2. Using shorter timeouts for subsequent requests
3. Keeping any buffered data between requests

=============================================================================
CONNECTION STATE MACHINE
=============================================================================

    NEW ──────► READING ──────► PROCESSING ──────► WRITING ────────┐
     │             │                                    │           │
     │             │                                    │           ▼
     │             │                                    │      KEEP_ALIVE
     │             │                                    │           │
     │             │                                    │           │
     │             ▼                                    │           │
     └──────────► CLOSING ◄─────────────────────────────┴───────────┘
                    │
                    ▼
                  CLOSED

=============================================================================
"""

import socket
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import uuid


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """
    Connection lifecycle states.
    
    These states help us track what's happening with each connection
    for logging, debugging, and proper resource management.
    """
    NEW = "new"              # Just accepted, haven't read anything yet
    READING = "reading"      # Currently reading request data
    PROCESSING = "processing"  # Request parsed, handler is executing
    WRITING = "writing"      # Sending response data
    KEEP_ALIVE = "keep_alive"  # Response sent, waiting for next request
    CLOSING = "closing"      # About to close (shutdown sequence)
    CLOSED = "closed"        # Connection closed, socket released


@dataclass
class Connection:
    """
    Represents a client connection.
    
    This class wraps a raw socket with higher-level functionality:
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    Connection Responsibilities                       │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  1. BUFFERED READING                                                 │
    │     └── TCP delivers bytes in arbitrary chunks                       │
    │     └── We buffer until we have a complete HTTP request              │
    │     └── _buffer holds partial data between recv() calls              │
    │                                                                      │
    │  2. TIMEOUT MANAGEMENT                                               │
    │     └── Different timeouts for different situations                  │
    │     └── First request: 30 seconds (client might be slow)            │
    │     └── Keep-alive: 5 seconds (should be quick if they want more)   │
    │                                                                      │
    │  3. STATE TRACKING                                                   │
    │     └── Know what phase of request handling we're in                 │
    │     └── Helps with debugging and logging                             │
    │     └── Used for metrics (how long in each state)                    │
    │                                                                      │
    │  4. REQUEST COUNTING                                                 │
    │     └── How many requests on this connection?                        │
    │     └── Used for keep-alive limits and metrics                       │
    │                                                                      │
    │  5. GRACEFUL CLOSE                                                   │
    │     └── Proper TCP shutdown sequence                                 │
    │     └── Drain any remaining data                                     │
    │     └── Don't leak file descriptors                                  │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘
    
    Attributes:
        socket: The client socket.
        address: Client's (ip, port) tuple.
        id: Unique connection identifier (for logging).
        state: Current connection state.
        created_at: Timestamp when connection was accepted.
        last_activity: Timestamp of last activity.
        requests_handled: Number of requests on this connection.
    """
    
    # Required parameters
    socket: socket.socket
    address: tuple[str, int]
    
    # Generated/default parameters
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    state: ConnectionState = ConnectionState.NEW
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    requests_handled: int = 0
    
    # Configuration (passed from ServerConfig)
    buffer_size: int = 8192           # How much to read at once
    timeout: float = 30.0             # Timeout for first request
    keep_alive_timeout: float = 5.0   # Timeout for subsequent requests
    max_request_size: int = 10 * 1024 * 1024  # 10 MB max request
    
    # Internal state (not shown in repr for cleaner logs)
    _buffer: bytes = field(default=b"", repr=False)
    
    def __post_init__(self):
        """
        Configure socket after initialization.
        
        Called automatically by dataclass after __init__.
        """
        # Set socket to blocking mode (we manage timeouts ourselves)
        self.socket.setblocking(True)
        
        # Set initial timeout
        if self.timeout:
            self.socket.settimeout(self.timeout)
    
    # =========================================================================
    # PROPERTIES: Convenient accessors
    # =========================================================================
    
    @property
    def client_ip(self) -> str:
        """Get the client IP address."""
        return self.address[0]
    
    @property
    def client_port(self) -> int:
        """Get the client port."""
        return self.address[1]
    
    @property
    def age(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """Get time since last activity in seconds."""
        return time.time() - self.last_activity
    
    # =========================================================================
    # READING: Get complete HTTP requests from the socket
    # =========================================================================
    
    def read_request(self) -> Optional[bytes]:
        """
        Read a complete HTTP request from the socket.
        
        This is the CORE method for reading HTTP requests. It handles:
        
        1. BUFFERING: Accumulates data until we have complete headers
        2. HEADER DETECTION: Looks for \r\n\r\n marker
        3. BODY READING: Uses Content-Length to read exact body size
        4. KEEP-ALIVE: Shorter timeout for subsequent requests
        
        ┌─────────────────────────────────────────────────────────────────┐
        │                    read_request() Flow                           │
        ├─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │   ┌─────────────────────┐                                       │
        │   │ Is this keep-alive? │                                       │
        │   └──────────┬──────────┘                                       │
        │              │                                                   │
        │   ┌──────────▼──────────┐                                       │
        │   │ Set timeout         │   (5s for keep-alive, 30s otherwise) │
        │   └──────────┬──────────┘                                       │
        │              │                                                   │
        │   ┌──────────▼──────────┐                                       │
        │   │ while no \r\n\r\n:  │   ← Wait for complete headers         │
        │   │   recv() → buffer   │                                       │
        │   └──────────┬──────────┘                                       │
        │              │                                                   │
        │   ┌──────────▼──────────┐                                       │
        │   │ Parse Content-Length│   ← How big is the body?              │
        │   └──────────┬──────────┘                                       │
        │              │                                                   │
        │   ┌──────────▼──────────┐                                       │
        │   │ while body incomplete│  ← Read remaining body               │
        │   │   recv() → buffer   │                                       │
        │   └──────────┬──────────┘                                       │
        │              │                                                   │
        │   ┌──────────▼──────────┐                                       │
        │   │ Extract request     │   ← Pull from buffer, keep extras     │
        │   │ Return bytes        │                                       │
        │   └─────────────────────┘                                       │
        │                                                                  │
        └─────────────────────────────────────────────────────────────────┘
        
        Returns:
            Complete HTTP request bytes, or None if connection closed.
        
        Raises:
            TimeoutError: If read times out.
            ConnectionError: If connection is lost.
            ValueError: If request exceeds max size.
        """
        self.state = ConnectionState.READING
        self.last_activity = time.time()
        
        # ─────────────────────────────────────────────────────────────────
        # ADJUST TIMEOUT FOR KEEP-ALIVE
        # ─────────────────────────────────────────────────────────────────
        # If this is a subsequent request (keep-alive), use shorter timeout.
        # The client already knows we're here, so they should be quick.
        # If they're not sending another request, we close the connection.
        
        if self.requests_handled > 0:
            self.socket.settimeout(self.keep_alive_timeout)
        
        try:
            # ─────────────────────────────────────────────────────────────
            # STEP 1: Read until we have complete headers
            # ─────────────────────────────────────────────────────────────
            # HTTP headers end with \r\n\r\n (empty line)
            # We keep reading until we see this delimiter
            
            while b"\r\n\r\n" not in self._buffer:
                chunk = self._recv()
                if not chunk:
                    return None  # Connection closed by client
                
                self._buffer += chunk
                
                # Safety check: don't let buffer grow forever
                if len(self._buffer) > self.max_request_size:
                    raise ValueError(f"Request too large: {len(self._buffer)} bytes")
            
            # ─────────────────────────────────────────────────────────────
            # STEP 2: Find the header/body boundary
            # ─────────────────────────────────────────────────────────────
            # Headers and body are separated by \r\n\r\n
            #
            #   GET / HTTP/1.1\r\n
            #   Content-Length: 5\r\n
            #   \r\n                ← header_end points here
            #   Hello               ← body_start is 4 bytes later
            
            header_end = self._buffer.find(b"\r\n\r\n")
            header_section = self._buffer[:header_end]
            body_start = header_end + 4  # Skip the \r\n\r\n
            
            # ─────────────────────────────────────────────────────────────
            # STEP 3: Parse Content-Length
            # ─────────────────────────────────────────────────────────────
            # GET requests usually have no body (Content-Length: 0)
            # POST/PUT requests have body, need to read exact amount
            
            content_length = self._parse_content_length(header_section)
            
            # ─────────────────────────────────────────────────────────────
            # STEP 4: Read remaining body if needed
            # ─────────────────────────────────────────────────────────────
            # We might already have some body in the buffer
            # Read more until we have exactly content_length bytes
            
            while len(self._buffer) - body_start < content_length:
                chunk = self._recv()
                if not chunk:
                    break  # Connection closed mid-request
                
                self._buffer += chunk
                
                if len(self._buffer) > self.max_request_size:
                    raise ValueError(f"Request too large: {len(self._buffer)} bytes")
            
            # ─────────────────────────────────────────────────────────────
            # STEP 5: Extract complete request, keep leftovers
            # ─────────────────────────────────────────────────────────────
            # In HTTP pipelining, client might send multiple requests.
            # We extract one and leave the rest in buffer for next call.
            
            request_end = body_start + content_length
            request_data = self._buffer[:request_end]
            
            # Keep any extra data (pipelining support)
            self._buffer = self._buffer[request_end:]
            
            self.requests_handled += 1
            self.last_activity = time.time()
            
            return request_data
            
        except socket.timeout:
            # ─────────────────────────────────────────────────────────────
            # TIMEOUT HANDLING
            # ─────────────────────────────────────────────────────────────
            # For keep-alive connections, timeout is normal - client
            # just doesn't have more requests. Return None to close.
            #
            # For first request, timeout is an error - client connected
            # but never sent anything.
            
            if self.requests_handled > 0:
                # Keep-alive timeout is normal
                logger.debug(f"[{self.id}] Keep-alive timeout")
                return None
            raise TimeoutError("Request read timeout")
        
        finally:
            # Restore normal timeout
            self.socket.settimeout(self.timeout)
    
    def _recv(self) -> bytes:
        """
        Receive data from socket with error handling.
        
        Wraps socket.recv() to handle common errors gracefully.
        
        Returns:
            Received bytes, or empty bytes if connection closed.
        """
        try:
            data = self.socket.recv(self.buffer_size)
            self.last_activity = time.time()
            return data
        except (ConnectionResetError, BrokenPipeError):
            # Client disconnected abruptly
            return b""
    
    def _parse_content_length(self, headers: bytes) -> int:
        """
        Parse Content-Length header from raw headers.
        
        We do a simple string search rather than fully parsing headers
        because we need this BEFORE we can parse the request.
        
        Args:
            headers: Raw header bytes.
        
        Returns:
            Content-Length value, or 0 if not present.
        """
        try:
            # Decode and lowercase for case-insensitive search
            header_str = headers.decode("utf-8", errors="replace").lower()
            for line in header_str.split("\r\n"):
                if line.startswith("content-length:"):
                    # Extract the number after the colon
                    return int(line.split(":", 1)[1].strip())
        except (ValueError, IndexError):
            pass
        return 0
    
    # =========================================================================
    # WRITING: Send response data to the client
    # =========================================================================
    
    def send_response(self, data: bytes) -> bool:
        """
        Send response data to the client.
        
        Uses sendall() to ensure ALL data is sent. Regular send() might
        only send part of the data if the buffer is full.
        
        Args:
            data: Response bytes to send.
        
        Returns:
            True if send succeeded, False if connection lost.
        """
        self.state = ConnectionState.WRITING
        self.last_activity = time.time()
        
        try:
            # sendall() blocks until ALL data is sent or error
            # This is important because send() might only send part
            self.socket.sendall(data)
            self.last_activity = time.time()
            return True
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            # Client disconnected
            logger.warning(f"[{self.id}] Send failed: {e}")
            return False
    
    # =========================================================================
    # CLOSING: Properly terminate the connection
    # =========================================================================
    
    def close(self):
        """
        Close the connection gracefully.
        
        Performs proper TCP shutdown sequence:
        
        1. shutdown(SHUT_WR): Tell client we're done sending
           └── Sends FIN packet to client
           
        2. Drain remaining data: Read any data client sent
           └── Important to not leave data in kernel buffers
           
        3. close(): Release socket file descriptor
           └── OS reclaims resources
        
        ┌─────────────────────────────────────────────────────────────────┐
        │                    TCP Close Sequence                            │
        ├─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │   Server                              Client                     │
        │      │                                   │                       │
        │      │   FIN ──────────────────────────► │  (shutdown SHUT_WR)  │
        │      │                                   │                       │
        │      │ ◄───────────────────────── ACK   │                       │
        │      │                                   │                       │
        │      │ ◄───────────────────────── FIN   │  (client closes)      │
        │      │                                   │                       │
        │      │   ACK ──────────────────────────► │                       │
        │      │                                   │                       │
        │   (socket closed)                  (socket closed)               │
        │                                                                  │
        └─────────────────────────────────────────────────────────────────┘
        """
        if self.state == ConnectionState.CLOSED:
            return  # Already closed
        
        self.state = ConnectionState.CLOSING
        
        try:
            # ─────────────────────────────────────────────────────────────
            # STEP 1: Stop sending (sends FIN)
            # ─────────────────────────────────────────────────────────────
            # shutdown(SHUT_WR) tells the OS we're done sending.
            # This sends a FIN packet to the client, starting the close.
            
            self.socket.shutdown(socket.SHUT_WR)
        except OSError:
            pass  # Already disconnected, that's fine
        
        try:
            # ─────────────────────────────────────────────────────────────
            # STEP 2: Drain any remaining data
            # ─────────────────────────────────────────────────────────────
            # The client might have sent data we haven't read.
            # We need to drain it or it'll sit in kernel buffers.
            
            self.socket.settimeout(0.5)  # Quick timeout
            while self.socket.recv(1024):
                pass  # Discard any remaining data
        except (socket.timeout, OSError):
            pass  # That's fine, we're closing anyway
        
        try:
            # ─────────────────────────────────────────────────────────────
            # STEP 3: Close the socket
            # ─────────────────────────────────────────────────────────────
            # Release the file descriptor back to the OS.
            
            self.socket.close()
        except OSError:
            pass
        
        self.state = ConnectionState.CLOSED
        logger.debug(f"[{self.id}] Connection closed after {self.requests_handled} requests")
    
    def set_keep_alive(self):
        """Mark connection for keep-alive (ready for next request)."""
        self.state = ConnectionState.KEEP_ALIVE
    
    # =========================================================================
    # CONTEXT MANAGER: For use with 'with' statement
    # =========================================================================
    
    def __enter__(self):
        """
        Context manager entry.
        
        Allows using Connection with 'with' statement for automatic cleanup:
        
            with conn:
                data = conn.read_request()
                conn.send_response(response)
            # Connection automatically closed here
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure connection is closed."""
        self.close()
        return False  # Don't suppress exceptions
