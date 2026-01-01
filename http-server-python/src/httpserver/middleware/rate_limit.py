"""
=============================================================================
RATE LIMITING MIDDLEWARE
=============================================================================

Implements rate limiting using the Token Bucket algorithm to protect
the server from abuse and ensure fair usage.

=============================================================================
WHY RATE LIMITING?
=============================================================================

Rate limiting prevents:
- Denial of Service (DoS) attacks
- Abuse from bots/scrapers
- Unfair resource consumption
- API quota enforcement
- Cost control (for paid resources)

Without rate limiting, a single client could overwhelm your server
or consume disproportionate resources.

=============================================================================
TOKEN BUCKET ALGORITHM
=============================================================================

The Token Bucket is one of the most common rate limiting algorithms.
It's used by AWS, Google Cloud, and many other services.

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    TOKEN BUCKET VISUALIZATION                       │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │       TOKENS ADDED                      BUCKET                       │
    │       ─────────────                     ──────                       │
    │                                                                      │
    │         ● ● ●                      ┌──────────┐                     │
    │          ╲│╱                       │ ● ● ●    │ ◄── Current tokens  │
    │           ▼                        │ ● ● ●    │                     │
    │   tokens_per_second                │ ● ●      │                     │
    │   (refill rate)                    │          │                     │
    │                                    └────┬─────┘                     │
    │                                         │                           │
    │                                         ▼                           │
    │                               REQUESTS CONSUME                      │
    │                               ────────────────                      │
    │                                                                      │
    │   Each request takes 1 token.                                       │
    │   If no tokens → REQUEST REJECTED (429)                             │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

    KEY PROPERTIES:
    
    1. Bucket has max capacity (burst_size)
       - Full bucket = can handle burst of requests
       
    2. Tokens added at constant rate (tokens_per_second)
       - Sustained rate = tokens_per_second
       
    3. Each request consumes 1 token
       - No tokens = request rejected
       
    4. Tokens don't accumulate beyond capacity
       - Can't "save up" unlimited tokens

=============================================================================
TOKEN BUCKET VS OTHER ALGORITHMS
=============================================================================

    ┌─────────────────┬───────────────────────────────────────────────────┐
    │ Algorithm       │ Characteristics                                   │
    ├─────────────────┼───────────────────────────────────────────────────┤
    │ TOKEN BUCKET    │ ✓ Allows bursts up to bucket size                │
    │ (used here)     │ ✓ Smooth rate limiting                            │
    │                 │ ✓ Simple to understand and implement              │
    ├─────────────────┼───────────────────────────────────────────────────┤
    │ LEAKY BUCKET    │ ✓ Fixed output rate (no bursts)                  │
    │                 │ ✓ Good for traffic shaping                       │
    │                 │ ✗ Doesn't allow any bursts                       │
    ├─────────────────┼───────────────────────────────────────────────────┤
    │ FIXED WINDOW    │ ✓ Simple to implement                            │
    │                 │ ✗ Allows 2x burst at window boundary             │
    │                 │ Example: 100/min window, 100 at 0:59, 100 at 1:00│
    ├─────────────────┼───────────────────────────────────────────────────┤
    │ SLIDING WINDOW  │ ✓ Smooth rate limiting                           │
    │                 │ ✓ No boundary issues                              │
    │                 │ ✗ More memory (stores timestamps)                │
    └─────────────────┴───────────────────────────────────────────────────┘

=============================================================================
INTERVIEW QUESTIONS ABOUT RATE LIMITING
=============================================================================

Q: "How would you implement rate limiting in a distributed system?"
A: "In distributed systems, you can't use local token buckets.
   Options include:
   1. Redis-based rate limiting (INCR with TTL)
   2. Distributed token bucket with Redis
   3. Rate limiting at load balancer/API gateway
   4. Consistent hashing to route requests to same limiter"

Q: "What's the difference between Token Bucket and Leaky Bucket?"
A: "Token Bucket allows bursts (if bucket is full).
   Leaky Bucket has constant output rate (no bursts).
   Token Bucket is better for user-facing APIs (responsive).
   Leaky Bucket is better for traffic shaping."

Q: "How do you handle rate limiting for authenticated vs anonymous users?"
A: "Use a key_func that returns different keys:
   - Anonymous: IP address (more restrictive)
   - Authenticated: User ID or API key (more generous)
   Different buckets can have different rates."

=============================================================================
"""

import time
import threading
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field

from .base import Middleware, NextHandler
from ..http.request import HTTPRequest
from ..http.response import HTTPResponse, ResponseBuilder, HTTPStatus


@dataclass
class TokenBucket:
    """
    Token Bucket rate limiter.
    
    =========================================================================
    HOW IT WORKS
    =========================================================================
    
    1. Bucket starts full: tokens = max_tokens
    
    2. Each request calls consume():
       - Refill tokens based on time elapsed
       - If tokens >= 1: consume and allow request
       - If tokens < 1: reject request
    
    3. Tokens refill over time:
       tokens += elapsed_seconds * tokens_per_second
       (capped at max_tokens)
    
    =========================================================================
    EXAMPLE
    =========================================================================
    
    Config: max_tokens=10, tokens_per_second=1
    
    t=0:  bucket=10/10  Request → allowed (bucket=9)
    t=0:  bucket=9/10   Request → allowed (bucket=8)
    ...
    t=0:  bucket=1/10   Request → allowed (bucket=0)
    t=0:  bucket=0/10   Request → REJECTED (429)
    
    t=5:  bucket=5/10   (5 seconds passed, 5 tokens added)
          Request → allowed (bucket=4)
    
    =========================================================================
    """
    
    max_tokens: float           # Bucket capacity (burst size)
    tokens_per_second: float    # Refill rate (sustained rate)
    tokens: float = field(default=0.0)           # Current token count
    last_update: float = field(default_factory=time.time)  # Last refill time
    
    def __post_init__(self):
        """Initialize bucket with full tokens."""
        if self.tokens == 0.0:
            self.tokens = self.max_tokens
    
    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens from the bucket.
        
        This is the main method for rate limiting:
        - First, refill based on elapsed time
        - Then, check if enough tokens are available
        - If yes, consume and return True
        - If no, return False (request should be rejected)
        
        Args:
            tokens: Number of tokens to consume (usually 1)
        
        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True  # Request allowed
        
        return False  # Request rejected (429)
    
    def _refill(self):
        """
        Refill tokens based on elapsed time.
        
        This is the key to smooth rate limiting:
        - Calculate time since last refill
        - Add tokens proportional to elapsed time
        - Cap at max_tokens (can't exceed bucket capacity)
        """
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens: elapsed_seconds * tokens_per_second
        self.tokens = min(
            self.max_tokens,  # Cap at bucket capacity
            self.tokens + (elapsed * self.tokens_per_second)
        )
        self.last_update = now
    
    @property
    def available_tokens(self) -> float:
        """Get current token count (after refill)."""
        self._refill()
        return self.tokens
    
    def time_until_available(self, tokens: float = 1.0) -> float:
        """
        Calculate time until tokens will be available.
        
        Used for the Retry-After header in 429 responses.
        
        Args:
            tokens: Number of tokens needed
        
        Returns:
            Seconds until tokens available (0 if already available)
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0  # Already available
        
        # Calculate time to get needed tokens
        needed = tokens - self.tokens
        return needed / self.tokens_per_second


class RateLimitMiddleware(Middleware):
    """
    Rate limiting middleware using Token Bucket algorithm.
    
    =========================================================================
    FEATURES
    =========================================================================
    
    - Per-client rate limiting (by IP, API key, user ID, etc.)
    - Configurable rate and burst size
    - Custom key extraction function
    - Retry-After header on rate limit
    - Rate limit headers (X-RateLimit-*)
    - Automatic cleanup of old buckets (memory management)
    
    =========================================================================
    USAGE EXAMPLES
    =========================================================================
    
    # Basic: 10 req/sec with burst of 20
    pipeline.add(RateLimitMiddleware(
        requests_per_second=10,
        burst_size=20
    ))
    
    # 100 requests per minute
    pipeline.add(RateLimitMiddleware(
        requests_per_second=100/60,  # ~1.67 req/s
        burst_size=10
    ))
    
    # Rate limit by API key instead of IP
    pipeline.add(RateLimitMiddleware(
        key_func=lambda req: req.headers.get("X-API-Key", "anonymous"),
        requests_per_second=10,
        burst_size=20
    ))
    
    =========================================================================
    RESPONSE HEADERS
    =========================================================================
    
    Successful requests include:
        X-RateLimit-Limit: 20       (bucket capacity)
        X-RateLimit-Remaining: 15   (tokens remaining)
    
    Rate limited requests (429) include:
        Retry-After: 5              (seconds until retry allowed)
        X-RateLimit-Limit: 20
        X-RateLimit-Remaining: 0
    
    =========================================================================
    """
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
        key_func: Optional[Callable[[HTTPRequest], str]] = None,
        cleanup_interval: float = 60.0,
        bucket_ttl: float = 300.0,
    ):
        """
        Initialize rate limit middleware.
        
        Args:
            requests_per_second: Sustained request rate allowed.
                                This is the long-term average rate.
            
            burst_size: Maximum burst size (bucket capacity).
                       Allows this many requests in quick succession.
            
            key_func: Function to extract rate limit key from request.
                     Defaults to client IP address.
                     Examples: API key, user ID, session ID.
            
            cleanup_interval: How often to clean up old buckets (seconds).
                            Prevents memory leak from inactive clients.
            
            bucket_ttl: How long to keep inactive buckets (seconds).
                       Buckets not used for this long are removed.
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.key_func = key_func or self._default_key_func
        self.cleanup_interval = cleanup_interval
        self.bucket_ttl = bucket_ttl
        
        # Storage for per-client buckets
        self._buckets: Dict[str, TokenBucket] = {}
        
        # Thread lock for bucket access (thread-safe)
        self._lock = threading.Lock()
        
        # Track last cleanup time
        self._last_cleanup = time.time()
    
    def _default_key_func(self, request: HTTPRequest) -> str:
        """Default key function using client IP address."""
        return request.client_address[0]
    
    def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse:
        """
        Rate limit the request.
        
        Flow:
        1. Extract rate limit key (IP, API key, etc.)
        2. Get or create token bucket for this key
        3. Try to consume a token
        4. If successful: allow request, add rate limit headers
        5. If failed: return 429 Too Many Requests
        """
        # Get rate limit key for this request
        key = self.key_func(request)
        
        # Get or create bucket for this client
        bucket = self._get_bucket(key)
        
        # Try to consume a token
        if bucket.consume():
            # ═══════════════════════════════════════════════════════════════
            # REQUEST ALLOWED
            # ═══════════════════════════════════════════════════════════════
            response = next(request)
            
            # Add rate limit headers for client awareness
            response.headers["X-RateLimit-Limit"] = str(self.burst_size)
            response.headers["X-RateLimit-Remaining"] = str(int(bucket.available_tokens))
            
            return response
        
        # ═══════════════════════════════════════════════════════════════════
        # REQUEST REJECTED - RATE LIMITED
        # ═══════════════════════════════════════════════════════════════════
        
        # Calculate retry time
        retry_after = bucket.time_until_available()
        
        # Return 429 Too Many Requests
        return (ResponseBuilder()
            .status(HTTPStatus.TOO_MANY_REQUESTS)
            .header("Retry-After", str(int(retry_after) + 1))
            .header("X-RateLimit-Limit", str(self.burst_size))
            .header("X-RateLimit-Remaining", "0")
            .json({
                "error": "Too Many Requests",
                "message": f"Rate limit exceeded. Try again in {int(retry_after) + 1} seconds.",
                "retry_after": int(retry_after) + 1,
            })
            .build())
    
    def _get_bucket(self, key: str) -> TokenBucket:
        """
        Get or create a token bucket for a key.
        
        =====================================================================
        BUCKET MANAGEMENT
        =====================================================================
        
        Each unique key (IP, API key, etc.) gets its own bucket.
        This is stored in a dictionary:
        
            _buckets = {
                "192.168.1.1": TokenBucket(tokens=5, ...),
                "192.168.1.2": TokenBucket(tokens=20, ...),
                "api-key-abc": TokenBucket(tokens=0, ...),
            }
        
        THREAD SAFETY:
        We use a lock because multiple threads may access the
        same bucket concurrently.
        
        MEMORY MANAGEMENT:
        We periodically clean up inactive buckets to prevent
        memory leaks from clients that make one request and leave.
        
        =====================================================================
        
        Args:
            key: Rate limit key (e.g., IP address).
        
        Returns:
            Token bucket for the key.
        """
        with self._lock:
            # ═══════════════════════════════════════════════════════════════
            # PERIODIC CLEANUP - Prevent memory leaks
            # ═══════════════════════════════════════════════════════════════
            if time.time() - self._last_cleanup > self.cleanup_interval:
                self._cleanup()
            
            # ═══════════════════════════════════════════════════════════════
            # GET OR CREATE BUCKET
            # ═══════════════════════════════════════════════════════════════
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    max_tokens=self.burst_size,
                    tokens_per_second=self.requests_per_second,
                )
            
            return self._buckets[key]
    
    def _cleanup(self):
        """
        Remove old inactive buckets to prevent memory leaks.
        
        =====================================================================
        WHY CLEANUP IS IMPORTANT
        =====================================================================
        
        Without cleanup, every unique client IP ever seen would
        consume memory forever. For a public-facing server, this
        could lead to millions of buckets.
        
        Example memory calculation:
        - Each TokenBucket: ~100 bytes
        - 1 million unique IPs: ~100 MB
        - 10 million unique IPs: ~1 GB
        
        By removing buckets inactive for bucket_ttl (default 5 min),
        we only keep active clients in memory.
        
        =====================================================================
        """
        now = time.time()
        
        # Find buckets that haven't been used recently
        expired_keys = [
            key for key, bucket in self._buckets.items()
            if now - bucket.last_update > self.bucket_ttl
        ]
        
        # Remove expired buckets
        for key in expired_keys:
            del self._buckets[key]
        
        self._last_cleanup = now
    
    def reset(self, key: Optional[str] = None):
        """
        Reset rate limits.
        
        Useful for:
        - Testing (reset between test cases)
        - Admin intervention (unblock a user)
        - After a user upgrades their plan
        
        Args:
            key: Specific key to reset, or None to reset all.
        """
        with self._lock:
            if key is None:
                self._buckets.clear()
            elif key in self._buckets:
                del self._buckets[key]


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# This module implements production-grade rate limiting:
#
# 1. TokenBucket: The core algorithm
#    - Allows bursts up to bucket size
#    - Refills at constant rate
#    - Simple and efficient
#
# 2. RateLimitMiddleware: Integration with HTTP server
#    - Per-client tracking
#    - Configurable key function
#    - Memory management
#    - Standard rate limit headers
#
# INTERVIEW TIP:
# Rate limiting is a favorite interview topic. Be prepared to discuss:
# - Token Bucket vs Leaky Bucket vs Sliding Window
# - Distributed rate limiting (Redis, API Gateway)
# - Rate limit by different dimensions (IP, user, endpoint)
# - The 429 status code and Retry-After header
# =============================================================================
