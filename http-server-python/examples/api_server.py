"""
=============================================================================
EXAMPLE: REST API SERVER
=============================================================================

This example demonstrates how to build a complete REST API using our
HTTP server built from scratch. It showcases:

1. Server configuration and initialization
2. Middleware pipeline (logging, CORS, rate limiting)
3. RESTful route definitions (GET, POST, PUT, DELETE)
4. Request parsing (path params, JSON body)
5. Response building with proper status codes
6. Error handling patterns

ARCHITECTURE OVERVIEW:
─────────────────────

    ┌─────────────────────────────────────────────────────────────────┐
    │                        Client Request                            │
    │              curl http://localhost:8080/api/users               │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      1. SOCKET SERVER                            │
    │  ─────────────────────────────────────────────────────────────  │
    │  • Listens on 127.0.0.1:8080                                    │
    │  • Accepts TCP connections                                       │
    │  • Performs 3-way handshake (SYN → SYN-ACK → ACK)               │
    │  • Creates Connection object for each client                     │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      2. THREAD POOL                              │
    │  ─────────────────────────────────────────────────────────────  │
    │  • 4-8 worker threads waiting for tasks                          │
    │  • Connection is submitted to the pool                           │
    │  • Worker picks up connection and processes it                   │
    │  • Allows handling multiple clients concurrently                 │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      3. REQUEST PARSER                           │
    │  ─────────────────────────────────────────────────────────────  │
    │  Raw bytes from socket:                                          │
    │    GET /api/users HTTP/1.1\r\n                                  │
    │    Host: localhost:8080\r\n                                     │
    │    \r\n                                                          │
    │                                                                  │
    │  Parsed into HTTPRequest object:                                 │
    │    request.method = "GET"                                        │
    │    request.path = "/api/users"                                   │
    │    request.headers = {"host": "localhost:8080"}                 │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   4. MIDDLEWARE PIPELINE                         │
    │  ─────────────────────────────────────────────────────────────  │
    │                                                                  │
    │  Request flows through each middleware in order:                 │
    │                                                                  │
    │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
    │  │   Logging    │──►│    CORS      │──►│  RateLimit   │──► ... │
    │  │  Middleware  │   │  Middleware  │   │  Middleware  │        │
    │  └──────────────┘   └──────────────┘   └──────────────┘        │
    │         │                   │                   │                │
    │     Log start           Add CORS          Check rate            │
    │     timestamp           headers           limit quota            │
    │         │                   │                   │                │
    │         └───────────────────┴───────────────────┘                │
    │                            │                                     │
    │                    (After handler runs)                          │
    │                            │                                     │
    │         ┌───────────────────┴───────────────────┐                │
    │         │                   │                   │                │
    │     Log duration        Add Vary           Add rate             │
    │     & status           header             limit headers          │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                        5. ROUTER                                 │
    │  ─────────────────────────────────────────────────────────────  │
    │                                                                  │
    │  Registered routes:                                              │
    │    GET    /api/users       → list_users()                       │
    │    GET    /api/users/:id   → get_user()                         │
    │    POST   /api/users       → create_user()                      │
    │    PUT    /api/users/:id   → update_user()                      │
    │    DELETE /api/users/:id   → delete_user()                      │
    │                                                                  │
    │  Router matches: GET /api/users → calls list_users(request)     │
    │                                                                  │
    │  For dynamic routes like /api/users/:id:                        │
    │    GET /api/users/42 → get_user(request)                        │
    │    request.path_params = {"id": "42"}                           │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      6. HANDLER FUNCTION                         │
    │  ─────────────────────────────────────────────────────────────  │
    │                                                                  │
    │  def list_users(request):                                        │
    │      # Business logic here                                       │
    │      return ok({"users": [...]})                                │
    │                                                                  │
    │  Returns HTTPResponse object with:                               │
    │    status = 200 OK                                               │
    │    headers = {"Content-Type": "application/json"}               │
    │    body = '{"users": [...]}'                                    │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   7. RESPONSE SERIALIZATION                      │
    │  ─────────────────────────────────────────────────────────────  │
    │                                                                  │
    │  HTTPResponse is converted to bytes:                             │
    │                                                                  │
    │    HTTP/1.1 200 OK\r\n                                          │
    │    Content-Type: application/json\r\n                           │
    │    Content-Length: 42\r\n                                       │
    │    Date: Wed, 01 Jan 2026 12:00:00 GMT\r\n                      │
    │    \r\n                                                          │
    │    {"users": [...]}                                              │
    │                                                                  │
    │  These bytes are sent over the TCP socket to the client.         │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                       Client Response                            │
    │                   {"users": [...]} displayed                     │
    └─────────────────────────────────────────────────────────────────┘

"""

import sys
from pathlib import Path

# =============================================================================
# PATH SETUP
# =============================================================================
# Add the src directory to Python's module search path.
# This allows us to import our httpserver package during development
# without needing to install it first.
#
# In production, you would install the package with `pip install -e .`
# and this wouldn't be necessary.

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# IMPORTS
# =============================================================================
# 
# HTTPServer: The main server class that ties everything together
# ServerConfig: Configuration dataclass for server settings
#
# Response helpers (from httpserver.http):
#   - ok(): Creates 200 OK response
#   - created(): Creates 201 Created response (for POST success)
#   - not_found(): Creates 404 Not Found response
#   - bad_request(): Creates 400 Bad Request response
#   - no_content(): Creates 204 No Content response (for DELETE success)
#
# Middleware (from httpserver.middleware):
#   - LoggingMiddleware: Logs every request with timing info
#   - CORSMiddleware: Adds Cross-Origin Resource Sharing headers
#   - RateLimitMiddleware: Prevents abuse with token bucket algorithm
#
# Handlers (from httpserver.handlers):
#   - HealthHandler: Kubernetes-style health check endpoints

from httpserver import HTTPServer, ServerConfig
from httpserver.http import ok, created, not_found, bad_request, no_content
from httpserver.middleware import LoggingMiddleware, CORSMiddleware, RateLimitMiddleware
from httpserver.handlers import HealthHandler


# =============================================================================
# IN-MEMORY DATABASE
# =============================================================================
# For this example, we use a simple dictionary as our "database".
# In a real application, you would use a proper database like:
#   - PostgreSQL (with psycopg2 or asyncpg)
#   - MongoDB (with pymongo)
#   - Redis (with redis-py)
#   - SQLite (with sqlite3)
#
# Note: This is NOT thread-safe! In production with multiple workers,
# you would need proper synchronization (locks) or a real database.

users_db: dict[int, dict] = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
}

# Auto-incrementing ID for new users
# In a real database, this would be handled automatically (e.g., SERIAL in PostgreSQL)
next_id = 3


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    """
    Main application entry point.
    
    This function:
    1. Creates and configures the server
    2. Registers middleware
    3. Defines API routes
    4. Starts the server (blocking)
    """
    
    # =========================================================================
    # STEP 1: SERVER CONFIGURATION
    # =========================================================================
    # ServerConfig holds all settings for the HTTP server.
    # These settings control networking, concurrency, and logging behavior.
    
    config = ServerConfig(
        # ─────────────────────────────────────────────────────────────────────
        # NETWORK SETTINGS
        # ─────────────────────────────────────────────────────────────────────
        
        host="127.0.0.1",  # The IP address to bind to
                           # 
                           # "127.0.0.1" (localhost) - Only accessible from this machine
                           #   → Safe for development
                           #   → Packets never leave the network interface
                           # 
                           # "0.0.0.0" (all interfaces) - Accessible from any network
                           #   → Required for Docker containers
                           #   → Required for accessing from other devices on LAN
                           #   → Use with caution in production!
        
        port=8080,         # The TCP port to listen on (0-65535)
                           #
                           # Well-known ports (0-1023) require root/admin:
                           #   80  = HTTP (standard web)
                           #   443 = HTTPS (secure web)
                           #
                           # Common development ports:
                           #   3000 = Node.js convention
                           #   5000 = Flask convention
                           #   8000 = Django convention
                           #   8080 = HTTP alternate (we use this!)
        
        # ─────────────────────────────────────────────────────────────────────
        # CONCURRENCY SETTINGS
        # ─────────────────────────────────────────────────────────────────────
        
        min_workers=4,     # Minimum number of worker threads
                           # These threads are created at startup and always running.
                           # They wait for connections in the thread pool queue.
                           #
                           # Rule of thumb: Start with CPU cores count
                           
        max_workers=8,     # Maximum number of worker threads
                           # If all workers are busy and queue is filling up,
                           # new workers are spawned up to this limit.
                           #
                           # Rule of thumb: 2-4x CPU cores for I/O-bound work
                           #
                           # WHY NOT MORE?
                           # - Too many threads = context switching overhead
                           # - Memory usage increases with each thread
                           # - Python's GIL limits true parallelism anyway
        
        # ─────────────────────────────────────────────────────────────────────
        # LOGGING SETTINGS
        # ─────────────────────────────────────────────────────────────────────
        
        log_level="INFO",  # Logging verbosity
                           # DEBUG   = Everything (noisy, for debugging)
                           # INFO    = General operational info (default)
                           # WARNING = Something unexpected but handled
                           # ERROR   = Something failed
        
        # ─────────────────────────────────────────────────────────────────────
        # SERVER IDENTITY
        # ─────────────────────────────────────────────────────────────────────
        
        server_name="ExampleAPI/1.0",  # Sent in the "Server" response header
                                        # Identifies your server in responses
                                        # Example response header:
                                        #   Server: ExampleAPI/1.0
    )
    
    # Create the HTTPServer instance with our configuration
    # This initializes (but doesn't start) all the internal components:
    #   - SocketServer (TCP listener)
    #   - ThreadPool (worker threads)
    #   - RequestParser (HTTP parsing)
    #   - Router (URL dispatching)
    #   - MiddlewarePipeline (request/response processing)
    
    server = HTTPServer(config)
    
    
    # =========================================================================
    # STEP 2: MIDDLEWARE REGISTRATION
    # =========================================================================
    # Middleware is code that runs BEFORE and AFTER every request handler.
    # It's used for cross-cutting concerns like logging, security, caching.
    #
    # Middleware executes in the ORDER they are added:
    #
    #   Request:  Logging → CORS → RateLimit → Handler
    #   Response: Handler → RateLimit → CORS → Logging
    #
    # This is the "Chain of Responsibility" design pattern.
    #
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ MIDDLEWARE PIPELINE VISUALIZATION                                   │
    # ├─────────────────────────────────────────────────────────────────────┤
    # │                                                                     │
    # │   Request ──┐                                                       │
    # │             ▼                                                       │
    # │   ┌─────────────────┐                                              │
    # │   │ LoggingMiddleware│ ← Records start time, generates request ID  │
    # │   └────────┬────────┘                                              │
    # │            ▼                                                       │
    # │   ┌─────────────────┐                                              │
    # │   │ CORSMiddleware  │ ← Handles OPTIONS preflight, adds headers    │
    # │   └────────┬────────┘                                              │
    # │            ▼                                                       │
    # │   ┌─────────────────┐                                              │
    # │   │RateLimitMiddleware│ ← Checks token bucket, may reject (429)    │
    # │   └────────┬────────┘                                              │
    # │            ▼                                                       │
    # │   ┌─────────────────┐                                              │
    # │   │  Route Handler  │ ← Your business logic                        │
    # │   └────────┬────────┘                                              │
    # │            ▼                                                       │
    # │   (Response bubbles back up through middleware)                    │
    # │            ▼                                                       │
    # │   Response ◄─┘                                                      │
    # │                                                                     │
    # └─────────────────────────────────────────────────────────────────────┘
    
    # ─────────────────────────────────────────────────────────────────────────
    # LOGGING MIDDLEWARE
    # ─────────────────────────────────────────────────────────────────────────
    # Logs every request with:
    #   - Request ID (for distributed tracing)
    #   - Method and path
    #   - Response status code
    #   - Duration in milliseconds
    #
    # log_format options:
    #   "text" → Human-readable: 127.0.0.1 - - [01/Jan/2026:12:00:00] "GET /api/users" 200 45 2.34ms
    #   "json" → Machine-parseable: {"request_id": "abc123", "method": "GET", ...}
    #
    # JSON format is better for log aggregation (ELK stack, Datadog, etc.)
    
    server.use(LoggingMiddleware(log_format="text"))
    
    # ─────────────────────────────────────────────────────────────────────────
    # CORS MIDDLEWARE
    # ─────────────────────────────────────────────────────────────────────────
    # CORS (Cross-Origin Resource Sharing) is a security feature in browsers.
    #
    # PROBLEM: By default, browsers block JavaScript from making requests to
    # a different origin (domain:port) than the page was loaded from.
    #
    # EXAMPLE:
    #   Page loaded from: https://myapp.com
    #   API request to:   http://localhost:8080/api/users  ← BLOCKED!
    #
    # SOLUTION: The API server must send special headers allowing the request:
    #   Access-Control-Allow-Origin: https://myapp.com
    #   Access-Control-Allow-Methods: GET, POST, PUT, DELETE
    #   Access-Control-Allow-Headers: Content-Type, Authorization
    #
    # HOW IT WORKS:
    # 1. Browser sends "preflight" OPTIONS request before the real request
    # 2. Server responds with allowed origins/methods/headers
    # 3. If allowed, browser sends the actual request
    #
    # Default CORSMiddleware() allows all origins ("*") - good for development.
    # In production, specify exact origins for security.
    
    server.use(CORSMiddleware())
    
    # ─────────────────────────────────────────────────────────────────────────
    # RATE LIMIT MIDDLEWARE
    # ─────────────────────────────────────────────────────────────────────────
    # Prevents abuse by limiting how many requests a client can make.
    #
    # Uses the TOKEN BUCKET algorithm (interview favorite!):
    #
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ TOKEN BUCKET ALGORITHM                                             │
    # ├─────────────────────────────────────────────────────────────────────┤
    # │                                                                     │
    # │  Imagine a bucket that holds tokens:                               │
    # │                                                                     │
    # │  ┌───────────┐                                                     │
    # │  │ ● ● ● ●   │ ← Bucket with max 20 tokens (burst_size)           │
    # │  │ ● ● ● ●   │                                                     │
    # │  │ ● ● ● ●   │                                                     │
    # │  └───────────┘                                                     │
    # │       ▲                                                            │
    # │       │ Tokens added at rate: 10/second (requests_per_second)      │
    # │                                                                     │
    # │  • Each request CONSUMES 1 token                                   │
    # │  • If no tokens available → 429 Too Many Requests                  │
    # │  • Tokens refill over time at constant rate                        │
    # │                                                                     │
    # │  BENEFITS:                                                         │
    # │  • Allows short bursts (up to burst_size)                          │
    # │  • Smooths out traffic over time                                   │
    # │  • Simple to understand and implement                              │
    # │  • Each client has their own bucket (by IP address)                │
    # │                                                                     │
    # └─────────────────────────────────────────────────────────────────────┘
    #
    # With these settings:
    #   - Client can burst 20 requests immediately
    #   - Then sustained rate of 10 requests/second
    #   - Bucket refills at 10 tokens/second
    
    server.use(RateLimitMiddleware(requests_per_second=10, burst_size=20))
    
    
    # =========================================================================
    # STEP 3: HEALTH CHECK ENDPOINTS
    # =========================================================================
    # Health checks are essential for production deployments.
    # They let orchestration systems (Kubernetes, Docker Swarm, load balancers)
    # know if your server is alive and ready to handle traffic.
    #
    # THREE TYPES OF HEALTH CHECKS:
    #
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ 1. /health - Overall Health                                        │
    # │    Returns: {"status": "healthy", "uptime_seconds": 3600, ...}     │
    # │    Use: Monitoring dashboards, alerts                              │
    # ├─────────────────────────────────────────────────────────────────────┤
    # │ 2. /health/live - Liveness Probe                                   │
    # │    Question: "Is the process running?"                             │
    # │    Returns: 200 OK if process is alive                             │
    # │    Use: Kubernetes uses this to decide if pod should be RESTARTED  │
    # │    If this fails → Pod is killed and recreated                     │
    # ├─────────────────────────────────────────────────────────────────────┤
    # │ 3. /health/ready - Readiness Probe                                 │
    # │    Question: "Can it handle requests?"                             │
    # │    Returns: 200 OK if ready, 503 if not ready                      │
    # │    Use: Kubernetes uses this to decide if pod should receive TRAFFIC│
    # │    If this fails → Pod is removed from load balancer               │
    # │    Example: Not ready during startup, database connection issues   │
    # └─────────────────────────────────────────────────────────────────────┘
    
    health = HealthHandler(include_system_info=True)
    
    # Register health endpoints
    # Note: We use server.get("/health")(health.handle) instead of decorators
    # because health.handle is already a method, not a new function.
    server.get("/health")(health.handle)
    server.get("/health/live")(health.liveness)
    server.get("/health/ready")(health.readiness)
    
    
    # =========================================================================
    # STEP 4: API ROUTE DEFINITIONS
    # =========================================================================
    # Routes map URL patterns to handler functions.
    #
    # REST API CONVENTIONS:
    #
    # ┌───────────┬─────────────────┬──────────────┬───────────────────────┐
    # │ Method    │ Path            │ Action       │ Response              │
    # ├───────────┼─────────────────┼──────────────┼───────────────────────┤
    # │ GET       │ /api/users      │ List all     │ 200 + array           │
    # │ GET       │ /api/users/:id  │ Get one      │ 200 + object or 404   │
    # │ POST      │ /api/users      │ Create       │ 201 + object          │
    # │ PUT       │ /api/users/:id  │ Update       │ 200 + object or 404   │
    # │ DELETE    │ /api/users/:id  │ Delete       │ 204 (no content)      │
    # └───────────┴─────────────────┴──────────────┴───────────────────────┘
    #
    # PATH PARAMETERS:
    #   :id in the path is a dynamic parameter
    #   /api/users/42 → request.path_params = {"id": "42"}
    
    
    # ─────────────────────────────────────────────────────────────────────────
    # LIST ALL USERS
    # ─────────────────────────────────────────────────────────────────────────
    # GET /api/users
    #
    # Example request:
    #   curl http://localhost:8080/api/users
    #
    # Example response:
    #   HTTP/1.1 200 OK
    #   Content-Type: application/json
    #   
    #   {"users": [{"id": 1, "name": "Alice", ...}, {"id": 2, "name": "Bob", ...}]}
    
    @server.get("/api/users")
    def list_users(request):
        """
        List all users.
        
        This is the simplest handler - just return all data.
        The ok() function:
          1. Sets status to 200 OK
          2. Serializes the dict to JSON
          3. Sets Content-Type: application/json
        """
        return ok({"users": list(users_db.values())})
    
    
    # ─────────────────────────────────────────────────────────────────────────
    # GET SINGLE USER
    # ─────────────────────────────────────────────────────────────────────────
    # GET /api/users/:id
    #
    # The :id part is a path parameter. When a request comes in for
    # /api/users/42, the router extracts "42" and puts it in path_params.
    #
    # Example request:
    #   curl http://localhost:8080/api/users/1
    #
    # Example response (found):
    #   HTTP/1.1 200 OK
    #   {"id": 1, "name": "Alice", "email": "alice@example.com"}
    #
    # Example response (not found):
    #   HTTP/1.1 404 Not Found
    #   {"error": "User 999 not found"}
    
    @server.get("/api/users/:id")
    def get_user(request):
        """
        Get a single user by ID.
        
        Demonstrates:
          - Accessing path parameters
          - Returning 404 for missing resources
        """
        # Extract the :id parameter from the URL
        # Note: Path params are always strings, so we convert to int
        user_id = int(request.path_params["id"])
        
        # Check if user exists
        if user_id not in users_db:
            # Return 404 Not Found with error message
            # The not_found() function creates:
            #   Status: 404 Not Found
            #   Body: {"error": "User 999 not found"}
            return not_found(f"User {user_id} not found")
        
        # Return the user data with 200 OK
        return ok(users_db[user_id])
    
    
    # ─────────────────────────────────────────────────────────────────────────
    # CREATE NEW USER
    # ─────────────────────────────────────────────────────────────────────────
    # POST /api/users
    #
    # POST requests create new resources. The request body contains the data.
    #
    # Example request:
    #   curl -X POST http://localhost:8080/api/users \
    #        -H "Content-Type: application/json" \
    #        -d '{"name": "Charlie", "email": "charlie@example.com"}'
    #
    # Example response:
    #   HTTP/1.1 201 Created
    #   Location: /api/users/3
    #   
    #   {"id": 3, "name": "Charlie", "email": "charlie@example.com"}
    #
    # STATUS 201 vs 200:
    #   200 OK = Request succeeded (general success)
    #   201 Created = New resource was created (more specific)
    #
    # LOCATION HEADER:
    #   Points to the URL of the newly created resource
    #   Clients can follow this to retrieve the new resource
    
    @server.post("/api/users")
    def create_user(request):
        """
        Create a new user.
        
        Demonstrates:
          - Parsing JSON request body
          - Input validation
          - Returning 201 Created with Location header
        """
        global next_id  # We need to modify the global counter
        
        # ─────────────────────────────────────────────────────────────────────
        # PARSE REQUEST BODY
        # ─────────────────────────────────────────────────────────────────────
        # request.json automatically:
        #   1. Checks Content-Type is application/json
        #   2. Decodes the body bytes as UTF-8
        #   3. Parses JSON into Python dict/list
        #   4. Raises exception if invalid JSON
        
        try:
            data = request.json
        except Exception:
            # If JSON parsing fails, return 400 Bad Request
            # This happens when:
            #   - Body is not valid JSON (e.g., missing quotes, trailing comma)
            #   - Body is not UTF-8 encoded
            #   - Content-Type header is wrong
            return bad_request("Invalid JSON body")
        
        # ─────────────────────────────────────────────────────────────────────
        # INPUT VALIDATION
        # ─────────────────────────────────────────────────────────────────────
        # Always validate input! Never trust client data.
        # In production, use a validation library like Pydantic or Marshmallow.
        
        if not data.get("name"):
            return bad_request("Name is required")
        
        if not data.get("email"):
            return bad_request("Email is required")
        
        # Additional validation you might add:
        # - Email format validation (regex or email-validator library)
        # - Name length limits
        # - Check for duplicate email
        # - Sanitize input to prevent XSS/SQL injection
        
        # ─────────────────────────────────────────────────────────────────────
        # CREATE USER
        # ─────────────────────────────────────────────────────────────────────
        
        user = {
            "id": next_id,
            "name": data["name"],
            "email": data["email"],
        }
        
        # Add to "database"
        users_db[next_id] = user
        next_id += 1
        
        # ─────────────────────────────────────────────────────────────────────
        # RETURN RESPONSE
        # ─────────────────────────────────────────────────────────────────────
        # created() returns 201 Created with:
        #   - The user object as JSON body
        #   - Location header pointing to the new resource
        
        return created(user, location=f"/api/users/{user['id']}")
    
    
    # ─────────────────────────────────────────────────────────────────────────
    # UPDATE USER
    # ─────────────────────────────────────────────────────────────────────────
    # PUT /api/users/:id
    #
    # PUT requests update existing resources.
    # Convention: PUT replaces the entire resource
    #            PATCH updates only specified fields
    # (This example uses PUT but implements PATCH-like behavior)
    #
    # Example request:
    #   curl -X PUT http://localhost:8080/api/users/1 \
    #        -H "Content-Type: application/json" \
    #        -d '{"name": "Alice Updated"}'
    #
    # Example response:
    #   HTTP/1.1 200 OK
    #   {"id": 1, "name": "Alice Updated", "email": "alice@example.com"}
    
    @server.put("/api/users/:id")
    def update_user(request):
        """
        Update an existing user.
        
        Demonstrates:
          - Combining path params with request body
          - Partial updates (only update provided fields)
        """
        user_id = int(request.path_params["id"])
        
        # Check if user exists FIRST (before parsing body)
        # This gives better error messages and fails fast
        if user_id not in users_db:
            return not_found(f"User {user_id} not found")
        
        # Parse request body
        try:
            data = request.json
        except Exception:
            return bad_request("Invalid JSON body")
        
        # Get the existing user
        user = users_db[user_id]
        
        # Update only the fields that were provided
        # This is "partial update" or "PATCH-like" behavior
        if "name" in data:
            user["name"] = data["name"]
        if "email" in data:
            user["email"] = data["email"]
        
        # Return the updated user
        return ok(user)
    
    
    # ─────────────────────────────────────────────────────────────────────────
    # DELETE USER
    # ─────────────────────────────────────────────────────────────────────────
    # DELETE /api/users/:id
    #
    # Removes a resource. Convention is to return 204 No Content on success.
    #
    # Example request:
    #   curl -X DELETE http://localhost:8080/api/users/1
    #
    # Example response:
    #   HTTP/1.1 204 No Content
    #   (empty body)
    #
    # WHY 204 NO CONTENT?
    #   - The resource is gone, nothing to return
    #   - 200 OK with empty body is also valid
    #   - Some APIs return the deleted resource (200 + body)
    #   - 204 is the most "RESTful" approach
    
    @server.delete("/api/users/:id")
    def delete_user(request):
        """
        Delete a user.
        
        Demonstrates:
          - DELETE method handling
          - 204 No Content response
        """
        user_id = int(request.path_params["id"])
        
        if user_id not in users_db:
            return not_found(f"User {user_id} not found")
        
        # Remove from "database"
        del users_db[user_id]
        
        # Return 204 No Content (success with no body)
        return no_content()
    
    
    # =========================================================================
    # STEP 5: START THE SERVER
    # =========================================================================
    # server.run() is a BLOCKING call. It:
    #   1. Starts the thread pool
    #   2. Binds to the socket
    #   3. Enters the accept loop (waits for connections)
    #   4. Only returns when server is shut down (Ctrl+C)
    #
    # WHAT HAPPENS UNDER THE HOOD:
    #
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ server.run() Internal Steps                                        │
    # ├─────────────────────────────────────────────────────────────────────┤
    # │                                                                     │
    # │  1. ThreadPool.start()                                             │
    # │     └─ Creates 4 worker threads (min_workers)                      │
    # │     └─ Workers wait on task queue                                  │
    # │                                                                     │
    # │  2. socket.socket(AF_INET, SOCK_STREAM)                            │
    # │     └─ Creates TCP socket                                          │
    # │                                                                     │
    # │  3. socket.setsockopt(SO_REUSEADDR, 1)                             │
    # │     └─ Allows restarting server immediately                        │
    # │                                                                     │
    # │  4. socket.bind(("127.0.0.1", 8080))                               │
    # │     └─ Associates socket with address                              │
    # │                                                                     │
    # │  5. socket.listen(128)                                             │
    # │     └─ Marks socket as accepting connections                       │
    # │     └─ 128 = backlog (max queued connections)                      │
    # │                                                                     │
    # │  6. while running:                                                 │
    # │     └─ client_socket, address = socket.accept()  ← BLOCKS HERE    │
    # │     └─ connection = Connection(client_socket)                      │
    # │     └─ thread_pool.submit(handle_connection, connection)           │
    # │                                                                     │
    # │  7. On Ctrl+C (SIGINT):                                            │
    # │     └─ running = False                                             │
    # │     └─ thread_pool.shutdown(wait=True)                             │
    # │     └─ socket.close()                                              │
    # │                                                                     │
    # └─────────────────────────────────────────────────────────────────────┘
    
    print("Starting API server...")
    print()
    print("=" * 60)
    print("TEST COMMANDS:")
    print("=" * 60)
    print()
    print("# List all users")
    print("curl http://localhost:8080/api/users")
    print()
    print("# Get single user")
    print("curl http://localhost:8080/api/users/1")
    print()
    print("# Create new user")
    print("curl -X POST http://localhost:8080/api/users \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"name\":\"Charlie\",\"email\":\"charlie@example.com\"}'")
    print()
    print("# Update user")
    print("curl -X PUT http://localhost:8080/api/users/1 \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"name\":\"Alice Updated\"}'")
    print()
    print("# Delete user")
    print("curl -X DELETE http://localhost:8080/api/users/2")
    print()
    print("# Health check")
    print("curl http://localhost:8080/health")
    print()
    print("=" * 60)
    print()
    
    # This blocks until Ctrl+C
    server.run()


# =============================================================================
# ENTRY POINT
# =============================================================================
# This is the standard Python idiom for making a script both:
#   1. Runnable as a script: python api_server.py
#   2. Importable as a module: from api_server import main

if __name__ == "__main__":
    main()
