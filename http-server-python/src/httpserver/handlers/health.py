"""
=============================================================================
HEALTH CHECK HANDLER
=============================================================================

Provides health check endpoints for container orchestration and monitoring.

=============================================================================
WHY HEALTH CHECKS?
=============================================================================

Health checks tell external systems whether your application is working:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    HEALTH CHECK ECOSYSTEM                           │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   KUBERNETES                  LOAD BALANCER         MONITORING      │
    │   ───────────                 ─────────────         ──────────      │
    │                                                                      │
    │   ┌─────────┐                 ┌─────────┐          ┌─────────┐     │
    │   │ Pod     │ GET /health     │ HAProxy │          │ Datadog │     │
    │   │ kubelet │ ◀──────────────▶│ checks  │          │ checks  │     │
    │   └─────────┘                 └─────────┘          └─────────┘     │
    │        │                           │                    │           │
    │        ▼                           ▼                    ▼           │
    │   Restart pod               Remove from              Alert         │
    │   if unhealthy              rotation if              on-call       │
    │                             unhealthy                 team          │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
KUBERNETES HEALTH PROBES
=============================================================================

Kubernetes uses three types of probes:

    ┌─────────────────────┬───────────────────────────────────────────────┐
    │ Probe Type          │ Purpose                                       │
    ├─────────────────────┼───────────────────────────────────────────────┤
    │ LIVENESS PROBE      │ "Is the process alive?"                       │
    │ /health/live        │ If fails → Kubernetes RESTARTS the pod       │
    │                     │ Use: detect deadlocks, infinite loops        │
    ├─────────────────────┼───────────────────────────────────────────────┤
    │ READINESS PROBE     │ "Can it handle traffic?"                      │
    │ /health/ready       │ If fails → Remove from load balancer         │
    │                     │ Use: wait for deps, graceful shutdown        │
    ├─────────────────────┼───────────────────────────────────────────────┤
    │ STARTUP PROBE       │ "Has it finished starting?"                   │
    │ /health/live        │ If fails → Don't run other probes yet        │
    │                     │ Use: slow-starting applications              │
    └─────────────────────┴───────────────────────────────────────────────┘

    Kubernetes YAML example:
    
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 10
    
    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5

=============================================================================
HEALTH CHECK PATTERNS
=============================================================================

    SHALLOW CHECK (liveness):
    ├── Return 200 if process is running
    └── Don't check dependencies (fast, simple)
    
    DEEP CHECK (readiness/health):
    ├── Check database connectivity
    ├── Check cache connectivity
    ├── Check external service availability
    └── Return 503 if any critical dependency fails

=============================================================================
INTERVIEW QUESTIONS ABOUT HEALTH CHECKS
=============================================================================

Q: "What's the difference between liveness and readiness?"
A: "Liveness: 'Is the process fundamentally broken?' (restart if failing)
   Readiness: 'Can it serve requests right now?' (stop traffic if failing)
   
   Example: During a database failover, readiness fails (stop traffic)
   but liveness passes (don't restart the app)."

Q: "Why use Cache-Control: no-store on health endpoints?"
A: "Health checks must never be cached. A cached healthy response
   while the server is actually down would be catastrophic.
   Load balancers might send traffic to a dead instance."

Q: "How would you implement graceful shutdown?"
A: "1. Receive SIGTERM
   2. Mark readiness as 'not ready' immediately
   3. Wait for in-flight requests to complete
   4. Close connections and exit"

=============================================================================
"""

import time
import platform
import sys
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field

from ..http.request import HTTPRequest
from ..http.response import HTTPResponse, ResponseBuilder, HTTPStatus


@dataclass
class HealthStatus:
    """
    Health check result.
    
    =========================================================================
    USAGE
    =========================================================================
    
        # Simple check
        def check_database():
            if db.ping():
                return HealthStatus(healthy=True)
            return HealthStatus(healthy=False, message="Connection failed")
        
        # Check with details
        def check_cache():
            latency = cache.ping()
            return HealthStatus(
                healthy=latency < 100,
                message="OK" if latency < 100 else "High latency",
                details={"latency_ms": latency}
            )
    
    =========================================================================
    """
    
    healthy: bool           # True if the check passed
    message: str = "OK"     # Human-readable status message
    details: Dict[str, Any] = field(default_factory=dict)  # Extra info
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            "status": "healthy" if self.healthy else "unhealthy",
            "message": self.message,
            **self.details,
        }


# Type alias for health check functions
HealthCheck = Callable[[], HealthStatus]


class HealthHandler:
    """
    Health check endpoint handler.
    
    =========================================================================
    ENDPOINTS
    =========================================================================
    
    /health         Overall health status with all registered checks
    /health/live    Liveness probe (is the process running?)
    /health/ready   Readiness probe (can it handle requests?)
    
    =========================================================================
    FEATURES
    =========================================================================
    
    - Custom health check functions for your dependencies
    - Uptime tracking
    - Optional system info (hostname, Python version)
    - Kubernetes-compatible responses (200/503)
    - No caching (Cache-Control: no-store)
    
    =========================================================================
    USAGE EXAMPLE
    =========================================================================
    
        # Create handler
        health = HealthHandler(include_system_info=True)
        
        # Add dependency checks
        health.add_check("database", check_database)
        health.add_check("redis", check_redis)
        health.add_check("external_api", check_external_api)
        
        # Register routes
        router.get("/health", health.handle)
        router.get("/health/live", health.liveness)
        router.get("/health/ready", health.readiness)
    
    =========================================================================
    RESPONSE FORMAT
    =========================================================================
    
    Healthy (200 OK):
    {
        "status": "healthy",
        "uptime_seconds": 3600,
        "checks": {
            "database": {"status": "healthy", "message": "OK"},
            "redis": {"status": "healthy", "message": "OK"}
        }
    }
    
    Unhealthy (503 Service Unavailable):
    {
        "status": "unhealthy",
        "uptime_seconds": 3600,
        "checks": {
            "database": {"status": "unhealthy", "error": "Connection refused"},
            "redis": {"status": "healthy", "message": "OK"}
        }
    }
    
    =========================================================================
    """
    
    def __init__(
        self,
        include_details: bool = True,
        include_system_info: bool = False,
    ):
        """
        Initialize health handler.
        
        Args:
            include_details: Include detailed check results in response.
                           Set to False in production if sensitive.
            
            include_system_info: Include system information like hostname.
                               Useful for debugging which pod is responding.
        """
        self.include_details = include_details
        self.include_system_info = include_system_info
        self._checks: Dict[str, HealthCheck] = {}
        self._start_time = time.time()  # For uptime calculation
    
    def add_check(self, name: str, check: HealthCheck) -> "HealthHandler":
        """
        Add a health check.
        
        Checks are run on each /health request. Keep them fast!
        For slow checks, consider caching results.
        
        Args:
            name: Name of the check (e.g., "database", "redis").
            check: Function that returns HealthStatus.
        
        Returns:
            Self for method chaining.
        
        Example:
            health.add_check("database", check_db)
                  .add_check("cache", check_cache)
                  .add_check("queue", check_queue)
        """
        self._checks[name] = check
        return self
    
    def handle(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle health check request.
        
        Runs all registered checks and returns overall health status.
        Returns 200 if ALL checks pass, 503 if ANY check fails.
        
        =====================================================================
        FLOW
        =====================================================================
        
        1. Run all registered health checks
        2. Collect results and determine overall status
        3. Build JSON response with appropriate status code
        4. Add Cache-Control: no-store header
        
        =====================================================================
        """
        results = {}
        all_healthy = True
        
        # ─────────────────────────────────────────────────────────────────
        # RUN ALL HEALTH CHECKS
        # ─────────────────────────────────────────────────────────────────
        for name, check in self._checks.items():
            try:
                status = check()
                results[name] = status.to_dict()
                if not status.healthy:
                    all_healthy = False
            except Exception as e:
                # If a check throws an exception, it's unhealthy
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                all_healthy = False
        
        # ─────────────────────────────────────────────────────────────────
        # BUILD RESPONSE
        # ─────────────────────────────────────────────────────────────────
        response_data: Dict[str, Any] = {
            "status": "healthy" if all_healthy else "unhealthy",
            "uptime_seconds": int(time.time() - self._start_time),
        }
        
        if self.include_details and results:
            response_data["checks"] = results
        
        if self.include_system_info:
            response_data["system"] = {
                "hostname": platform.node(),
                "platform": platform.system(),
                "python_version": sys.version.split()[0],
            }
        
        # ─────────────────────────────────────────────────────────────────
        # RETURN WITH APPROPRIATE STATUS CODE
        # ─────────────────────────────────────────────────────────────────
        # 200 = healthy (keep sending traffic)
        # 503 = unhealthy (stop sending traffic)
        http_status = HTTPStatus.OK if all_healthy else HTTPStatus.SERVICE_UNAVAILABLE
        
        return (ResponseBuilder()
            .status(http_status)
            .json(response_data)
            .header("Cache-Control", "no-store")  # NEVER cache health checks
            .build())
    
    def liveness(self, request: HTTPRequest) -> HTTPResponse:
        """
        Liveness probe endpoint.
        
        =====================================================================
        PURPOSE
        =====================================================================
        
        Answers: "Is the process fundamentally broken?"
        
        If this fails, Kubernetes will RESTART the pod.
        
        Keep this check SIMPLE - just return 200 if the process is running.
        Don't check dependencies here (that's what readiness is for).
        
        =====================================================================
        WHEN LIVENESS SHOULD FAIL
        =====================================================================
        
        - Process is deadlocked
        - Process is in an infinite loop
        - Process is otherwise unrecoverable
        
        =====================================================================
        """
        return (ResponseBuilder()
            .status(HTTPStatus.OK)
            .json({"status": "alive"})
            .header("Cache-Control", "no-store")
            .build())
    
    def readiness(self, request: HTTPRequest) -> HTTPResponse:
        """
        Readiness probe endpoint.
        
        =====================================================================
        PURPOSE
        =====================================================================
        
        Answers: "Can this instance handle traffic right now?"
        
        If this fails, the load balancer will STOP sending traffic
        to this instance (but won't restart it).
        
        =====================================================================
        WHEN READINESS SHOULD FAIL
        =====================================================================
        
        - Database connection is down
        - Critical cache is unavailable
        - Required external service is unreachable
        - Application is starting up
        - Application is shutting down gracefully
        
        =====================================================================
        """
        # Run checks to determine readiness
        for name, check in self._checks.items():
            try:
                status = check()
                if not status.healthy:
                    return (ResponseBuilder()
                        .status(HTTPStatus.SERVICE_UNAVAILABLE)
                        .json({
                            "status": "not ready",
                            "reason": f"Check '{name}' failed: {status.message}",
                        })
                        .header("Cache-Control", "no-store")
                        .build())
            except Exception as e:
                return (ResponseBuilder()
                    .status(HTTPStatus.SERVICE_UNAVAILABLE)
                    .json({
                        "status": "not ready",
                        "reason": f"Check '{name}' error: {str(e)}",
                    })
                    .header("Cache-Control", "no-store")
                    .build())
        
        return (ResponseBuilder()
            .status(HTTPStatus.OK)
            .json({"status": "ready"})
            .header("Cache-Control", "no-store")
            .build())
    
    @property
    def uptime(self) -> float:
        """Get server uptime in seconds."""
        return time.time() - self._start_time


def health_check() -> HealthHandler:
    """
    Create a health check handler.
    
    Factory function for convenient handler creation.
    
    Returns:
        Configured HealthHandler instance.
    
    Example:
        health = health_check()
        health.add_check("db", lambda: HealthStatus(db.is_connected()))
    """
    return HealthHandler()


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# Health checks are critical for production deployments:
#
# 1. Liveness: "Am I running?" (restart if not)
# 2. Readiness: "Can I serve traffic?" (remove from LB if not)
# 3. Custom checks: Database, cache, external services
#
# BEST PRACTICES:
# - Keep liveness checks simple (just return 200)
# - Check critical dependencies in readiness
# - Don't cache health check responses
# - Include uptime for monitoring
# - Log health check failures for debugging
# =============================================================================
