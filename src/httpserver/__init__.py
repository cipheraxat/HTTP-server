"""
=============================================================================
HTTPSERVER - Production-Grade HTTP/1.1 Server Built From Scratch
=============================================================================

This package implements a complete HTTP server using raw Python sockets,
demonstrating deep understanding of networking fundamentals, concurrency
patterns, and clean architecture principles.

=============================================================================
PROJECT OVERVIEW
=============================================================================

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    PYHTTP SERVER ARCHITECTURE                       │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   This HTTP server is built entirely from scratch, implementing:   │
    │                                                                      │
    │   1. RAW SOCKET PROGRAMMING                                         │
    │      - TCP socket creation and binding                              │
    │      - Accept loop for incoming connections                         │
    │      - Buffered reading and writing                                 │
    │                                                                      │
    │   2. HTTP/1.1 PROTOCOL                                              │
    │      - Request parsing (method, path, headers, body)               │
    │      - Response building (status, headers, body)                   │
    │      - Keep-alive connection support                                │
    │                                                                      │
    │   3. CONCURRENT REQUEST HANDLING                                    │
    │      - Thread pool with min/max workers                            │
    │      - Task queue for pending connections                          │
    │      - Graceful shutdown                                            │
    │                                                                      │
    │   4. MIDDLEWARE ARCHITECTURE                                        │
    │      - Chain of Responsibility pattern                             │
    │      - Logging, CORS, rate limiting, compression                   │
    │                                                                      │
    │   5. URL ROUTING                                                    │
    │      - Pattern matching with regex                                  │
    │      - Dynamic path parameters (:id, *wildcard)                    │
    │      - Method-based routing (GET, POST, etc.)                      │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
PACKAGE STRUCTURE
=============================================================================

    httpserver/
    ├── __init__.py          # This file - package exports
    ├── __main__.py          # CLI entry point (python -m httpserver)
    ├── server.py            # Main HTTPServer class
    ├── config.py            # ServerConfig dataclass
    ├── core/                # Low-level components
    │   ├── socket_server.py # TCP socket handling
    │   ├── connection.py    # Connection wrapper
    │   └── thread_pool.py   # Thread pool implementation
    ├── http/                # HTTP protocol components
    │   ├── request.py       # HTTP request parsing
    │   ├── response.py      # HTTP response building
    │   ├── router.py        # URL routing
    │   ├── status_codes.py  # HTTP status enums
    │   └── mime_types.py    # MIME type detection
    ├── middleware/          # Middleware components
    │   ├── base.py          # Base middleware classes
    │   ├── logging.py       # Request logging
    │   ├── cors.py          # CORS handling
    │   ├── compression.py   # gzip compression
    │   └── rate_limit.py    # Rate limiting
    └── handlers/            # Request handlers
        ├── static.py        # Static file serving
        └── health.py        # Health check endpoints

=============================================================================
QUICK START
=============================================================================

    from httpserver import HTTPServer, ServerConfig
    from httpserver.http.response import ok, created
    from httpserver.middleware import LoggingMiddleware
    
    # Create server
    server = HTTPServer(ServerConfig(port=8080))
    
    # Add middleware
    server.use(LoggingMiddleware())
    
    # Define routes
    @server.get("/")
    def index(request):
        return ok({"message": "Hello, World!"})
    
    @server.get("/users/:id")
    def get_user(request):
        user_id = request.path_params["id"]
        return ok({"id": user_id})
    
    @server.post("/users")
    def create_user(request):
        data = request.json
        return created({"id": 1, **data})
    
    # Run server
    server.run()

=============================================================================
FEATURES FOR SDE2 RESUME
=============================================================================

This project demonstrates:

1. SYSTEMS PROGRAMMING
   - Raw socket programming without high-level frameworks
   - Understanding of TCP/IP networking fundamentals
   - Buffer management and byte handling

2. CONCURRENCY PATTERNS
   - Thread pool pattern for scalable request handling
   - Thread-safe data structures (queues, locks)
   - Graceful shutdown with proper cleanup

3. DESIGN PATTERNS
   - Chain of Responsibility (middleware)
   - Builder (response building)
   - Factory (handlers)
   - Strategy (routing)

4. PROTOCOL IMPLEMENTATION
   - HTTP/1.1 message parsing (RFC 7230)
   - Keep-alive connection management
   - Content negotiation (encoding, compression)

5. PRODUCTION FEATURES
   - Health checks for Kubernetes
   - Structured logging for observability
   - Rate limiting for protection
   - CORS for API security

=============================================================================
INTERVIEW TALKING POINTS
=============================================================================

"I built a production-grade HTTP server from scratch to deeply understand
how web servers work at the protocol level. The project handles:

- TCP connections using raw sockets
- Multi-threaded request processing with a custom thread pool
- Full HTTP/1.1 parsing and response generation
- A middleware pipeline using the Chain of Responsibility pattern
- Rate limiting with the Token Bucket algorithm
- Static file serving with ETag caching

Building this gave me deep insight into the abstractions that frameworks
like Flask and Django provide, and helped me understand networking
concepts that come up in distributed systems design."

=============================================================================
"""

__version__ = "1.0.0"
__author__ = "Your Name"

from .server import HTTPServer
from .config import ServerConfig

__all__ = ["HTTPServer", "ServerConfig", "__version__"]
