"""
=============================================================================
LOGGING MIDDLEWARE
=============================================================================

Provides structured request logging with timing, correlation IDs, and
configurable output formats.

=============================================================================
WHY REQUEST LOGGING?
=============================================================================

Request logging is essential for:

1. OBSERVABILITY - Understanding what's happening in production
2. DEBUGGING - Tracking down issues with specific requests
3. SECURITY - Auditing who accessed what resources
4. PERFORMANCE - Identifying slow endpoints
5. ANALYTICS - Understanding usage patterns

=============================================================================
LOG FORMATS
=============================================================================

    APACHE COMBINED LOG FORMAT (default):
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 192.168.1.1 - - [10/Jun/2024:10:55:36 +0000] "GET /api" 200 1234 5ms│
    │ ───────────────────────────────────────────────────────────────────│
    │ IP          Timestamp          Method/Path   Status Size Duration  │
    └─────────────────────────────────────────────────────────────────────┘
    
    Human-readable, works with standard log analysis tools
    
    JSON FORMAT (for log aggregators):
    ┌─────────────────────────────────────────────────────────────────────┐
    │ {                                                                   │
    │   "request_id": "a1b2c3d4",                                        │
    │   "method": "GET",                                                  │
    │   "path": "/api/users",                                            │
    │   "client_ip": "192.168.1.1",                                      │
    │   "status_code": 200,                                               │
    │   "duration_ms": 5.23                                               │
    │ }                                                                   │
    └─────────────────────────────────────────────────────────────────────┘
    
    Machine-parseable, ideal for ELK stack, Datadog, Splunk

=============================================================================
REQUEST CORRELATION
=============================================================================

The X-Request-ID header enables distributed tracing:

    ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
    │ Client  │────▶│ Gateway │────▶│Service A│────▶│Service B│
    └─────────┘     └─────────┘     └─────────┘     └─────────┘
         │               │               │               │
         └───────────────┼───────────────┼───────────────┘
                         │               │               │
                    X-Request-ID: a1b2c3d4
                         │               │               │
                    ┌────▼───────────────▼───────────────▼────┐
                    │           LOG AGGREGATOR               │
                    │  [a1b2c3d4] Gateway: received          │
                    │  [a1b2c3d4] Service A: processing     │
                    │  [a1b2c3d4] Service B: database query │
                    └─────────────────────────────────────────┘

All logs for one request can be correlated using the same ID!

=============================================================================
INTERVIEW QUESTIONS ABOUT LOGGING
=============================================================================

Q: "How would you implement distributed tracing?"
A: "Propagate X-Request-ID through all service calls.
   Use structured logging with JSON format.
   Aggregate logs centrally (ELK, Datadog).
   Consider OpenTelemetry for automatic instrumentation."

Q: "What should you NOT log?"
A: "Never log: passwords, API keys, PII (SSN, credit cards),
   session tokens, or any sensitive data. Use allow-lists
   for logged fields, not block-lists."

Q: "How do you handle high-volume logging in production?"
A: "Sample logs (log 1% of requests), async logging,
   log levels (DEBUG/INFO/WARN/ERROR), log rotation,
   structured logging for efficient parsing."

=============================================================================
"""

import time
import json
import uuid
import logging
from typing import Optional
from dataclasses import dataclass

from .base import Middleware, NextHandler
from ..http.request import HTTPRequest
from ..http.response import HTTPResponse


# ═══════════════════════════════════════════════════════════════════════════
# LOGGER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
# We use a namespaced logger for granular control.
# In production, you can configure this logger specifically:
#   logging.getLogger("httpserver.access").setLevel(logging.INFO)
#   logging.getLogger("httpserver.access").addHandler(file_handler)
# ═══════════════════════════════════════════════════════════════════════════
logger = logging.getLogger("httpserver.access")


@dataclass
class RequestLog:
    """
    Structured log entry for a request.
    
    =========================================================================
    STRUCTURED LOGGING
    =========================================================================
    
    Why use a dataclass for logs?
    - Type safety: All fields have defined types
    - Consistency: Every log has the same structure
    - Serialization: Easy to convert to JSON/dict
    - IDE support: Autocomplete and validation
    
    =========================================================================
    FIELDS EXPLAINED
    =========================================================================
    
    request_id:     Unique ID for distributed tracing
    method:         HTTP method (GET, POST, etc.)
    path:           Request path (e.g., /api/users)
    query:          Query string parameters
    client_ip:      Client's IP address
    user_agent:     Browser/client identifier
    status_code:    HTTP response code
    content_length: Response body size in bytes
    duration_ms:    Request processing time
    timestamp:      When the request was processed
    
    =========================================================================
    """
    
    request_id: str
    method: str
    path: str
    query: str
    client_ip: str
    user_agent: str
    status_code: int
    content_length: int
    duration_ms: float
    timestamp: str
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for JSON serialization.
        
        Used by log aggregators that expect JSON format.
        """
        return {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "query": self.query,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "status_code": self.status_code,
            "content_length": self.content_length,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }
    
    def to_text(self) -> str:
        """
        Format as Apache combined log format.
        
        This format is widely supported by log analysis tools:
        - GoAccess
        - AWStats
        - Webalizer
        - Any regex-based log parser
        """
        return (
            f'{self.client_ip} - - [{self.timestamp}] '
            f'"{self.method} {self.path}" {self.status_code} '
            f'{self.content_length} {self.duration_ms:.2f}ms'
        )


class LoggingMiddleware(Middleware):
    """
    Request logging middleware.
    
    =========================================================================
    FEATURES
    =========================================================================
    
    - Request timing (duration in milliseconds)
    - Unique request IDs for correlation (X-Request-ID header)
    - Client IP and User-Agent logging
    - Configurable log level
    - JSON structured logging option
    - Skip logging for health check endpoints
    
    =========================================================================
    MIDDLEWARE POSITION
    =========================================================================
    
    Logging middleware should be FIRST in the pipeline:
    
        pipeline.add(LoggingMiddleware())  # FIRST - sees all requests
        pipeline.add(AuthMiddleware())
        pipeline.add(RateLimitMiddleware())
    
    This ensures:
    1. All requests are logged, even those rejected by other middleware
    2. Timing includes full request processing
    3. Request ID is available to all downstream handlers
    
    =========================================================================
    USAGE
    =========================================================================
    
        # Text format (Apache combined)
        pipeline.add(LoggingMiddleware(log_format="text"))
        
        # JSON format (for ELK, Datadog, etc.)
        pipeline.add(LoggingMiddleware(log_format="json"))
        
        # Skip health checks (they're noisy)
        pipeline.add(LoggingMiddleware(skip_paths=["/health", "/ready"]))
    
    =========================================================================
    """
    
    def __init__(
        self,
        log_format: str = "text",
        include_request_id: bool = True,
        log_level: int = logging.INFO,
        skip_paths: Optional[list[str]] = None,
    ):
        """
        Initialize logging middleware.
        
        Args:
            log_format: Output format ("text" or "json").
                       "text" - Apache combined log format (human readable)
                       "json" - Structured JSON (machine parseable)
            
            include_request_id: Add X-Request-ID header to response.
                               Enables distributed tracing.
            
            log_level: Logging level for access logs.
                      Default is INFO. Use DEBUG for development.
            
            skip_paths: Paths to skip logging (e.g., ["/health"]).
                       Health check endpoints can be very noisy.
        """
        self.log_format = log_format
        self.include_request_id = include_request_id
        self.log_level = log_level
        self.skip_paths = set(skip_paths or [])
    
    def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse:
        """
        Log the request and response.
        
        Flow:
        1. Generate unique request ID
        2. Start timing
        3. Call next handler
        4. Calculate duration
        5. Build and emit log entry
        6. Add X-Request-ID to response
        """
        # ═══════════════════════════════════════════════════════════════════
        # GENERATE REQUEST ID
        # ═══════════════════════════════════════════════════════════════════
        # UUIDv4 is random - good for avoiding collisions
        # We truncate to 8 chars for readability (still 4 billion combos)
        request_id = str(uuid.uuid4())[:8]
        
        # ═══════════════════════════════════════════════════════════════════
        # START TIMING
        # ═══════════════════════════════════════════════════════════════════
        # time.time() returns seconds as float
        # We'll convert to milliseconds later
        start_time = time.time()
        
        # ═══════════════════════════════════════════════════════════════════
        # CALL NEXT HANDLER (the actual request processing)
        # ═══════════════════════════════════════════════════════════════════
        try:
            response = next(request)
        except Exception as e:
            # Log error and re-raise
            # We still want to log failed requests
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.path} "
                f"- {type(e).__name__}: {e} ({duration_ms:.2f}ms)"
            )
            raise
        
        # ═══════════════════════════════════════════════════════════════════
        # CALCULATE DURATION
        # ═══════════════════════════════════════════════════════════════════
        duration_ms = (time.time() - start_time) * 1000  # Convert to ms
        
        # ═══════════════════════════════════════════════════════════════════
        # SKIP LOGGING FOR NOISY ENDPOINTS
        # ═══════════════════════════════════════════════════════════════════
        # Health checks every 10 seconds = 8640 logs/day per probe!
        if request.path in self.skip_paths:
            return response
        
        # ═══════════════════════════════════════════════════════════════════
        # BUILD STRUCTURED LOG ENTRY
        # ═══════════════════════════════════════════════════════════════════
        log_entry = RequestLog(
            request_id=request_id,
            method=request.method,
            path=request.path,
            query=str(request.query_params) if request.query_params else "",
            client_ip=request.client_address[0],
            user_agent=request.user_agent or "-",
            status_code=response.status,
            content_length=len(response.body),
            duration_ms=duration_ms,
            timestamp=time.strftime("%d/%b/%Y:%H:%M:%S %z"),
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # EMIT LOG
        # ═══════════════════════════════════════════════════════════════════
        if self.log_format == "json":
            logger.log(self.log_level, json.dumps(log_entry.to_dict()))
        else:
            logger.log(self.log_level, log_entry.to_text())
        
        # ═══════════════════════════════════════════════════════════════════
        # ADD REQUEST ID TO RESPONSE
        # ═══════════════════════════════════════════════════════════════════
        # This allows clients to report issues with a specific request ID
        if self.include_request_id:
            response.headers["X-Request-ID"] = request_id
        
        return response


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# This module implements production-grade request logging:
#
# 1. Timing: Measure how long each request takes
# 2. Correlation: X-Request-ID for distributed tracing
# 3. Structured: Both human and machine readable formats
# 4. Configurable: Skip paths, log levels, formats
#
# PRODUCTION TIPS:
# - Use JSON format with log aggregators (ELK, Datadog, Splunk)
# - Skip health check endpoints to reduce noise
# - Set appropriate log levels (INFO in prod, DEBUG in dev)
# - Consider async logging for high-throughput services
# =============================================================================
