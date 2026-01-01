"""
=============================================================================
URL ROUTER
=============================================================================

Implements path-based routing with support for:
- Static paths: /users, /api/health
- Dynamic parameters: /users/:id, /posts/:post_id/comments/:comment_id
- Wildcard paths: /static/*filepath
- Method-based routing: GET, POST, PUT, DELETE, etc.

=============================================================================
ROUTING ARCHITECTURE
=============================================================================

URL routing maps incoming request URLs to handler functions:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                        ROUTING FLOW                                 │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   Incoming Request                                                   │
    │   GET /users/123                                                     │
    │        │                                                             │
    │        ▼                                                             │
    │   ┌─────────────────────────────────────────────────────────────┐   │
    │   │  ROUTER                                                      │   │
    │   │                                                              │   │
    │   │  Registered Routes:                                          │   │
    │   │  ┌────────────────────────────────────────────────────────┐ │   │
    │   │  │ GET  /health       → health_handler                    │ │   │
    │   │  │ GET  /users        → list_users                        │ │   │
    │   │  │ GET  /users/:id    → get_user       ← MATCH!           │ │   │
    │   │  │ POST /users        → create_user                       │ │   │
    │   │  │ GET  /static/*path → static_handler                    │ │   │
    │   │  └────────────────────────────────────────────────────────┘ │   │
    │   │                                                              │   │
    │   │  Extracted: path_params = {"id": "123"}                     │   │
    │   └─────────────────────────────────────────────────────────────┘   │
    │        │                                                             │
    │        ▼                                                             │
    │   get_user(request)                                                  │
    │   # request.path_params["id"] == "123"                              │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
ROUTE PATTERNS
=============================================================================

1. STATIC PATHS: Exact string match
   
   Pattern: /users
   Matches: /users
   Doesn't match: /users/123, /users/, /user

2. DYNAMIC PARAMETERS (:param): Match a single path segment
   
   Pattern: /users/:id
   Matches: /users/123 → {"id": "123"}
            /users/abc → {"id": "abc"}
   Doesn't match: /users, /users/123/posts

3. WILDCARD (*param): Match remaining path
   
   Pattern: /static/*filepath  
   Matches: /static/css/style.css → {"filepath": "css/style.css"}
            /static/js/app.js    → {"filepath": "js/app.js"}
   Must be the LAST segment in pattern.

=============================================================================
PATTERN MATCHING ALGORITHM
=============================================================================

Routes are compiled to regex patterns for efficient matching:

    Pattern:  /users/:id/posts/:post_id
                 │     │         │
                 ▼     ▼         ▼
    Regex:    ^/users/(?P<id>[^/]+)/posts/(?P<post_id>[^/]+)$
                      ─────────────        ──────────────────
                      Named capture        Named capture
                      group for :id        group for :post_id

    When matching /users/42/posts/7:
    - Regex match succeeds
    - Extract named groups: {"id": "42", "post_id": "7"}
    - Return RouteMatch with params

=============================================================================
INTERVIEW QUESTIONS ABOUT ROUTING
=============================================================================

Q: "How would you implement URL routing?"
A: "I'd use regex with named capture groups. Each route pattern is
   compiled to a regex. Dynamic segments like :id become capture
   groups. On each request, I iterate routes and try to match."

Q: "What's the time complexity of route matching?"
A: "O(R × P) where R is number of routes and P is path length.
   For each route, regex matching is O(P). Advanced routers use
   radix trees for O(P) total, but regex is simpler to implement."

Q: "How do you handle route conflicts?"
A: "First-match wins. More specific routes should be registered first.
   For example, /users/me should come before /users/:id."

Q: "What's the difference between /users/:id and /users/*path?"
A: ":id matches exactly one segment (between slashes).
   *path matches everything remaining (any number of segments)."

=============================================================================
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, Any, List
import re
from enum import Enum

from .request import HTTPRequest
from .response import HTTPResponse, not_found, method_not_allowed


# =============================================================================
# TYPE ALIASES
# =============================================================================

# Handler: A function that takes a request and returns a response
# This is the signature all route handlers must follow
Handler = Callable[[HTTPRequest], HTTPResponse]


class RouteType(Enum):
    """
    Types of route segments.
    
    Used internally to categorize how each path segment should be matched.
    """
    STATIC = "static"       # /users - exact match required
    PARAM = "param"         # /:id - captures one path segment
    WILDCARD = "wildcard"   # /*filepath - captures everything remaining


@dataclass
class Route:
    """
    Represents a registered route.
    
    A route binds a URL pattern to a handler function.
    
    =========================================================================
    ANATOMY OF A ROUTE
    =========================================================================
    
        @router.get("/users/:id", name="get_user")
        def get_user(request):
            ...
            
        Route(
            path="/users/:id",      # URL pattern
            method="GET",            # HTTP method filter
            handler=get_user,        # Handler function
            name="get_user",         # Optional name for URL generation
            meta={},                 # Optional metadata for middleware
            _pattern=<compiled>,     # Compiled regex for matching
            _param_names=["id"]      # List of dynamic parameter names
        )
    
    =========================================================================
    """
    
    path: str                        # URL pattern (e.g., /users/:id)
    method: Optional[str]            # HTTP method (None = any method)
    handler: Handler                 # Handler function to call
    name: Optional[str] = None       # Route name for url_for()
    meta: Dict[str, Any] = field(default_factory=dict)  # Custom metadata
    
    # Internal: compiled regex pattern for matching
    _pattern: Optional[re.Pattern] = field(default=None, repr=False)
    # Internal: ordered list of parameter names in pattern
    _param_names: List[str] = field(default_factory=list, repr=False)


@dataclass
class RouteMatch:
    """
    Result of a successful route match.
    
    Contains the matched route and extracted path parameters.
    
    Example:
        Pattern: /users/:id
        Path:    /users/123
        Result:  RouteMatch(route=<Route>, params={"id": "123"})
    """
    route: Route                     # The Route that matched
    params: Dict[str, str]           # Extracted path parameters


class Router:
    """
    HTTP request router with dynamic path parameters.
    
    ==========================================================================
    THE ROUTER PATTERN
    ==========================================================================
    
    The Router is the traffic controller of a web framework:
    
        Incoming Requests → Router → Correct Handler
        
        GET  /          → home_handler()
        GET  /users     → list_users()
        GET  /users/123 → get_user()
        POST /users     → create_user()
        ...
    
    ==========================================================================
    DECORATOR-BASED API
    ==========================================================================
    
    Routes are typically registered using decorators (like Flask):
    
        router = Router()
        
        @router.get("/users")
        def list_users(request):
            return ok({"users": []})
        
        @router.get("/users/:id")
        def get_user(request):
            user_id = request.path_params["id"]
            return ok({"id": user_id})
        
        @router.post("/users")
        def create_user(request):
            data = request.json
            return created({"id": "new-id"})
    
    ==========================================================================
    ROUTE GROUPS
    ==========================================================================
    
    Group related routes under a common prefix:
    
        # All routes under /api/v1
        api = router.group("/api/v1")
        
        @api.get("/users")      # Matches /api/v1/users
        def list_users(request):
            ...
        
        @api.get("/posts")      # Matches /api/v1/posts
        def list_posts(request):
            ...
    
    ==========================================================================
    REVERSE ROUTING
    ==========================================================================
    
    Generate URLs from route names (useful for redirects):
    
        @router.get("/users/:id", name="get_user")
        def get_user(request):
            ...
        
        # Later:
        url = router.url_for("get_user", id="123")  # Returns "/users/123"
    
    ==========================================================================
    """
    
    def __init__(self, prefix: str = ""):
        """
        Initialize the router.
        
        Args:
            prefix: URL prefix for all routes in this router.
                   Used for route groups: Router(prefix="/api/v1")
        """
        self.prefix = prefix.rstrip("/")  # Remove trailing slash
        self._routes: List[Route] = []     # All registered routes
        self._named_routes: Dict[str, Route] = {}  # Routes by name
        self._sub_routers: List[tuple[str, "Router"]] = []  # Mounted routers
    
    # =========================================================================
    # ROUTE REGISTRATION
    # =========================================================================
    
    def add_route(
        self,
        path: str,
        handler: Handler,
        method: Optional[str] = None,
        name: Optional[str] = None,
        **meta: Any
    ) -> Route:
        """
        Register a route.
        
        This is the core method for adding routes. The decorator methods
        (get, post, etc.) are convenience wrappers around this.
        
        Args:
            path: URL pattern (e.g., /users/:id)
            handler: Handler function that takes request, returns response
            method: HTTP method (None for any method)
            name: Optional route name for reverse routing
            **meta: Additional metadata (accessible via route.meta)
        
        Returns:
            The registered Route object
        
        Example:
            router.add_route("/users/:id", get_user, method="GET", name="get_user")
        """
        # Combine router prefix with route path
        full_path = self.prefix + path
        
        # Compile pattern to regex
        pattern, param_names = self._compile_pattern(full_path)
        
        # Create route object
        route = Route(
            path=full_path,
            method=method.upper() if method else None,
            handler=handler,
            name=name,
            meta=meta,
            _pattern=pattern,
            _param_names=param_names,
        )
        
        self._routes.append(route)
        
        # Store by name for url_for()
        if name:
            self._named_routes[name] = route
        
        return route
    
    def _compile_pattern(self, path: str) -> tuple[re.Pattern, List[str]]:
        """
        Compile a path pattern into a regex.
        
        =====================================================================
        PATTERN COMPILATION
        =====================================================================
        
        Input:  "/users/:id/posts/:post_id"
        
        Step 1: Split by "/"
                ["", "users", ":id", "posts", ":post_id"]
        
        Step 2: Process each segment
                ""           → (skip empty)
                "users"      → /users              (static)
                ":id"        → /(?P<id>[^/]+)     (param)
                "posts"      → /posts              (static)
                ":post_id"   → /(?P<post_id>[^/]+)(param)
        
        Step 3: Join and add anchors
                ^/users/(?P<id>[^/]+)/posts/(?P<post_id>[^/]+)$
        
        =====================================================================
        
        Patterns:
            :param - Match a single path segment (no slashes)
            *param - Match remaining path (including slashes)
        
        Args:
            path: Route pattern to compile
        
        Returns:
            Tuple of (compiled regex, list of parameter names)
        """
        param_names: List[str] = []
        regex_parts = ["^"]
        
        segments = path.split("/")
        for i, segment in enumerate(segments):
            if not segment:
                continue
            
            regex_parts.append("/")
            
            if segment.startswith(":"):
                # ---------------------------------------------------------
                # DYNAMIC PARAMETER: :id
                # ---------------------------------------------------------
                # Matches a single path segment (anything except /)
                # Uses named capture group for extraction
                #
                # :id → (?P<id>[^/]+)
                #       ─────── ────
                #       │       │
                #       │       └── One or more non-slash chars
                #       └────────── Named capture group "id"
                #
                param_name = segment[1:]  # Remove leading ":"
                param_names.append(param_name)
                regex_parts.append(f"(?P<{param_name}>[^/]+)")
            
            elif segment.startswith("*"):
                # ---------------------------------------------------------
                # WILDCARD: *filepath
                # ---------------------------------------------------------
                # Matches everything remaining (including slashes)
                # Must be the last segment in the pattern
                #
                # *filepath → (?P<filepath>.*)
                #
                param_name = segment[1:] or "wildcard"
                param_names.append(param_name)
                regex_parts.append(f"(?P<{param_name}>.*)")
                break  # Wildcard consumes everything, stop here
            
            else:
                # ---------------------------------------------------------
                # STATIC SEGMENT: users
                # ---------------------------------------------------------
                # Exact match required
                # re.escape handles special chars in segment
                #
                regex_parts.append(re.escape(segment))
        
        # End anchor ensures full match (not prefix match)
        regex_parts.append("$")
        pattern = re.compile("".join(regex_parts))
        
        return pattern, param_names
    
    # =========================================================================
    # ROUTE MATCHING
    # =========================================================================
    
    def match(self, method: str, path: str) -> Optional[RouteMatch]:
        """
        Find a matching route for the given method and path.
        
        Iterates through all registered routes and returns the first match.
        Order matters: first-registered, first-matched.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (/users/123)
        
        Returns:
            RouteMatch if found, None otherwise
        """
        # Normalize path (ensure leading slash, remove trailing)
        path = "/" + path.strip("/") if path != "/" else "/"
        
        # Try each route
        for route in self._routes:
            # Check method (None means any method is allowed)
            if route.method and route.method != method.upper():
                continue
            
            # Check pattern
            if route._pattern:
                match = route._pattern.match(path)
                if match:
                    # Extract named groups as params
                    return RouteMatch(
                        route=route,
                        params=match.groupdict()
                    )
        
        # Check sub-routers (mounted routers)
        for prefix, sub_router in self._sub_routers:
            if path.startswith(prefix):
                result = sub_router.match(method, path)
                if result:
                    return result
        
        return None  # No match found
    
    def get_allowed_methods(self, path: str) -> List[str]:
        """
        Get list of allowed methods for a path.
        
        Used to generate the Allow header for 405 Method Not Allowed responses.
        
        Args:
            path: Request path
        
        Returns:
            List of allowed HTTP methods (e.g., ["GET", "POST"])
        """
        path = "/" + path.strip("/") if path != "/" else "/"
        methods = set()
        
        for route in self._routes:
            if route._pattern and route._pattern.match(path):
                if route.method:
                    methods.add(route.method)
                else:
                    # Route accepts any method
                    return ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        
        return sorted(methods)
    
    def handle(self, request: HTTPRequest) -> HTTPResponse:
        """
        Route a request to the appropriate handler.
        
        This is the main entry point for request handling:
        1. Find matching route
        2. Extract path parameters
        3. Call handler
        4. Return response (or error if no match)
        
        Args:
            request: The HTTP request to route
        
        Returns:
            HTTP response from handler or error response
        """
        # Try to find a matching route
        match = self.match(request.method, request.path)
        
        if match:
            # Inject path parameters into request
            # Handler can access them via request.path_params
            request.path_params = match.params
            return match.route.handler(request)
        
        # No route found - check if path exists with different method
        allowed = self.get_allowed_methods(request.path)
        if allowed:
            # Path exists but method not allowed → 405
            return method_not_allowed(allowed)
        
        # Path doesn't exist at all → 404
        # Path doesn't exist at all → 404
        return not_found(f"No route matches {request.path}")
    
    # =========================================================================
    # DECORATOR-STYLE ROUTE REGISTRATION
    # =========================================================================
    #
    # These decorators provide a clean, Flask-like API for registering routes.
    # They're syntactic sugar around add_route().
    #
    # Example:
    #     @router.get("/users")
    #     def list_users(request):
    #         return ok([])
    #
    # Is equivalent to:
    #     def list_users(request):
    #         return ok([])
    #     router.add_route("/users", list_users, method="GET")
    #
    # =========================================================================
    
    def route(
        self,
        path: str,
        method: Optional[str] = None,
        name: Optional[str] = None,
        **meta: Any
    ) -> Callable[[Handler], Handler]:
        """
        Decorator for registering routes.
        
        This is the base decorator. Use @router.get, @router.post, etc.
        for method-specific routes.
        
        Args:
            path: URL pattern
            method: HTTP method (None for any)
            name: Route name for reverse routing
            **meta: Additional metadata
        
        Returns:
            Decorator function
        
        Usage:
            @router.route("/users", method="GET")
            def list_users(request):
                return ok([])
        """
        def decorator(handler: Handler) -> Handler:
            self.add_route(path, handler, method, name, **meta)
            return handler  # Return handler unchanged (allows stacking decorators)
        return decorator
    
    def get(self, path: str, name: Optional[str] = None, **meta: Any) -> Callable[[Handler], Handler]:
        """Register a GET route. Most common for reading data."""
        return self.route(path, "GET", name, **meta)
    
    def post(self, path: str, name: Optional[str] = None, **meta: Any) -> Callable[[Handler], Handler]:
        """Register a POST route. Used for creating resources."""
        return self.route(path, "POST", name, **meta)
    
    def put(self, path: str, name: Optional[str] = None, **meta: Any) -> Callable[[Handler], Handler]:
        """Register a PUT route. Used for replacing resources."""
        return self.route(path, "PUT", name, **meta)
    
    def delete(self, path: str, name: Optional[str] = None, **meta: Any) -> Callable[[Handler], Handler]:
        """Register a DELETE route. Used for removing resources."""
        return self.route(path, "DELETE", name, **meta)
    
    def patch(self, path: str, name: Optional[str] = None, **meta: Any) -> Callable[[Handler], Handler]:
        """Register a PATCH route. Used for partial updates."""
        return self.route(path, "PATCH", name, **meta)
    
    def head(self, path: str, name: Optional[str] = None, **meta: Any) -> Callable[[Handler], Handler]:
        """Register a HEAD route. Like GET but returns only headers."""
        return self.route(path, "HEAD", name, **meta)
    
    def options(self, path: str, name: Optional[str] = None, **meta: Any) -> Callable[[Handler], Handler]:
        """Register an OPTIONS route. Used for CORS preflight."""
        return self.route(path, "OPTIONS", name, **meta)
    
    # =========================================================================
    # ROUTER COMPOSITION
    # =========================================================================
    #
    # These methods allow building complex routing structures by combining
    # multiple routers. This is useful for:
    # - Organizing code by feature/domain
    # - API versioning (/api/v1, /api/v2)
    # - Mounting reusable route sets
    #
    # =========================================================================
    
    def include(self, prefix: str, router: "Router") -> None:
        """
        Mount a sub-router at the given prefix.
        
        This allows organizing routes into separate files/modules:
        
            # In users.py:
            user_router = Router()
            @user_router.get("/")
            def list_users(request):
                ...
            
            # In main.py:
            main_router.include("/users", user_router)
            # Now /users/ is handled by user_router
        
        Args:
            prefix: URL prefix for the sub-router
            router: The sub-router to mount
        """
        # Update all routes in sub-router with new prefix
        full_prefix = self.prefix + prefix
        router.prefix = full_prefix
        
        # Recompile patterns with new prefix
        for route in router._routes:
            route.path = full_prefix + route.path[len(router.prefix) - len(prefix):]
            route._pattern, route._param_names = self._compile_pattern(route.path)
        
        self._sub_routers.append((prefix, router))
    
    def group(self, prefix: str) -> "Router":
        """
        Create a route group with a prefix.
        
        Route groups make it easy to organize related routes:
        
            # All routes under /api/v1
            api = router.group("/api/v1")
            
            @api.get("/users")      # Matches /api/v1/users
            def list_users(request):
                ...
            
            @api.get("/posts")      # Matches /api/v1/posts
            def list_posts(request):
                ...
        
        Args:
            prefix: URL prefix for the group
        
        Returns:
            A new Router with the prefix (can be used for decorators)
        """
        sub_router = Router(self.prefix + prefix)
        self._sub_routers.append((prefix, sub_router))
        return sub_router
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def url_for(self, name: str, **params: str) -> Optional[str]:
        """
        Generate URL for a named route (reverse routing).
        
        This is useful for generating redirect URLs without hardcoding paths:
        
            @router.get("/users/:id", name="get_user")
            def get_user(request):
                ...
            
            # In another handler:
            url = router.url_for("get_user", id="123")
            return redirect(url)  # Redirects to /users/123
        
        Args:
            name: Route name (set via name parameter in decorator)
            **params: Path parameters to substitute
        
        Returns:
            Generated URL or None if route not found
        """
        route = self._named_routes.get(name)
        if not route:
            return None
        
        url = route.path
        for param_name, value in params.items():
            url = url.replace(f":{param_name}", value)
            url = url.replace(f"*{param_name}", value)
        
        return url
    
    def routes(self) -> List[Route]:
        """
        Get all registered routes (including sub-routers).
        
        Useful for debugging and documentation generation.
        
        Returns:
            List of all Route objects
        """
        all_routes = list(self._routes)
        for _, sub_router in self._sub_routers:
            all_routes.extend(sub_router.routes())
        return all_routes
    
    def print_routes(self) -> None:
        """
        Print all registered routes (useful for debugging).
        
        Example output:
            Registered Routes:
            ------------------------------------------------------------
              GET      /health
              GET      /users
              GET      /users/:id
              POST     /users
              DELETE   /users/:id
            ------------------------------------------------------------
        """
        print("\nRegistered Routes:")
        print("-" * 60)
        for route in self.routes():
            method = route.method or "ANY"
            print(f"  {method:8} {route.path}")
        print("-" * 60)
