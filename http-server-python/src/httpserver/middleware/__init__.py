"""
=============================================================================
MIDDLEWARE FRAMEWORK
=============================================================================

Middleware provides a composable way to process requests and responses.
This is one of the most important patterns in web frameworks.

=============================================================================
WHAT IS MIDDLEWARE?
=============================================================================

Middleware is code that runs BETWEEN receiving a request and calling
the final handler. Think of it like a pipeline of filters:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    MIDDLEWARE PIPELINE                              │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   Incoming Request                                                   │
    │        │                                                             │
    │        ▼                                                             │
    │   ┌─────────────────┐                                               │
    │   │ LoggingMiddleware│ ──► Logs request details                     │
    │   └────────┬────────┘                                               │
    │            ▼                                                         │
    │   ┌─────────────────┐                                               │
    │   │ CORSMiddleware   │ ──► Adds CORS headers                        │
    │   └────────┬────────┘                                               │
    │            ▼                                                         │
    │   ┌─────────────────┐                                               │
    │   │ RateLimitMiddle │ ──► May reject if rate exceeded               │
    │   └────────┬────────┘                                               │
    │            ▼                                                         │
    │   ┌─────────────────┐                                               │
    │   │ CompressionMidd │ ──► Will compress response                    │
    │   └────────┬────────┘                                               │
    │            ▼                                                         │
    │   ┌─────────────────┐                                               │
    │   │   Your Handler   │ ──► Actual business logic                    │
    │   └────────┬────────┘                                               │
    │            │                                                         │
    │            ▼                                                         │
    │   Response flows back UP through middleware                         │
    │   (each can modify the response)                                    │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
WHY USE MIDDLEWARE?
=============================================================================

Middleware implements CROSS-CUTTING CONCERNS - things that affect
multiple handlers but aren't part of the core business logic:

1. LOGGING: Log every request without modifying handlers
2. AUTHENTICATION: Verify tokens before handlers run
3. CORS: Add headers to every response
4. COMPRESSION: Compress all responses
5. RATE LIMITING: Protect all endpoints from abuse
6. ERROR HANDLING: Catch exceptions from any handler
7. CACHING: Add cache headers to responses
8. METRICS: Track timing/counts for monitoring

=============================================================================
AVAILABLE MIDDLEWARE
=============================================================================

LoggingMiddleware:
    Logs every request with timing, status, and optional request IDs.
    Useful for debugging and access logs.

CORSMiddleware:
    Handles CORS (Cross-Origin Resource Sharing) for browser security.
    Automatically responds to preflight OPTIONS requests.

CompressionMiddleware:
    Compresses responses with gzip when clients support it.
    Reduces bandwidth and improves load times.

RateLimitMiddleware:
    Limits request rate per client using Token Bucket algorithm.
    Protects against abuse and ensures fair usage.

=============================================================================
DESIGN PATTERN: CHAIN OF RESPONSIBILITY
=============================================================================

Middleware uses the Chain of Responsibility pattern:
- Each middleware is a "handler" in the chain
- Each can process the request or pass it to the next
- Each can modify the response on the way back

This is a common interview topic for web framework design!

=============================================================================
"""

from .base import Middleware, MiddlewarePipeline
from .logging import LoggingMiddleware
from .cors import CORSMiddleware
from .compression import CompressionMiddleware
from .rate_limit import RateLimitMiddleware

__all__ = [
    # Base classes
    "Middleware",
    "MiddlewarePipeline",
    
    # Built-in middleware
    "LoggingMiddleware",
    "CORSMiddleware",
    "CompressionMiddleware",
    "RateLimitMiddleware",
]
