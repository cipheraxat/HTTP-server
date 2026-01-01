"""
=============================================================================
CORS (Cross-Origin Resource Sharing) MIDDLEWARE
=============================================================================

Handles CORS to enable cross-origin requests from browsers.

=============================================================================
WHAT IS CORS?
=============================================================================

CORS is a browser security feature that restricts web pages from making
requests to a different domain than the one that served the page.

    ┌───────────────────────────────────────────────────────────────────┐
    │                    SAME-ORIGIN POLICY                             │
    ├───────────────────────────────────────────────────────────────────┤
    │                                                                    │
    │   Page from: https://app.example.com                              │
    │                                                                    │
    │   ✅ Can request: https://app.example.com/api   (same origin)     │
    │   ❌ Cannot request: https://api.example.com   (different domain) │
    │   ❌ Cannot request: http://app.example.com    (different scheme) │
    │   ❌ Cannot request: https://app.example.com:8080 (different port)│
    │                                                                    │
    │   Origin = scheme + domain + port                                 │
    │                                                                    │
    └───────────────────────────────────────────────────────────────────┘

CORS relaxes this restriction by allowing servers to declare which
origins are permitted to access their resources.

=============================================================================
CORS REQUEST FLOW
=============================================================================

    SIMPLE REQUEST (GET, HEAD, or POST with simple content types):
    
    ┌─────────┐                                          ┌─────────┐
    │ Browser │─────────── GET /api ────────────────────▶│ Server  │
    │         │           Origin: https://app.com        │         │
    │         │◀──────────────────────────────────────────│         │
    │         │    Access-Control-Allow-Origin: *        │         │
    └─────────┘                                          └─────────┘
    
    
    PREFLIGHT REQUEST (non-simple requests):
    
    ┌─────────┐                                          ┌─────────┐
    │ Browser │─────────── OPTIONS /api ────────────────▶│ Server  │
    │         │           Origin: https://app.com        │         │
    │         │           Access-Control-Request-Method: │         │
    │         │             DELETE                       │         │
    │         │◀──────────────────────────────────────────│         │
    │         │    Access-Control-Allow-Origin: *        │         │
    │         │    Access-Control-Allow-Methods: DELETE  │         │
    │         │    Access-Control-Max-Age: 86400         │         │
    │         │                                          │         │
    │         │─────────── DELETE /api/users/1 ─────────▶│         │
    │         │           Origin: https://app.com        │         │
    │         │◀──────────────────────────────────────────│         │
    │         │    Access-Control-Allow-Origin: *        │         │
    └─────────┘    200 OK                                └─────────┘
    
    Preflight checks if the actual request is safe BEFORE sending it.

=============================================================================
WHEN IS PREFLIGHT NEEDED?
=============================================================================

Simple requests (no preflight):
- Methods: GET, HEAD, POST
- Headers: Accept, Accept-Language, Content-Language
- Content-Type: application/x-www-form-urlencoded, multipart/form-data, text/plain

Non-simple requests (preflight required):
- Methods: PUT, DELETE, PATCH, etc.
- Custom headers: Authorization, X-Custom-Header
- Content-Type: application/json

=============================================================================
CORS HEADERS EXPLAINED
=============================================================================

    ┌─────────────────────────────────┬───────────────────────────────────┐
    │ Header                          │ Purpose                           │
    ├─────────────────────────────────┼───────────────────────────────────┤
    │ Access-Control-Allow-Origin     │ Which origins can access          │
    │                                 │ "*" = any, or specific origin     │
    ├─────────────────────────────────┼───────────────────────────────────┤
    │ Access-Control-Allow-Methods    │ Allowed HTTP methods              │
    │                                 │ GET, POST, PUT, DELETE, etc.      │
    ├─────────────────────────────────┼───────────────────────────────────┤
    │ Access-Control-Allow-Headers    │ Allowed request headers           │
    │                                 │ Content-Type, Authorization, etc. │
    ├─────────────────────────────────┼───────────────────────────────────┤
    │ Access-Control-Expose-Headers   │ Headers browser can access        │
    │                                 │ (otherwise only "safe" headers)   │
    ├─────────────────────────────────┼───────────────────────────────────┤
    │ Access-Control-Allow-Credentials│ Allow cookies/auth headers        │
    │                                 │ "true" or absent                  │
    ├─────────────────────────────────┼───────────────────────────────────┤
    │ Access-Control-Max-Age          │ Preflight cache duration          │
    │                                 │ In seconds (e.g., 86400 = 24h)    │
    └─────────────────────────────────┴───────────────────────────────────┘

=============================================================================
INTERVIEW QUESTIONS ABOUT CORS
=============================================================================

Q: "Why can't you use * with credentials?"
A: "When Allow-Credentials is true, the browser requires an explicit
   origin in Allow-Origin (not *). This prevents credential leakage
   to arbitrary origins. We must echo back the actual origin."

Q: "What's the Vary header for in CORS?"
A: "The Vary header tells caches that the response varies based on
   the Origin header. Without it, a cache might serve a response
   for origin A to origin B, breaking CORS."

Q: "CORS is bypassed by curl/Postman. Is it still useful?"
A: "Yes! CORS is a browser security feature. It protects users from
   malicious websites making unauthorized API calls on their behalf.
   Server-to-server calls don't need CORS."

=============================================================================
"""

from typing import Optional, List
from dataclasses import dataclass

from .base import Middleware, NextHandler
from ..http.request import HTTPRequest
from ..http.response import HTTPResponse, ResponseBuilder, HTTPStatus


@dataclass
class CORSConfig:
    """
    CORS configuration options.
    
    =========================================================================
    CONFIGURATION GUIDE
    =========================================================================
    
    DEVELOPMENT (permissive):
        CORSConfig()  # Defaults: allow everything
    
    PRODUCTION (restrictive):
        CORSConfig(
            allow_origins=["https://myapp.com"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"]
        )
    
    =========================================================================
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # Origins allowed to make requests
    # Use ["*"] for any origin, or list specific origins
    # ─────────────────────────────────────────────────────────────────────
    allow_origins: List[str] = None
    
    # ─────────────────────────────────────────────────────────────────────
    # HTTP methods allowed for CORS requests
    # ─────────────────────────────────────────────────────────────────────
    allow_methods: List[str] = None
    
    # ─────────────────────────────────────────────────────────────────────
    # Headers allowed in requests from the browser
    # ─────────────────────────────────────────────────────────────────────
    allow_headers: List[str] = None
    
    # ─────────────────────────────────────────────────────────────────────
    # Headers exposed to the browser (normally restricted)
    # ─────────────────────────────────────────────────────────────────────
    expose_headers: List[str] = None
    
    # ─────────────────────────────────────────────────────────────────────
    # Allow credentials (cookies, authorization headers)
    # WARNING: Cannot use with allow_origins=["*"]
    # ─────────────────────────────────────────────────────────────────────
    allow_credentials: bool = False
    
    # ─────────────────────────────────────────────────────────────────────
    # How long to cache preflight response (seconds)
    # Higher = fewer preflight requests, but slower policy updates
    # ─────────────────────────────────────────────────────────────────────
    max_age: int = 86400  # 24 hours
    
    def __post_init__(self):
        """Set sensible defaults for development."""
        if self.allow_origins is None:
            self.allow_origins = ["*"]  # Allow all (dev-friendly)
        if self.allow_methods is None:
            self.allow_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        if self.allow_headers is None:
            self.allow_headers = ["Content-Type", "Authorization", "X-Requested-With"]
        if self.expose_headers is None:
            self.expose_headers = []


class CORSMiddleware(Middleware):
    """
    CORS middleware for handling cross-origin requests.
    
    =========================================================================
    WHAT THIS MIDDLEWARE DOES
    =========================================================================
    
    1. Intercepts OPTIONS requests (preflight) and responds appropriately
    2. Adds CORS headers to all responses
    3. Handles the Origin/Credentials dance correctly
    
    =========================================================================
    MIDDLEWARE POSITION
    =========================================================================
    
    CORS middleware should be early in the pipeline, but after logging:
    
        pipeline.add(LoggingMiddleware())    # First - log everything
        pipeline.add(CORSMiddleware())       # Second - handle CORS
        pipeline.add(AuthMiddleware())       # Auth comes after CORS
    
    Why? Preflight requests must succeed even if the actual request
    requires authentication.
    
    =========================================================================
    USAGE EXAMPLES
    =========================================================================
    
        # Development: Allow all origins
        pipeline.add(CORSMiddleware())
        
        # Production: Restrict to specific origins
        pipeline.add(CORSMiddleware(
            config=CORSConfig(
                allow_origins=["https://myapp.com", "https://www.myapp.com"],
                allow_credentials=True
            )
        ))
        
        # API with custom headers
        pipeline.add(CORSMiddleware(
            config=CORSConfig(
                allow_headers=["Authorization", "X-API-Key", "Content-Type"],
                expose_headers=["X-Request-ID", "X-RateLimit-Remaining"]
            )
        ))
    
    =========================================================================
    """
    
    def __init__(self, config: Optional[CORSConfig] = None):
        """
        Initialize CORS middleware.
        
        Args:
            config: CORS configuration. Uses permissive defaults if not provided.
        """
        self.config = config or CORSConfig()
    
    def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse:
        """
        Handle CORS for the request.
        
        Flow:
        1. Extract Origin header from request
        2. If OPTIONS request → return preflight response
        3. Otherwise → call handler and add CORS headers to response
        """
        # Get the origin from request
        origin = request.headers.get("origin", "")
        
        # ═══════════════════════════════════════════════════════════════════
        # PREFLIGHT REQUEST HANDLING
        # ═══════════════════════════════════════════════════════════════════
        # OPTIONS requests are "preflight" - browser checking permissions
        if request.method == "OPTIONS":
            return self._handle_preflight(request, origin)
        
        # ═══════════════════════════════════════════════════════════════════
        # ACTUAL REQUEST HANDLING
        # ═══════════════════════════════════════════════════════════════════
        response = next(request)
        
        # Add CORS headers to the response
        self._add_cors_headers(response, origin)
        
        return response
    
    def _handle_preflight(self, request: HTTPRequest, origin: str) -> HTTPResponse:
        """
        Handle CORS preflight (OPTIONS) request.
        
        =====================================================================
        PREFLIGHT RESPONSE
        =====================================================================
        
        The preflight response tells the browser:
        1. Whether the origin is allowed
        2. What methods are allowed
        3. What headers are allowed
        4. How long to cache this decision
        
        We respond with 204 No Content (empty body, just headers).
        
        =====================================================================
        """
        # 204 No Content - standard preflight response
        response = ResponseBuilder().status(HTTPStatus.NO_CONTENT).build()
        
        # Add standard CORS headers
        self._add_cors_headers(response, origin)
        
        # ─────────────────────────────────────────────────────────────────
        # PREFLIGHT-SPECIFIC HEADERS
        # ─────────────────────────────────────────────────────────────────
        # Browser tells us what method/headers it wants to use
        requested_method = request.headers.get("access-control-request-method", "")
        requested_headers = request.headers.get("access-control-request-headers", "")
        
        # We respond with what we allow
        if requested_method:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.config.allow_methods)
        
        if requested_headers:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.config.allow_headers)
        
        # ─────────────────────────────────────────────────────────────────
        # PREFLIGHT CACHING
        # ─────────────────────────────────────────────────────────────────
        # Browser caches this response to avoid repeated preflight requests
        # Higher value = better performance, slower policy updates
        response.headers["Access-Control-Max-Age"] = str(self.config.max_age)
        
        return response
    
    def _add_cors_headers(self, response: HTTPResponse, origin: str):
        """
        Add CORS headers to a response.
        
        =====================================================================
        ORIGIN MATCHING LOGIC
        =====================================================================
        
        If allow_origins = ["*"]:
            - Without credentials: respond with "*"
            - With credentials: respond with the actual origin
        
        If allow_origins = ["https://app.com", "https://api.com"]:
            - Only respond if origin is in the list
            - Echo back the matching origin
        
        =====================================================================
        
        Args:
            response: The HTTP response to modify.
            origin: The origin from the request.
        """
        # ─────────────────────────────────────────────────────────────────
        # DETERMINE ALLOWED ORIGIN
        # ─────────────────────────────────────────────────────────────────
        if "*" in self.config.allow_origins:
            # Wildcard - but can't use with credentials
            if self.config.allow_credentials:
                # Must echo back the specific origin (browser requirement)
                allowed_origin = origin if origin else "*"
            else:
                allowed_origin = "*"
        elif origin in self.config.allow_origins:
            # Origin is in our allow list - echo it back
            allowed_origin = origin
        else:
            # Origin not allowed - don't add CORS headers
            # Browser will block the response
            return
        
        # ─────────────────────────────────────────────────────────────────
        # SET CORS HEADERS
        # ─────────────────────────────────────────────────────────────────
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        
        # Add credentials header if enabled
        if self.config.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # Add exposed headers (browser can only see "safe" headers by default)
        if self.config.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(
                self.config.expose_headers
            )
        
        # ─────────────────────────────────────────────────────────────────
        # VARY HEADER FOR CACHING
        # ─────────────────────────────────────────────────────────────────
        # Tells caches that response varies based on Origin header
        # Without this, cache could serve wrong CORS headers
        vary = response.headers.get("Vary", "")
        if "Origin" not in vary:
            response.headers["Vary"] = f"{vary}, Origin".lstrip(", ")
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is allowed."""
        if "*" in self.config.allow_origins:
            return True
        return origin in self.config.allow_origins


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# CORS is a browser security feature that requires server cooperation.
# This middleware handles:
#
# 1. Preflight (OPTIONS) requests - browser checking permissions
# 2. CORS headers on all responses - telling browser access is allowed
# 3. Origin matching - validating allowed origins
# 4. Credentials handling - special rules for cookies/auth
#
# SECURITY NOTES:
# - In production, always specify exact origins (not "*")
# - Be careful with allow_credentials=True
# - CORS doesn't protect against server-to-server requests
# - CORS is enforced by browsers, not servers
# =============================================================================
