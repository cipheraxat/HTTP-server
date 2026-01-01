"""
=============================================================================
HANDLERS MODULE
=============================================================================

Built-in request handlers for common server functionality.

=============================================================================
WHAT IS A HANDLER?
=============================================================================

A handler is a function or class that processes HTTP requests and returns
HTTP responses. Handlers contain the business logic of your application.

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    REQUEST → HANDLER → RESPONSE                     │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │    Request                 Handler                 Response         │
    │   ┌─────────┐           ┌─────────┐           ┌─────────┐          │
    │   │ GET     │           │         │           │ 200 OK  │          │
    │   │ /api/   │ ────────▶ │ Logic   │ ────────▶ │         │          │
    │   │ users   │           │         │           │ {...}   │          │
    │   └─────────┘           └─────────┘           └─────────┘          │
    │                                                                      │
    │   Handler receives parsed request with:                             │
    │   - HTTP method, path, headers                                      │
    │   - Query parameters, path parameters                               │
    │   - Request body (parsed or raw)                                    │
    │                                                                      │
    │   Handler returns response with:                                    │
    │   - Status code                                                      │
    │   - Headers                                                          │
    │   - Body (JSON, HTML, bytes, etc.)                                  │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
HANDLER TYPES
=============================================================================

    ┌─────────────────────────────────────────────────────────────────────┐
    │ Type              │ Use Case                                        │
    ├─────────────────────────────────────────────────────────────────────┤
    │ Function Handler  │ Simple, stateless endpoints                    │
    │                   │ def hello(req): return ok({"msg": "Hi"})       │
    ├─────────────────────────────────────────────────────────────────────┤
    │ Class Handler     │ Complex handlers with configuration/state      │
    │                   │ StaticFileHandler, HealthHandler               │
    ├─────────────────────────────────────────────────────────────────────┤
    │ Factory Function  │ Create configured handlers                     │
    │                   │ serve_static("/var/www"), health_check()       │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
BUILT-IN HANDLERS
=============================================================================

1. StaticFileHandler / serve_static()
   - Serve static files from filesystem
   - MIME type detection
   - Directory indexes (index.html)
   - Path traversal protection
   - Caching headers (ETag, Cache-Control)

2. HealthHandler / health_check()
   - Health check endpoints for Kubernetes/load balancers
   - /health - Overall status with custom checks
   - /health/live - Liveness probe (process alive?)
   - /health/ready - Readiness probe (can serve traffic?)

=============================================================================
USAGE EXAMPLES
=============================================================================

    # Static file serving
    from httpserver.handlers import serve_static
    
    static = serve_static("/var/www/static", url_prefix="/static")
    router.get("/static/*path", static.handle)
    
    # Health checks
    from httpserver.handlers import health_check
    
    health = health_check()
    health.add_check("database", lambda: HealthStatus(db.is_connected()))
    
    router.get("/health", health.handle)
    router.get("/health/live", health.liveness)
    router.get("/health/ready", health.readiness)

=============================================================================
"""

from .static import StaticFileHandler, serve_static
from .health import HealthHandler, health_check

__all__ = [
    "StaticFileHandler",
    "serve_static",
    "HealthHandler",
    "health_check",
]
