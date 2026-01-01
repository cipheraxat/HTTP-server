"""
=============================================================================
COMPRESSION MIDDLEWARE
=============================================================================

Automatically compresses response bodies using gzip to reduce bandwidth
and improve page load times.

=============================================================================
WHY COMPRESSION?
=============================================================================

HTTP compression can dramatically reduce transfer size:

    ┌────────────────────────────────────────────────────────────────────┐
    │                  COMPRESSION BENEFITS                              │
    ├────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   Content Type        │ Original │ Compressed │ Savings           │
    │   ────────────────────┼──────────┼────────────┼─────────           │
    │   JSON (API response) │  100 KB  │   15 KB    │  85%              │
    │   HTML page           │   50 KB  │   10 KB    │  80%              │
    │   JavaScript bundle   │  500 KB  │   80 KB    │  84%              │
    │   CSS styles          │   30 KB  │    6 KB    │  80%              │
    │                                                                     │
    │   Text-based content typically compresses 70-90%!                  │
    │                                                                     │
    │   Binary content (images, videos) is already compressed            │
    │   and doesn't benefit from gzip.                                   │
    │                                                                     │
    └────────────────────────────────────────────────────────────────────┘

=============================================================================
HOW GZIP COMPRESSION WORKS
=============================================================================

gzip uses the DEFLATE algorithm (LZ77 + Huffman coding):

1. LZ77 - Find repeated sequences and replace with back-references
   
   Original: "The quick brown fox jumps over the lazy dog"
   Encoded:  "The quick brown fox jumps over" + [back-ref to "the"] + " lazy dog"

2. Huffman coding - Frequent characters use fewer bits
   
   'e' appears often  → encoded as 2-3 bits
   'z' appears rarely → encoded as 8-10 bits

=============================================================================
CONTENT NEGOTIATION
=============================================================================

The browser tells us what encoding it accepts:

    Request:
    ┌───────────────────────────────────────────────────────────────┐
    │ GET /api/data HTTP/1.1                                        │
    │ Host: example.com                                             │
    │ Accept-Encoding: gzip, deflate, br                            │
    │              │      │       │                                 │
    │              │      │       └── Brotli (newer, better)        │
    │              │      └── DEFLATE (older)                       │
    │              └── gzip (most common)                           │
    └───────────────────────────────────────────────────────────────┘

    Response:
    ┌───────────────────────────────────────────────────────────────┐
    │ HTTP/1.1 200 OK                                               │
    │ Content-Type: application/json                                │
    │ Content-Encoding: gzip                                        │
    │ Content-Length: 1234    (compressed size)                     │
    │ Vary: Accept-Encoding   (caching hint)                        │
    │                                                               │
    │ [gzip compressed body]                                        │
    └───────────────────────────────────────────────────────────────┘

=============================================================================
COMPRESSION LEVELS
=============================================================================

    Level 1:  Fastest compression, lowest ratio
    Level 6:  Balanced (default) - good ratio, good speed
    Level 9:  Best compression, slowest

    Rule of thumb:
    - Level 1-3: High-traffic APIs where CPU is bottleneck
    - Level 5-6: Most web servers (balanced)
    - Level 9: Pre-compressed static assets

=============================================================================
INTERVIEW QUESTIONS ABOUT COMPRESSION
=============================================================================

Q: "Why not compress everything?"
A: "Binary content (JPEG, PNG, MP4, ZIP) is already compressed.
   Gzipping them wastes CPU and can even make them larger.
   Also, small responses (<1KB) may not benefit after gzip overhead."

Q: "What's the Vary header for?"
A: "The Vary: Accept-Encoding header tells caches that the response
   varies based on the Accept-Encoding request header. Without it,
   a cache might serve a gzipped response to a client that doesn't
   support gzip."

Q: "How is Brotli different from gzip?"
A: "Brotli (br) is a newer algorithm by Google. It achieves 15-25%
   better compression than gzip for web content. It's supported by
   all modern browsers but has higher CPU cost."

=============================================================================
"""

import gzip
import zlib
from typing import Optional, Set

from .base import Middleware, NextHandler
from ..http.request import HTTPRequest
from ..http.response import HTTPResponse


class CompressionMiddleware(Middleware):
    """
    Response compression middleware.
    
    =========================================================================
    HOW IT WORKS
    =========================================================================
    
    1. Check if client accepts gzip (Accept-Encoding header)
    2. Call the next handler to get the response
    3. Check if response should be compressed:
       - Large enough (exceeds min_size)
       - Compressible content type (text, JSON, etc.)
       - Not already compressed
    4. Compress with gzip
    5. Update headers (Content-Encoding, Content-Length, Vary)
    
    =========================================================================
    MIDDLEWARE POSITION
    =========================================================================
    
    Compression should be LAST in the pipeline:
    
        pipeline.add(LoggingMiddleware())    # Log original size
        pipeline.add(CORSMiddleware())       # Add CORS headers
        pipeline.add(handler)                # Generate response
        pipeline.add(CompressionMiddleware()) # Compress at the end
    
    Why last? We want to compress the final response, including
    any headers added by other middleware.
    
    =========================================================================
    USAGE EXAMPLES
    =========================================================================
    
        # Default: compress responses > 1KB at level 6
        pipeline.add(CompressionMiddleware())
        
        # Aggressive compression for slow networks
        pipeline.add(CompressionMiddleware(
            min_size=256,  # Compress smaller responses
            level=9        # Maximum compression
        ))
        
        # Fast compression for high-traffic APIs
        pipeline.add(CompressionMiddleware(
            min_size=1024,
            level=1  # Fastest
        ))
    
    =========================================================================
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # COMPRESSIBLE CONTENT TYPES
    # ─────────────────────────────────────────────────────────────────────
    # These content types are text-based and compress well.
    # Binary formats (images, video, PDF) are already compressed.
    # ─────────────────────────────────────────────────────────────────────
    COMPRESSIBLE_TYPES: Set[str] = {
        # Text formats
        "text/html",
        "text/css",
        "text/plain",
        "text/xml",
        "text/javascript",
        
        # Application formats (text-based)
        "application/json",
        "application/javascript",
        "application/xml",
        "application/xhtml+xml",
        
        # SVG is XML-based, compresses well
        "image/svg+xml",
    }
    
    def __init__(
        self,
        min_size: int = 1024,
        level: int = 6,
        compressible_types: Optional[Set[str]] = None,
    ):
        """
        Initialize compression middleware.
        
        Args:
            min_size: Minimum response size to compress (bytes).
                     Smaller responses have overhead that may not be worth it.
                     Default 1024 (1KB) is a good balance.
            
            level: Compression level (1-9).
                  1 = fastest, least compression
                  6 = balanced (default)
                  9 = slowest, best compression
            
            compressible_types: Content types to compress.
                               Defaults to text-based types.
                               Don't add binary types (JPEG, PNG, etc.)
        """
        self.min_size = min_size
        self.level = level
        self.compressible_types = compressible_types or self.COMPRESSIBLE_TYPES
    
    def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse:
        """
        Compress the response if appropriate.
        
        Flow:
        1. Check Accept-Encoding header
        2. Get response from next handler
        3. Decide if compression is worthwhile
        4. Compress and update headers
        """
        # ═══════════════════════════════════════════════════════════════════
        # CHECK CLIENT SUPPORT
        # ═══════════════════════════════════════════════════════════════════
        # Only compress if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        accepts_gzip = "gzip" in accept_encoding.lower()
        
        # ═══════════════════════════════════════════════════════════════════
        # GET RESPONSE FROM HANDLER
        # ═══════════════════════════════════════════════════════════════════
        response = next(request)
        
        # ═══════════════════════════════════════════════════════════════════
        # CHECK IF WE SHOULD COMPRESS
        # ═══════════════════════════════════════════════════════════════════
        if not accepts_gzip:
            return response  # Client doesn't support gzip
        
        if not self._should_compress(response):
            return response  # Response shouldn't be compressed
        
        # ═══════════════════════════════════════════════════════════════════
        # COMPRESS THE BODY
        # ═══════════════════════════════════════════════════════════════════
        original_size = len(response.body)
        compressed_body = gzip.compress(response.body, compresslevel=self.level)
        compressed_size = len(compressed_body)
        
        # ═══════════════════════════════════════════════════════════════════
        # ONLY USE IF ACTUALLY SMALLER
        # ═══════════════════════════════════════════════════════════════════
        # gzip has overhead (~18 bytes). For small or already-compressed
        # content, the compressed version might be larger!
        if compressed_size >= original_size:
            return response  # Compression didn't help
        
        # ═══════════════════════════════════════════════════════════════════
        # UPDATE RESPONSE
        # ═══════════════════════════════════════════════════════════════════
        response.body = compressed_body
        
        # Tell client the encoding
        response.headers["Content-Encoding"] = "gzip"
        
        # Update Content-Length to compressed size
        response.headers["Content-Length"] = str(compressed_size)
        
        # ═══════════════════════════════════════════════════════════════════
        # ADD VARY HEADER FOR CACHING
        # ═══════════════════════════════════════════════════════════════════
        # This tells caches that the response varies based on Accept-Encoding
        # Without this, a cache might serve gzipped content to a client
        # that doesn't support gzip!
        vary = response.headers.get("Vary", "")
        if "Accept-Encoding" not in vary:
            response.headers["Vary"] = f"{vary}, Accept-Encoding".lstrip(", ")
        
        return response
    
    def _should_compress(self, response: HTTPResponse) -> bool:
        """
        Check if response should be compressed.
        
        Decision factors:
        1. Not already encoded (Content-Encoding absent)
        2. Exceeds minimum size threshold
        3. Content type is compressible (text-based)
        
        Args:
            response: The HTTP response.
        
        Returns:
            True if response should be compressed.
        """
        # ─────────────────────────────────────────────────────────────────
        # CHECK IF ALREADY ENCODED
        # ─────────────────────────────────────────────────────────────────
        # Don't double-compress!
        if "Content-Encoding" in response.headers:
            return False
        
        # ─────────────────────────────────────────────────────────────────
        # CHECK MINIMUM SIZE
        # ─────────────────────────────────────────────────────────────────
        # Small responses: gzip overhead might not be worth it
        if len(response.body) < self.min_size:
            return False
        
        # ─────────────────────────────────────────────────────────────────
        # CHECK CONTENT TYPE
        # ─────────────────────────────────────────────────────────────────
        # Parse content type, ignoring charset and other params
        # "application/json; charset=utf-8" → "application/json"
        content_type = response.headers.get("Content-Type", "")
        base_type = content_type.split(";")[0].strip().lower()
        
        if base_type not in self.compressible_types:
            return False
        
        return True


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# HTTP compression is a quick win for web performance:
#
# 1. Check Accept-Encoding header from client
# 2. Compress text-based content with gzip
# 3. Set Content-Encoding header in response
# 4. Add Vary header for proper caching
#
# PRODUCTION TIPS:
# - Use level 5-6 for balanced speed/compression
# - Don't compress binary content (already compressed)
# - Consider pre-compressing static assets at build time
# - Monitor CPU usage if compressing high-traffic endpoints
# - Consider Brotli for modern browsers (15-25% better than gzip)
# =============================================================================
