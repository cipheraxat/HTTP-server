"""
=============================================================================
SERVER CONFIGURATION
=============================================================================

Centralized configuration management for the HTTP server.

=============================================================================
WHY A CONFIG CLASS?
=============================================================================

Configuration should be:
1. Centralized - One place to see all options
2. Typed - IDE autocomplete and error detection
3. Validated - Catch errors early
4. Configurable - From code, environment, or files

Using a dataclass provides all of these benefits automatically!

=============================================================================
CONFIGURATION SOURCES
=============================================================================

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    CONFIGURATION HIERARCHY                          │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   Priority (highest to lowest):                                     │
    │                                                                      │
    │   1. Command-line arguments                                         │
    │      └── python -m httpserver --port 3000                          │
    │                                                                      │
    │   2. Environment variables                                          │
    │      └── HTTP_PORT=3000 python -m httpserver                       │
    │                                                                      │
    │   3. Configuration files                                            │
    │      └── config.yaml, .env                                         │
    │                                                                      │
    │   4. Default values (in this dataclass)                            │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
12-FACTOR APP CONFIGURATION
=============================================================================

This follows the 12-factor app methodology:
https://12factor.net/config

"Store config in the environment"

Benefits:
- Same code runs in dev, staging, production
- No secrets in source code
- Easy to change without rebuilding

=============================================================================
INTERVIEW QUESTIONS ABOUT CONFIGURATION
=============================================================================

Q: "How do you handle secrets in configuration?"
A: "Never store secrets in code or config files committed to git.
   Use environment variables, secrets managers (AWS Secrets Manager,
   HashiCorp Vault), or Kubernetes secrets. In development,
   use a .env file that's gitignored."

Q: "How do you validate configuration?"
A: "Validate eagerly at startup, not lazily at first use.
   Fail fast with clear error messages. This prevents runtime
   errors hours into a production deployment."

=============================================================================
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServerConfig:
    """
    Configuration for the HTTP server.
    
    =========================================================================
    CONFIGURATION GROUPS
    =========================================================================
    
    NETWORK SETTINGS
    - host, port, backlog, buffer_size, timeout
    
    HTTP SETTINGS
    - keep_alive, keep_alive_timeout, max_request_size
    
    THREADING SETTINGS
    - min_workers, max_workers
    
    STATIC FILES
    - static_dir, static_url_prefix
    
    LOGGING
    - log_level, log_format
    
    =========================================================================
    PRODUCTION VS DEVELOPMENT
    =========================================================================
    
    Development:
        ServerConfig(
            host="127.0.0.1",    # Localhost only
            port=8080,           # High port (no sudo)
            log_level="DEBUG",   # Verbose logging
        )
    
    Production:
        ServerConfig(
            host="0.0.0.0",      # All interfaces
            port=80,             # Standard HTTP port
            log_level="INFO",    # Less noise
            max_workers=32,      # More threads
        )
    
    =========================================================================
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # NETWORK SETTINGS
    # ─────────────────────────────────────────────────────────────────────
    
    host: str = "127.0.0.1"
    """
    The IP address to bind to.
    - "127.0.0.1" - Localhost only (development)
    - "0.0.0.0" - All network interfaces (production)
    """
    
    port: int = 8080
    """
    The port number to listen on.
    - 80 - Standard HTTP (requires root on Unix)
    - 443 - Standard HTTPS (requires root on Unix)
    - 8080 - Common development port
    - 3000 - Popular for Node.js apps
    """
    
    backlog: int = 128
    """
    Maximum number of queued connections.
    When the accept queue is full, new connections are refused.
    Higher = more connections can wait during burst.
    """
    
    buffer_size: int = 8192
    """
    Size of the receive buffer in bytes (8 KB default).
    Larger = faster for big requests, more memory per connection.
    """
    
    timeout: Optional[float] = 30.0
    """
    Socket timeout in seconds.
    None = blocking (infinite wait, dangerous in production!)
    30.0 = reasonable default for web requests
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # HTTP SETTINGS
    # ─────────────────────────────────────────────────────────────────────
    
    keep_alive: bool = True
    """
    Enable HTTP keep-alive connections.
    Allows multiple requests on same TCP connection.
    Reduces latency and TCP handshake overhead.
    """
    
    keep_alive_timeout: float = 5.0
    """
    Timeout for keep-alive connections in seconds.
    After this idle time, connection is closed.
    Prevents resource exhaustion from idle connections.
    """
    
    max_request_size: int = 10 * 1024 * 1024  # 10 MB
    """
    Maximum allowed request body size in bytes.
    Protects against DoS attacks with huge request bodies.
    For file upload APIs, increase this value.
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # THREAD POOL SETTINGS
    # ─────────────────────────────────────────────────────────────────────
    
    min_workers: int = 4
    """
    Minimum number of worker threads.
    These threads are created at startup.
    """
    
    max_workers: int = 16
    """
    Maximum number of worker threads.
    More threads = more concurrent requests, but more memory.
    Rule of thumb: num_cores * 2 for I/O-bound workloads.
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # STATIC FILES
    # ─────────────────────────────────────────────────────────────────────
    
    static_dir: Optional[str] = None
    """
    Directory for serving static files.
    If set, static file handler is automatically configured.
    """
    
    static_url_prefix: str = "/static"
    """
    URL prefix for static files.
    Requests starting with this prefix are served from static_dir.
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # LOGGING
    # ─────────────────────────────────────────────────────────────────────
    
    log_level: str = "INFO"
    """
    Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    DEBUG - Verbose, for development
    INFO - Normal, for production
    WARNING - Only problems
    """
    
    log_format: str = "text"
    """
    Log format: 'json' or 'text'.
    JSON is better for log aggregators (ELK, Datadog).
    Text is better for human reading.
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # SERVER IDENTITY
    # ─────────────────────────────────────────────────────────────────────
    
    server_name: str = "PyHTTPServer/1.0"
    """
    Server name for the Server header.
    Some hide this for security (obscurity).
    """
    
    @classmethod
    def from_env(cls) -> "ServerConfig":
        """
        Create configuration from environment variables.
        
        =====================================================================
        ENVIRONMENT VARIABLES
        =====================================================================
        
        HTTP_HOST       Server host (default: 127.0.0.1)
        HTTP_PORT       Server port (default: 8080)
        HTTP_WORKERS    Max worker threads (default: 16)
        HTTP_TIMEOUT    Request timeout in seconds (default: 30)
        HTTP_STATIC_DIR Static files directory (default: None)
        HTTP_LOG_LEVEL  Logging level (default: INFO)
        
        =====================================================================
        USAGE
        =====================================================================
        
        # From shell:
        HTTP_PORT=3000 HTTP_LOG_LEVEL=DEBUG python -m httpserver
        
        # In code:
        config = ServerConfig.from_env()
        server = HTTPServer(config)
        
        =====================================================================
        """
        return cls(
            host=os.getenv("HTTP_HOST", "127.0.0.1"),
            port=int(os.getenv("HTTP_PORT", "8080")),
            max_workers=int(os.getenv("HTTP_WORKERS", "16")),
            timeout=float(os.getenv("HTTP_TIMEOUT", "30")),
            static_dir=os.getenv("HTTP_STATIC_DIR"),
            log_level=os.getenv("HTTP_LOG_LEVEL", "INFO"),
        )
    
    def validate(self) -> None:
        """
        Validate configuration values.
        
        =====================================================================
        FAIL-FAST PRINCIPLE
        =====================================================================
        
        We validate configuration at startup, not at first use.
        This ensures errors are caught immediately, not hours into
        a production deployment.
        
        =====================================================================
        """
        if not 0 < self.port < 65536:
            raise ValueError(f"Invalid port: {self.port}. Must be 1-65535.")
        
        if self.min_workers < 1:
            raise ValueError(f"min_workers must be >= 1")
        
        if self.max_workers < self.min_workers:
            raise ValueError(f"max_workers must be >= min_workers")
        
        if self.buffer_size < 1024:
            raise ValueError(f"buffer_size must be >= 1024")
        
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError(f"timeout must be > 0")


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# This module provides centralized configuration management:
#
# 1. Type-safe configuration with dataclass
# 2. Environment variable support for 12-factor apps
# 3. Validation at startup (fail-fast)
# 4. Sensible defaults for development
#
# PRODUCTION CHECKLIST:
# □ Use environment variables for secrets
# □ Set appropriate timeout values
# □ Configure workers for your hardware
# □ Use INFO or WARNING log level
# □ Bind to 0.0.0.0 (not 127.0.0.1) for containers
# =============================================================================
