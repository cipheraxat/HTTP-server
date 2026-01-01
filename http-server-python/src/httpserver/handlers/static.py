"""
=============================================================================
STATIC FILE HANDLER
=============================================================================

Serves static files from the filesystem with security and caching.

=============================================================================
WHAT ARE STATIC FILES?
=============================================================================

Static files are unchanging resources served directly from disk:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    STATIC VS DYNAMIC CONTENT                        │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   STATIC FILES                    DYNAMIC CONTENT                   │
    │   ────────────                    ───────────────                   │
    │                                                                      │
    │   • HTML pages                    • API responses                   │
    │   • CSS stylesheets               • Search results                  │
    │   • JavaScript files              • User-specific data              │
    │   • Images (PNG, JPEG, SVG)       • Database queries                │
    │   • Fonts (WOFF, TTF)             • Rendered templates              │
    │   • Downloads (PDF, ZIP)          • Real-time data                  │
    │                                                                      │
    │   Same for everyone               Different per request             │
    │   Can be cached aggressively      Limited caching                   │
    │   Served from disk                Generated at runtime              │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
SECURITY: PATH TRAVERSAL ATTACK
=============================================================================

Path traversal is an attack where a malicious user tries to access
files outside the intended directory:

    ATTACK ATTEMPT:
    ┌─────────────────────────────────────────────────────────────────────┐
    │  GET /static/../../../etc/passwd HTTP/1.1                          │
    │                                                                      │
    │  If not protected, this could read:                                 │
    │  /var/www/static/../../../etc/passwd                               │
    │  → /etc/passwd  (SECURITY BREACH!)                                 │
    │                                                                      │
    │  Our protection:                                                    │
    │  1. Resolve the full path (follow .. and symlinks)                 │
    │  2. Check if it's still inside root_dir                            │
    │  3. If not, return 403 Forbidden                                   │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

    PYTHON PROTECTION:
    
        full_path = (root_dir / user_input).resolve()
        full_path.relative_to(root_dir)  # Raises if outside root!

=============================================================================
CACHING STATIC FILES
=============================================================================

HTTP caching reduces bandwidth and improves performance:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    HTTP CACHING HEADERS                             │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   CACHE-CONTROL                                                     │
    │   ─────────────                                                     │
    │   Cache-Control: public, max-age=3600                               │
    │                  │       │                                          │
    │                  │       └── Cache for 1 hour                       │
    │                  └── Cacheable by CDN/proxies                       │
    │                                                                      │
    │   ETAG (Entity Tag)                                                 │
    │   ─────────────────                                                 │
    │   ETag: "abc123"         Unique fingerprint of file content         │
    │                                                                      │
    │   Request: If-None-Match: "abc123"                                  │
    │   Response: 304 Not Modified (no body, use cached version)          │
    │                                                                      │
    │   LAST-MODIFIED                                                     │
    │   ─────────────                                                     │
    │   Last-Modified: Wed, 15 Jun 2024 10:00:00 GMT                     │
    │                                                                      │
    │   Request: If-Modified-Since: Wed, 15 Jun 2024 10:00:00 GMT        │
    │   Response: 304 Not Modified (if unchanged)                         │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
MIME TYPES
=============================================================================

MIME type tells the browser how to handle the file:

    Wrong MIME type → Browser may refuse to execute/display
    
    Example:
    - script.js with text/plain → Won't execute as JavaScript
    - image.png with text/html → Won't display as image
    
    We detect MIME type from file extension (see mime_types.py)

=============================================================================
INTERVIEW QUESTIONS ABOUT STATIC FILES
=============================================================================

Q: "How would you serve static files in production?"
A: "In production, I'd use a CDN like CloudFront or Cloudflare.
   The origin server sets Cache-Control headers, and the CDN
   caches files at edge locations worldwide. This reduces latency
   and offloads traffic from the origin."

Q: "What's the difference between ETag and Last-Modified?"
A: "ETag is a content hash (changes when content changes).
   Last-Modified is the file timestamp.
   ETag is more precise - a file could be touched (new timestamp)
   without content changing. ETag catches this case."

Q: "Why is path traversal dangerous?"
A: "An attacker could read sensitive files like /etc/passwd,
   database configs, or private keys. In the worst case,
   they could read source code and find other vulnerabilities."

=============================================================================
"""

import os
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from ..http.request import HTTPRequest
from ..http.response import (
    HTTPResponse, ResponseBuilder, HTTPStatus,
    not_found, forbidden
)
from ..http.mime_types import get_content_type


logger = logging.getLogger(__name__)


class StaticFileHandler:
    """
    Handler for serving static files.
    
    =========================================================================
    FEATURES
    =========================================================================
    
    - Serves files from a configured directory
    - Automatic MIME type detection
    - Directory index (serves index.html)
    - Path traversal protection (security critical!)
    - Cache-Control headers for browser caching
    - ETag support for conditional requests
    - Optional directory listing
    
    =========================================================================
    FLOW
    =========================================================================
    
        Request: GET /static/css/style.css
        
        1. Extract file path from URL
        2. Resolve to filesystem path
        3. Security check: is path within root_dir?
        4. If directory: try index.html or list contents
        5. If file: check ETag, serve content with headers
    
    =========================================================================
    USAGE
    =========================================================================
    
        # Create handler
        static = StaticFileHandler(
            root_dir="/var/www/static",
            url_prefix="/static",
            cache_max_age=86400  # 1 day
        )
        
        # Register route with wildcard
        router.get("/static/*path", static.handle)
    
    =========================================================================
    """
    
    def __init__(
        self,
        root_dir: str,
        url_prefix: str = "/static",
        index_file: str = "index.html",
        cache_max_age: int = 3600,
        enable_directory_listing: bool = False,
    ):
        """
        Initialize static file handler.
        
        Args:
            root_dir: Root directory to serve files from.
                     All files MUST be inside this directory.
            
            url_prefix: URL prefix for static files.
                       Stripped from URL to get file path.
            
            index_file: Default file for directory requests.
                       Usually "index.html".
            
            cache_max_age: Cache-Control max-age in seconds.
                          Default 3600 (1 hour).
            
            enable_directory_listing: Allow listing directory contents.
                                     SECURITY WARNING: May expose structure.
        """
        # Resolve to absolute path (important for security check later)
        self.root_dir = Path(root_dir).resolve()
        self.url_prefix = url_prefix.rstrip("/")
        self.index_file = index_file
        self.cache_max_age = cache_max_age
        self.enable_directory_listing = enable_directory_listing
        
        # Validate root directory exists
        if not self.root_dir.is_dir():
            raise ValueError(f"Static root directory does not exist: {root_dir}")
    
    def handle(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle a static file request.
        
        =====================================================================
        SECURITY
        =====================================================================
        
        This method includes path traversal protection. We:
        1. Resolve the full path (following .. and symlinks)
        2. Check that the resolved path is still inside root_dir
        3. Return 403 Forbidden if the check fails
        
        =====================================================================
        
        Args:
            request: The HTTP request.
        
        Returns:
            HTTP response with file content or error.
        """
        # ─────────────────────────────────────────────────────────────────
        # EXTRACT FILE PATH FROM URL
        # ─────────────────────────────────────────────────────────────────
        # Try path parameters first (from wildcard routes)
        file_path = request.path_params.get("path", "")
        if not file_path:
            # Fall back to stripping URL prefix
            file_path = request.path
            if file_path.startswith(self.url_prefix):
                file_path = file_path[len(self.url_prefix):]
        
        # Clean leading slashes
        file_path = file_path.lstrip("/")
        
        # ─────────────────────────────────────────────────────────────────
        # RESOLVE FULL FILESYSTEM PATH
        # ─────────────────────────────────────────────────────────────────
        # resolve() follows symlinks and normalizes .. components
        full_path = (self.root_dir / file_path).resolve()
        
        # ─────────────────────────────────────────────────────────────────
        # SECURITY: PATH TRAVERSAL CHECK
        # ─────────────────────────────────────────────────────────────────
        # Ensure the resolved path is still inside root_dir
        # This prevents attacks like /static/../../../etc/passwd
        try:
            full_path.relative_to(self.root_dir)
        except ValueError:
            # Path is outside root_dir - this is an attack!
            logger.warning(f"Path traversal attempt: {file_path}")
            return forbidden("Access denied")
        
        # ─────────────────────────────────────────────────────────────────
        # HANDLE DIRECTORY REQUESTS
        # ─────────────────────────────────────────────────────────────────
        if full_path.is_dir():
            # Try to serve index file (e.g., index.html)
            index_path = full_path / self.index_file
            if index_path.is_file():
                full_path = index_path
            elif self.enable_directory_listing:
                return self._directory_listing(full_path, request.path)
            else:
                return forbidden("Directory listing not allowed")
        
        # ─────────────────────────────────────────────────────────────────
        # CHECK FILE EXISTS
        # ─────────────────────────────────────────────────────────────────
        if not full_path.is_file():
            return not_found(f"File not found: {file_path}")
        
        # ─────────────────────────────────────────────────────────────────
        # SERVE THE FILE
        # ─────────────────────────────────────────────────────────────────
        return self._serve_file(full_path, request)
    
    def _serve_file(self, path: Path, request: HTTPRequest) -> HTTPResponse:
        """
        Serve a single file with proper headers.
        
        =====================================================================
        CACHING STRATEGY
        =====================================================================
        
        We implement conditional requests with ETag:
        
        1. Generate ETag from file mtime and size
        2. Check If-None-Match header from client
        3. If ETag matches: return 304 Not Modified (no body)
        4. If different/missing: send full file with ETag
        
        This saves bandwidth when client has cached version.
        
        =====================================================================
        
        Args:
            path: Path to the file.
            request: The HTTP request.
        
        Returns:
            HTTP response with file content.
        """
        try:
            # Get file stats for caching headers
            stat = path.stat()
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            
            # ─────────────────────────────────────────────────────────────
            # GENERATE ETAG
            # ─────────────────────────────────────────────────────────────
            # ETag is a unique identifier for this version of the file
            # We use mtime-size as a simple but effective fingerprint
            etag = f'"{int(stat.st_mtime)}-{size}"'
            
            # ─────────────────────────────────────────────────────────────
            # CHECK CONDITIONAL REQUEST
            # ─────────────────────────────────────────────────────────────
            # If client has cached version with matching ETag,
            # return 304 Not Modified (saves bandwidth!)
            if_none_match = request.headers.get("if-none-match", "")
            if if_none_match == etag:
                return (ResponseBuilder()
                    .status(HTTPStatus.NOT_MODIFIED)
                    .header("ETag", etag)
                    .build())
            
            # ─────────────────────────────────────────────────────────────
            # READ FILE CONTENT
            # ─────────────────────────────────────────────────────────────
            # Note: For large files, consider streaming instead
            content = path.read_bytes()
            
            # ─────────────────────────────────────────────────────────────
            # BUILD RESPONSE WITH CACHING HEADERS
            # ─────────────────────────────────────────────────────────────
            return (ResponseBuilder()
                .status(HTTPStatus.OK)
                .header("Content-Type", get_content_type(path))
                .header("Content-Length", str(size))
                .header("ETag", etag)
                .header("Last-Modified", self._format_http_date(mtime))
                .header("Cache-Control", f"public, max-age={self.cache_max_age}")
                .body(content)
                .build())
            
        except PermissionError:
            return forbidden("Permission denied")
        except Exception as e:
            logger.error(f"Error serving file {path}: {e}")
            return (ResponseBuilder()
                .status(HTTPStatus.INTERNAL_SERVER_ERROR)
                .json({"error": "Failed to read file"})
                .build())
    
    def _directory_listing(self, path: Path, url_path: str) -> HTTPResponse:
        """
        Generate a directory listing page.
        
        =====================================================================
        SECURITY NOTE
        =====================================================================
        
        Directory listing exposes the structure of your files.
        Only enable if you're serving a public file repository.
        
        =====================================================================
        
        Args:
            path: Directory path.
            url_path: URL path for generating links.
        
        Returns:
            HTML response with directory listing.
        """
        entries = []
        
        # Add parent directory link if not at root
        if path != self.root_dir:
            entries.append('<li><a href="../">../</a></li>')
        
        # List directory contents (sorted for consistent ordering)
        for entry in sorted(path.iterdir()):
            name = entry.name
            if entry.is_dir():
                name += "/"  # Trailing slash indicates directory
            entries.append(f'<li><a href="{name}">{name}</a></li>')
        
        # Generate simple HTML page
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Index of {url_path}</title>
    <style>
        body {{ font-family: monospace; padding: 20px; }}
        h1 {{ border-bottom: 1px solid #ccc; padding-bottom: 10px; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ padding: 5px 0; }}
        a {{ text-decoration: none; color: #0066cc; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Index of {url_path}</h1>
    <ul>
        {''.join(entries)}
    </ul>
</body>
</html>
"""
        return ResponseBuilder().html(html).build()
    
    def _format_http_date(self, dt: datetime) -> str:
        """
        Format datetime as HTTP-date (RFC 7231).
        
        HTTP-date format:
        Wed, 15 Jun 2024 10:00:00 GMT
        
        This format is required by HTTP specifications for
        Last-Modified and other date headers.
        """
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        return (
            f"{days[dt.weekday()]}, "
            f"{dt.day:02d} {months[dt.month - 1]} {dt.year} "
            f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} GMT"
        )


def serve_static(root_dir: str, **kwargs) -> "StaticFileHandler":
    """
    Create a static file handler.
    
    Factory function for convenient handler creation.
    
    Args:
        root_dir: Root directory to serve files from.
        **kwargs: Additional arguments for StaticFileHandler.
    
    Returns:
        Configured StaticFileHandler instance.
    
    Example:
        static = serve_static("/var/www/static", cache_max_age=86400)
        router.get("/static/*path", static.handle)
    """
    return StaticFileHandler(root_dir, **kwargs)


# =============================================================================
# MODULE SUMMARY
# =============================================================================
#
# Static file serving is deceptively complex:
#
# 1. Security: Path traversal protection is critical
# 2. Performance: Caching headers reduce bandwidth
# 3. Correctness: MIME types matter for browser behavior
# 4. Features: ETag, directory index, directory listing
#
# PRODUCTION TIPS:
# - Use a CDN for static files (CloudFront, Cloudflare)
# - Set long cache times (86400+) for versioned assets
# - Use fingerprinted filenames (app.abc123.js) for cache busting
# - Disable directory listing in production
# =============================================================================
