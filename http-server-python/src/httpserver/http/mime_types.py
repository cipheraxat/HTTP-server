"""
=============================================================================
MIME TYPE DETECTION
=============================================================================

Maps file extensions to their corresponding MIME types for proper
Content-Type header setting in HTTP responses.

=============================================================================
WHAT IS A MIME TYPE?
=============================================================================

MIME = Multipurpose Internet Mail Extensions

MIME types tell the browser/client how to interpret the response body.
They follow the format: type/subtype

    ┌────────────────────────────────────────────────────────────────────┐
    │                    COMMON MIME TYPES                               │
    ├────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │  TEXT TYPES:                                                       │
    │  ──────────────────────────────────────────────────────────────── │
    │  text/html         → HTML document                                 │
    │  text/css          → CSS stylesheet                                │
    │  text/javascript   → JavaScript code                               │
    │  text/plain        → Plain text                                    │
    │  application/json  → JSON data                                     │
    │  application/xml   → XML document                                  │
    │                                                                     │
    │  IMAGE TYPES:                                                       │
    │  ──────────────────────────────────────────────────────────────── │
    │  image/png         → PNG image                                     │
    │  image/jpeg        → JPEG image                                    │
    │  image/gif         → GIF image                                     │
    │  image/svg+xml     → SVG vector image                              │
    │  image/webp        → WebP image (modern format)                    │
    │                                                                     │
    │  BINARY TYPES:                                                      │
    │  ──────────────────────────────────────────────────────────────── │
    │  application/octet-stream  → Unknown/binary (default)              │
    │  application/pdf           → PDF document                          │
    │  application/zip           → ZIP archive                           │
    │                                                                     │
    └────────────────────────────────────────────────────────────────────┘

=============================================================================
WHY MIME TYPES MATTER
=============================================================================

1. BROWSER RENDERING:
   - text/html → Renders as web page
   - text/plain → Shows as plain text
   - application/pdf → Opens PDF viewer
   
2. SECURITY:
   - Without proper MIME type, browsers may refuse to execute JavaScript
   - CSP (Content-Security-Policy) depends on correct types
   
3. DOWNLOAD BEHAVIOR:
   - application/octet-stream → Forces download
   - Viewable types → Opens in browser

4. CHARSET:
   - Text types can include charset: "text/html; charset=utf-8"
   - Ensures proper character encoding

=============================================================================
INTERVIEW INSIGHT
=============================================================================

Q: "What happens if you serve JavaScript with wrong MIME type?"
A: "Modern browsers will refuse to execute it. If you serve JS as 
   text/plain, the browser won't run it - it's a security feature
   called MIME type checking."

Q: "What's the default MIME type?"
A: "application/octet-stream - meaning 'unknown binary data'.
   Browsers typically download these files rather than display them."

=============================================================================
"""

from pathlib import Path
from typing import Optional


# =============================================================================
# MIME TYPE DATABASE
# =============================================================================
#
# Maps file extensions (lowercase, with dot) to MIME types.
# This covers the most common file types for web serving.
#
# For a comprehensive list, see:
# https://www.iana.org/assignments/media-types/media-types.xhtml
#
# =============================================================================

MIME_TYPES = {
    # -------------------------------------------------------------------------
    # TEXT TYPES
    # -------------------------------------------------------------------------
    # These are human-readable text files
    #
    ".html": "text/html",
    ".htm": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",      # Modern standard (was application/javascript)
    ".mjs": "text/javascript",     # ES modules
    ".json": "application/json",   # application/ because it's data, not human-readable
    ".xml": "application/xml",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    
    # -------------------------------------------------------------------------
    # IMAGE TYPES
    # -------------------------------------------------------------------------
    #
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",       # SVG is XML, hence +xml
    ".ico": "image/x-icon",        # Favicon
    ".webp": "image/webp",         # Modern image format
    ".avif": "image/avif",         # Even more modern image format
    ".bmp": "image/bmp",
    
    # -------------------------------------------------------------------------
    # FONT TYPES
    # -------------------------------------------------------------------------
    #
    ".woff": "font/woff",
    ".woff2": "font/woff2",        # Web font format (compressed)
    ".ttf": "font/ttf",            # TrueType font
    ".otf": "font/otf",            # OpenType font
    ".eot": "application/vnd.ms-fontobject",  # Legacy IE format
    
    # -------------------------------------------------------------------------
    # AUDIO TYPES
    # -------------------------------------------------------------------------
    #
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    
    # -------------------------------------------------------------------------
    # VIDEO TYPES
    # -------------------------------------------------------------------------
    #
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    
    # -------------------------------------------------------------------------
    # DOCUMENT TYPES
    # -------------------------------------------------------------------------
    #
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    
    # -------------------------------------------------------------------------
    # ARCHIVE TYPES
    # -------------------------------------------------------------------------
    #
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed",
    
    # -------------------------------------------------------------------------
    # DATA/OTHER TYPES
    # -------------------------------------------------------------------------
    #
    ".wasm": "application/wasm",   # WebAssembly
    ".map": "application/json",    # Source maps
    
    # -------------------------------------------------------------------------
    # SOURCE CODE TYPES
    # -------------------------------------------------------------------------
    # Served as text for viewing (not execution)
    #
    ".py": "text/x-python",
    ".java": "text/x-java-source",
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".h": "text/x-c",
    ".rs": "text/x-rust",
    ".go": "text/x-go",
    ".rb": "text/x-ruby",
    ".php": "text/x-php",
    ".sh": "text/x-shellscript",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".toml": "text/x-toml",
}

# Default MIME type for unknown extensions
# application/octet-stream = "I don't know what this is, treat as binary"
DEFAULT_MIME_TYPE = "application/octet-stream"


# =============================================================================
# PUBLIC FUNCTIONS
# =============================================================================

def get_mime_type(path: str | Path, default: Optional[str] = None) -> str:
    """
    Get the MIME type for a file based on its extension.
    
    This function extracts the file extension and looks it up in our
    MIME type database.
    
    Args:
        path: File path or name with extension
        default: Default MIME type if extension not found
                 Uses application/octet-stream if not specified
    
    Returns:
        The MIME type string
    
    Examples:
        >>> get_mime_type("style.css")
        'text/css'
        
        >>> get_mime_type("/path/to/image.png")
        'image/png'
        
        >>> get_mime_type("unknown.xyz")
        'application/octet-stream'
        
        >>> get_mime_type("data.xyz", default="text/plain")
        'text/plain'
    """
    if isinstance(path, str):
        path = Path(path)
    
    extension = path.suffix.lower()  # .PNG → .png
    return MIME_TYPES.get(extension, default or DEFAULT_MIME_TYPE)


def is_text_type(mime_type: str) -> bool:
    """
    Check if a MIME type represents text content.
    
    Text content can (and should) be served with a charset parameter
    to specify character encoding.
    
    Args:
        mime_type: The MIME type to check
    
    Returns:
        True if the MIME type is text-based
    
    Examples:
        >>> is_text_type("text/html")
        True
        
        >>> is_text_type("application/json")
        True  # JSON is text even though it's application/
        
        >>> is_text_type("image/png")
        False
    """
    # All text/* types are text
    if mime_type.startswith("text/"):
        return True
    
    # Some application/* types are also text-based
    text_types = {
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-javascript",
        "image/svg+xml",  # SVG is XML text
    }
    
    return mime_type in text_types


def get_content_type(path: str | Path, charset: str = "utf-8") -> str:
    """
    Get the full Content-Type header value for a file.
    
    For text-based content, includes the charset parameter.
    For binary content, just returns the MIME type.
    
    Args:
        path: File path or name with extension
        charset: Character encoding for text files (default: utf-8)
    
    Returns:
        Content-Type header value
    
    Examples:
        >>> get_content_type("page.html")
        'text/html; charset=utf-8'
        
        >>> get_content_type("data.json")
        'application/json; charset=utf-8'
        
        >>> get_content_type("image.png")
        'image/png'
    """
    mime_type = get_mime_type(path)
    
    # Add charset for text types
    if is_text_type(mime_type):
        return f"{mime_type}; charset={charset}"
    
    return mime_type
