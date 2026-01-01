"""
=============================================================================
HTTP SERVER CLI ENTRY POINT
=============================================================================

This module provides the command-line interface for running the HTTP server.

=============================================================================
USAGE
=============================================================================

    # Run with defaults (localhost:8080)
    python -m httpserver
    
    # Custom port
    python -m httpserver --port 3000
    
    # Listen on all interfaces (for containers)
    python -m httpserver --host 0.0.0.0
    
    # With more worker threads
    python -m httpserver --workers 8
    
    # Serve static files
    python -m httpserver --static ./public
    
    # Enable CORS
    python -m httpserver --cors

=============================================================================
WHY __main__.py?
=============================================================================

Python looks for __main__.py when running a package as a module:

    python -m httpserver
                ▲
                │
                └── Looks for httpserver/__main__.py

This is the standard way to make a package executable.
It's used by pip, pytest, flask, django, and most Python tools.

=============================================================================
12-FACTOR APP: ENTRY POINT
=============================================================================

A 12-factor app has a single entry point that:

1. Reads configuration from environment/CLI
2. Constructs the application
3. Runs the application

This module follows that pattern:
1. argparse reads CLI arguments
2. ServerConfig + HTTPServer are constructed
3. server.run() starts the server

=============================================================================
"""

import argparse
import sys
import os

from .server import HTTPServer
from .config import ServerConfig
from .http.response import ok, ResponseBuilder
from .middleware import LoggingMiddleware, CORSMiddleware
from .handlers import HealthHandler


def main():
    """
    Main CLI entry point.
    
    =========================================================================
    ARGUMENT PARSING
    =========================================================================
    
    We use argparse for command-line argument parsing:
    - --host, -H: Server host
    - --port, -p: Server port  
    - --workers, -w: Number of worker threads
    - --static, -s: Static files directory
    - --log-level, -l: Logging verbosity
    - --cors: Enable CORS
    - --version, -v: Show version
    
    =========================================================================
    """
    parser = argparse.ArgumentParser(
        description="Production-grade HTTP server built from scratch in Python",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m httpserver                      # Run with defaults
  python -m httpserver --port 3000          # Custom port
  python -m httpserver --host 0.0.0.0       # Listen on all interfaces
  python -m httpserver --workers 8          # 8 worker threads
  python -m httpserver --static ./public    # Serve static files
  python -m httpserver --cors               # Enable CORS
        """
    )
    
    # ─────────────────────────────────────────────────────────────────────
    # NETWORK ARGUMENTS
    # ─────────────────────────────────────────────────────────────────────
    
    parser.add_argument(
        "--host", "-H",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1, use 0.0.0.0 for containers)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)"
    )
    
    # ─────────────────────────────────────────────────────────────────────
    # PERFORMANCE ARGUMENTS
    # ─────────────────────────────────────────────────────────────────────
    
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of worker threads (default: 4, max will be 2x this)"
    )
    
    # ─────────────────────────────────────────────────────────────────────
    # FEATURE ARGUMENTS
    # ─────────────────────────────────────────────────────────────────────
    
    parser.add_argument(
        "--static", "-s",
        type=str,
        default=None,
        help="Directory to serve static files from (e.g., ./public)"
    )
    
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--cors",
        action="store_true",
        help="Enable CORS for all origins (development convenience)"
    )
    
    # ─────────────────────────────────────────────────────────────────────
    # META ARGUMENTS
    # ─────────────────────────────────────────────────────────────────────
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="PyHTTPServer 1.0.0"
    )
    
    args = parser.parse_args()
    
    # =========================================================================
    # CREATE CONFIGURATION
    # =========================================================================
    # Translate CLI arguments to ServerConfig
    
    config = ServerConfig(
        host=args.host,
        port=args.port,
        min_workers=args.workers,
        max_workers=args.workers * 2,  # Scale max workers with min
        static_dir=args.static,
        log_level=args.log_level,
    )
    
    # =========================================================================
    # CREATE SERVER
    # =========================================================================
    
    server = HTTPServer(config)
    
    # =========================================================================
    # ADD MIDDLEWARE
    # =========================================================================
    # Logging is always enabled (it's essential for debugging)
    
    server.use(LoggingMiddleware())
    
    # CORS is optional (for development convenience)
    if args.cors:
        server.use(CORSMiddleware())
    
    # =========================================================================
    # ADD HEALTH CHECK ENDPOINTS
    # =========================================================================
    # These are critical for Kubernetes and load balancer health probes
    
    health = HealthHandler(include_system_info=True)
    server.get("/health")(health.handle)        # Overall health
    server.get("/health/live")(health.liveness)  # Liveness probe
    server.get("/health/ready")(health.readiness)  # Readiness probe
    
    # =========================================================================
    # ADD DEFAULT INDEX PAGE
    # =========================================================================
    # A nice landing page showing server info and available endpoints
    
    @server.get("/")
    def index(request):
        """
        Default landing page.
        
        Shows server features and available endpoints.
        In production, you'd replace this with your actual app.
        """
        return ResponseBuilder().html("""
<!DOCTYPE html>
<html>
<head>
    <title>PyHTTPServer</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            font-size: 1.1em;
            margin-bottom: 30px;
        }
        .features {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 30px 0;
        }
        .feature {
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .feature h3 {
            color: #667eea;
            margin: 0 0 10px 0;
        }
        .feature p {
            color: #666;
            margin: 0;
            font-size: 0.9em;
        }
        code {
            background: #f1f1f1;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .endpoints {
            background: #1e1e1e;
            color: #fff;
            padding: 20px;
            border-radius: 8px;
            font-family: monospace;
        }
        .endpoints a {
            color: #4fc3f7;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 PyHTTPServer</h1>
        <p class="subtitle">A production-grade HTTP/1.1 server built from scratch in Python</p>
        
        <div class="features">
            <div class="feature">
                <h3>⚡ Multi-threaded</h3>
                <p>Thread pool for handling concurrent connections efficiently</p>
            </div>
            <div class="feature">
                <h3>🔌 Middleware</h3>
                <p>Composable middleware pipeline for cross-cutting concerns</p>
            </div>
            <div class="feature">
                <h3>🛣️ Routing</h3>
                <p>Dynamic URL routing with path parameters</p>
            </div>
            <div class="feature">
                <h3>📁 Static Files</h3>
                <p>Serve static files with caching and MIME detection</p>
            </div>
        </div>
        
        <h3>Available Endpoints</h3>
        <div class="endpoints">
            GET <a href="/">/</a> - This page<br>
            GET <a href="/health">/health</a> - Health check<br>
            GET <a href="/health/live">/health/live</a> - Liveness probe<br>
            GET <a href="/health/ready">/health/ready</a> - Readiness probe
        </div>
    </div>
</body>
</html>
        """).build()
    
    # =========================================================================
    # ADD STATIC FILE SERVING
    # =========================================================================
    # Only if --static flag was provided
    
    if args.static and os.path.isdir(args.static):
        from .handlers import StaticFileHandler
        static_handler = StaticFileHandler(args.static)
        server.get("/static/*path")(static_handler.handle)
        print(f"📁 Serving static files from: {args.static}")
    
    # =========================================================================
    # RUN SERVER
    # =========================================================================
    # This blocks until Ctrl+C is pressed
    
    try:
        server.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# ENTRY POINT
# =============================================================================
# This allows running: python -m httpserver
# Python will execute this when the package is run as a module

if __name__ == "__main__":
    main()


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# This module provides the CLI entry point for the HTTP server:
#
# 1. Parse command-line arguments
# 2. Create configuration from arguments
# 3. Build server with middleware and routes
# 4. Run the server (blocking)
#
# EXTENDING THE CLI:
# - Add more arguments to parser
# - Add more middleware based on flags
# - Add more default routes
# - Load routes from a file
# =============================================================================
