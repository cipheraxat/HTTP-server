"""
=============================================================================
MAIN HTTP SERVER
=============================================================================

This is the main orchestrator that ties all components together into
a complete, production-ready HTTP server.

=============================================================================
ARCHITECTURE OVERVIEW
=============================================================================

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    HTTP SERVER ARCHITECTURE                         │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │                        ┌─────────────────┐                          │
    │                        │   HTTPServer    │                          │
    │                        │   (Orchestrator)│                          │
    │                        └────────┬────────┘                          │
    │                                 │                                    │
    │            ┌────────────────────┼────────────────────┐              │
    │            │                    │                    │              │
    │            ▼                    ▼                    ▼              │
    │    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        │
    │    │SocketServer  │    │  ThreadPool  │    │    Router    │        │
    │    │ (Networking) │    │ (Concurrency)│    │ (Dispatching)│        │
    │    └──────┬───────┘    └──────┬───────┘    └──────────────┘        │
    │           │                   │                                     │
    │           ▼                   ▼                                     │
    │    ┌──────────────┐    ┌──────────────┐                            │
    │    │  Connection  │    │   Handlers   │                            │
    │    │ (TCP Conn.)  │    │ (Business)   │                            │
    │    └──────────────┘    └──────────────┘                            │
    │                                                                      │
    │           ┌─────────────────────────────────────────┐               │
    │           │         Middleware Pipeline             │               │
    │           │   Logging → CORS → Auth → Handler       │               │
    │           └─────────────────────────────────────────┘               │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
REQUEST LIFECYCLE
=============================================================================

    1. CLIENT CONNECTS
       └── SocketServer accepts TCP connection
       
    2. QUEUE FOR PROCESSING
       └── Connection queued in ThreadPool
       
    3. PARSE REQUEST (Worker Thread)
       └── RequestParser extracts method, path, headers, body
       
    4. MIDDLEWARE PIPELINE
       └── Logging → CORS → Rate Limit → ... → Handler
       
    5. ROUTE DISPATCH
       └── Router matches path → calls handler function
       
    6. RESPONSE GENERATION
       └── Handler returns HTTPResponse
       
    7. MIDDLEWARE (Reverse Order)
       └── ... → Compression → Logging
       
    8. SEND RESPONSE
       └── Connection sends bytes to client
       
    9. KEEP-ALIVE OR CLOSE
       └── Loop for more requests, or close connection

=============================================================================
INTERVIEW QUESTIONS ABOUT WEB SERVERS
=============================================================================

Q: "Explain how a request flows through your server."
A: "1. Accept TCP connection on listening socket
   2. Queue connection in thread pool
   3. Worker thread reads HTTP bytes from socket
   4. Parse bytes into HTTPRequest object
   5. Run through middleware pipeline (logging, auth, etc.)
   6. Router matches URL to handler function
   7. Handler generates HTTPResponse
   8. Middleware post-processing (compression, etc.)
   9. Serialize response to bytes
   10. Send bytes on socket, close or keep-alive"

Q: "How do you handle concurrent connections?"
A: "Thread pool with configurable min/max workers.
   Each connection is processed by a worker thread.
   Thread pool has a queue for pending connections.
   If queue is full, we return 503 Service Unavailable."

Q: "What happens during graceful shutdown?"
A: "1. Stop accepting new connections
   2. Wait for in-flight requests to complete
   3. Set timeout on waiting (don't wait forever)
   4. Close all connections
   5. Shutdown thread pool"

=============================================================================
"""

import logging
import time
from typing import Optional, Callable

from .config import ServerConfig
from .core import SocketServer, Connection, ThreadPool
from .http import (
    HTTPRequest, RequestParser, HTTPParseError,
    HTTPResponse, ResponseBuilder, HTTPStatus,
    Router,
)
from .middleware import MiddlewarePipeline, Middleware


logger = logging.getLogger(__name__)


class HTTPServer:
    """
    Production-grade HTTP/1.1 server.
    
    =========================================================================
    FEATURES
    =========================================================================
    
    - Multi-threaded request handling (thread pool)
    - Middleware pipeline for cross-cutting concerns
    - URL routing with path parameters
    - Keep-alive connection support
    - Graceful shutdown
    - Configurable via ServerConfig
    
    =========================================================================
    USAGE
    =========================================================================
    
        # Create server
        server = HTTPServer()
        
        # Define routes with decorators
        @server.get("/")
        def index(request):
            return ok({"message": "Hello World"})
        
        @server.get("/users/:id")
        def get_user(request):
            user_id = request.path_params["id"]
            return ok({"id": user_id})
        
        @server.post("/users")
        def create_user(request):
            data = request.json
            return created({"id": 1, **data})
        
        # Add middleware
        server.use(LoggingMiddleware())
        server.use(CORSMiddleware())
        server.use(CompressionMiddleware())
        
        # Run server (blocking)
        server.run()
    
    =========================================================================
    ARCHITECTURE
    =========================================================================
    
    The server is composed of modular components:
    
    - ServerConfig: Configuration management
    - SocketServer: Low-level TCP socket handling
    - ThreadPool: Worker thread management
    - RequestParser: HTTP request parsing
    - Router: URL routing and dispatching
    - MiddlewarePipeline: Request/response processing
    
    =========================================================================
    """
    
    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize the HTTP server.
        
        Args:
            config: Server configuration. Uses sensible defaults if not provided.
        """
        self.config = config or ServerConfig()
        self.config.validate()  # Fail-fast on invalid config
        
        # ─────────────────────────────────────────────────────────────────
        # CORE COMPONENTS
        # ─────────────────────────────────────────────────────────────────
        
        # Socket server handles low-level TCP connections
        self._socket_server = SocketServer(self.config)
        
        # Thread pool provides worker threads for concurrent request handling
        self._thread_pool = ThreadPool(
            min_workers=self.config.min_workers,
            max_workers=self.config.max_workers,
        )
        
        # Request parser converts raw bytes to HTTPRequest objects
        self._parser = RequestParser(max_request_size=self.config.max_request_size)
        
        # ─────────────────────────────────────────────────────────────────
        # APPLICATION COMPONENTS
        # ─────────────────────────────────────────────────────────────────
        
        # Router maps URLs to handler functions
        self._router = Router()
        
        # Middleware pipeline for cross-cutting concerns
        self._middleware = MiddlewarePipeline()
        
        # ─────────────────────────────────────────────────────────────────
        # RUNTIME STATE
        # ─────────────────────────────────────────────────────────────────
        
        # Handler chain (built on first request)
        # This is middleware.wrap(router.handle)
        self._handler: Optional[Callable[[HTTPRequest], HTTPResponse]] = None
        
        # Server running state
        self._running = False
    
    # =========================================================================
    # CONFIGURATION METHODS
    # =========================================================================
    
    def use(self, middleware: Middleware) -> "HTTPServer":
        """
        Add middleware to the server.
        
        Middleware is executed in the order added. Place logging first,
        then auth, then route-specific middleware.
        
        Args:
            middleware: Middleware instance.
        
        Returns:
            Self for method chaining.
        
        Example:
            server.use(LoggingMiddleware())
                  .use(CORSMiddleware())
                  .use(RateLimitMiddleware())
        """
        self._middleware.add(middleware)
        return self
    
    @property
    def router(self) -> Router:
        """
        Get the router for advanced configuration.
        
        Use this for route groups, prefix routing, etc.
        """
        return self._router
    
    # =========================================================================
    # ROUTE REGISTRATION (Decorator Style)
    # =========================================================================
    
    def route(self, path: str, method: Optional[str] = None, **kwargs):
        """Register a route handler for any method."""
        return self._router.route(path, method, **kwargs)
    
    def get(self, path: str, **kwargs):
        """Register a GET route."""
        return self._router.get(path, **kwargs)
    
    def post(self, path: str, **kwargs):
        """Register a POST route."""
        return self._router.post(path, **kwargs)
    
    def put(self, path: str, **kwargs):
        """Register a PUT route."""
        return self._router.put(path, **kwargs)
    
    def delete(self, path: str, **kwargs):
        """Register a DELETE route."""
        return self._router.delete(path, **kwargs)
    
    def patch(self, path: str, **kwargs):
        """Register a PATCH route."""
        return self._router.patch(path, **kwargs)
    
    # =========================================================================
    # SERVER LIFECYCLE
    # =========================================================================
    
    def run(self, host: Optional[str] = None, port: Optional[int] = None):
        """
        Start the server (blocking).
        
        This method blocks until the server is stopped (Ctrl+C).
        
        Args:
            host: Override config host.
            port: Override config port.
        """
        if host:
            self.config.host = host
        if port:
            self.config.port = port
        
        self._running = True
        
        # ─────────────────────────────────────────────────────────────────
        # SETUP
        # ─────────────────────────────────────────────────────────────────
        self._setup_logging()
        
        # Build handler chain: middleware wrapping router
        # This creates the full request processing pipeline
        self._handler = self._middleware.wrap(self._router.handle)
        
        # Start thread pool (creates worker threads)
        self._thread_pool.start()
        
        logger.info(f"Starting HTTP server on {self.config.host}:{self.config.port}")
        self._print_startup_banner()
        
        # ─────────────────────────────────────────────────────────────────
        # MAIN LOOP (blocks here)
        # ─────────────────────────────────────────────────────────────────
        try:
            # Start accepting connections
            # This calls _handle_connection for each new client
            self._socket_server.start(self._handle_connection)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self._shutdown()
    
    def _print_startup_banner(self):
        """Print server startup information."""
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print(f"║  🚀 {self.config.server_name} running                           ║")
        print(f"║  📍 http://{self.config.host}:{self.config.port}                              ║")
        print(f"║  👷 Workers: {self.config.min_workers}-{self.config.max_workers} threads                                 ║")
        print("║  Press Ctrl+C to stop                                        ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()
        
        # Print registered routes for debugging
        self._router.print_routes()
    
    def _setup_logging(self):
        """Configure logging based on config."""
        level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        
        # Set httpserver logger level
        logging.getLogger("httpserver").setLevel(level)
    
    def _shutdown(self):
        """
        Graceful shutdown.
        
        =====================================================================
        GRACEFUL SHUTDOWN PROCESS
        =====================================================================
        
        1. Stop accepting new connections
        2. Wait for in-flight requests to complete (with timeout)
        3. Close all connections
        4. Shutdown thread pool
        5. Log shutdown complete
        
        =====================================================================
        """
        logger.info("Shutting down server...")
        self._running = False
        
        # Shutdown thread pool (waits for pending tasks)
        self._thread_pool.shutdown(wait=True, timeout=30.0)
        
        logger.info("Server stopped")
    
    # =========================================================================
    # REQUEST HANDLING
    # =========================================================================
    
    def _handle_connection(self, conn: Connection):
        """
        Queue a connection for handling by the thread pool.
        
        This is called by SocketServer for each new connection.
        We submit the connection to the thread pool for processing.
        
        Args:
            conn: The client connection.
        """
        # Submit to thread pool for async processing
        submitted = self._thread_pool.submit(
            self._process_connection,
            args=(conn,),
            timeout=self.config.timeout,
        )
        
        if not submitted:
            # Thread pool is full - server is overloaded
            logger.warning(f"[{conn.id}] Thread pool full, rejecting connection")
            self._send_error(conn, HTTPStatus.SERVICE_UNAVAILABLE, "Server overloaded")
            conn.close()
    
    def _process_connection(self, conn: Connection):
        """
        Process a connection (runs in worker thread).
        
        =====================================================================
        CONNECTION PROCESSING LOOP
        =====================================================================
        
        This method implements the HTTP keep-alive loop:
        
        1. Read request from socket
        2. Parse HTTP request
        3. Process through middleware + router
        4. Send response
        5. If keep-alive: repeat from step 1
        6. If not keep-alive: close connection
        
        =====================================================================
        
        Args:
            conn: The client connection.
        """
        with conn:  # Context manager ensures connection is closed
            while self._running:
                try:
                    # ─────────────────────────────────────────────────────
                    # READ REQUEST
                    # ─────────────────────────────────────────────────────
                    raw_request = conn.read_request()
                    if raw_request is None:
                        # Connection closed by client or timeout
                        break
                    
                    # ─────────────────────────────────────────────────────
                    # PARSE REQUEST
                    # ─────────────────────────────────────────────────────
                    try:
                        request = self._parser.parse(raw_request, conn.address)
                    except HTTPParseError as e:
                        # Malformed request - send error and close
                        self._send_error(conn, e.status_code, str(e))
                        break
                    
                    # ─────────────────────────────────────────────────────
                    # PROCESS REQUEST (Middleware + Router)
                    # ─────────────────────────────────────────────────────
                    conn.state = conn.state.PROCESSING
                    
                    try:
                        # Run through middleware pipeline and router
                        response = self._handler(request)
                    except Exception as e:
                        # Handler threw an exception - return 500
                        logger.exception(f"[{conn.id}] Handler error: {e}")
                        response = (ResponseBuilder()
                            .status(HTTPStatus.INTERNAL_SERVER_ERROR)
                            .json({"error": "Internal Server Error"})
                            .build())
                    
                    # ─────────────────────────────────────────────────────
                    # ADD CONNECTION HEADERS
                    # ─────────────────────────────────────────────────────
                    if request.is_keep_alive and self.config.keep_alive:
                        # Client wants keep-alive and we support it
                        response.headers.setdefault("Connection", "keep-alive")
                        response.headers.setdefault(
                            "Keep-Alive",
                            f"timeout={int(self.config.keep_alive_timeout)}"
                        )
                    else:
                        # Connection will close after this response
                        response.headers["Connection"] = "close"
                    
                    # ─────────────────────────────────────────────────────
                    # SEND RESPONSE
                    # ─────────────────────────────────────────────────────
                    response_bytes = response.to_bytes(self.config.server_name)
                    if not conn.send_response(response_bytes):
                        break  # Send failed, close connection
                    
                    # ─────────────────────────────────────────────────────
                    # KEEP-ALIVE OR CLOSE
                    # ─────────────────────────────────────────────────────
                    if not request.is_keep_alive or not self.config.keep_alive:
                        break  # Close connection
                    
                    # Prepare for next request on same connection
                    conn.set_keep_alive()
                    
                except TimeoutError:
                    # Request read timeout
                    self._send_error(conn, HTTPStatus.REQUEST_TIMEOUT, "Request timeout")
                    break
                
                except Exception as e:
                    logger.exception(f"[{conn.id}] Connection error: {e}")
                    break
    
    def _send_error(self, conn: Connection, status: HTTPStatus, message: str):
        """
        Send an error response.
        
        Used for errors that occur before handler processing
        (e.g., parse errors, timeouts).
        
        Args:
            conn: The connection.
            status: HTTP status code.
            message: Error message.
        """
        response = (ResponseBuilder()
            .status(status)
            .json({"error": message})
            .close_connection()
            .build())
        
        conn.send_response(response.to_bytes(self.config.server_name))


def create_app(config: Optional[ServerConfig] = None) -> HTTPServer:
    """
    Create an HTTP server application.
    
    Factory function for creating server instances.
    Commonly used pattern for WSGI/ASGI compatibility.
    
    Args:
        config: Server configuration.
    
    Returns:
        Configured HTTPServer instance.
    
    Example:
        app = create_app(ServerConfig(port=3000))
        
        @app.get("/")
        def index(request):
            return ok("Hello!")
        
        app.run()
    """
    return HTTPServer(config)


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# This module is the heart of the HTTP server, orchestrating:
#
# 1. Component Initialization: Config, sockets, threads, routing
# 2. Request Flow: Accept → Parse → Middleware → Route → Response
# 3. Connection Management: Keep-alive, timeouts, errors
# 4. Lifecycle: Startup, shutdown, signal handling
#
# KEY DESIGN DECISIONS:
# - Thread pool for concurrency (not async/await)
# - Middleware for cross-cutting concerns
# - Clean separation of components
# - Graceful shutdown with timeout
# =============================================================================
