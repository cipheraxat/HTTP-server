"""
=============================================================================
HTTP RESPONSE BUILDER
=============================================================================

Builds HTTP/1.1 responses with proper formatting per RFC 7230.

=============================================================================
HTTP RESPONSE ANATOMY
=============================================================================

An HTTP response mirrors the request structure:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     HTTP RESPONSE STRUCTURE                         │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  ┌─ STATUS LINE ──────────────────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    HTTP/1.1 200 OK\r\n                                         │ │
    │  │    ────┬─── ─┬─ ─┬─                                            │ │
    │  │        │     │   │                                              │ │
    │  │    Version  Code Phrase                                        │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    │  ┌─ HEADERS ──────────────────────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    Content-Type: application/json\r\n                          │ │
    │  │    Content-Length: 27\r\n                                      │ │
    │  │    Date: Wed, 01 Jan 2026 12:00:00 GMT\r\n                     │ │
    │  │    Server: PyHTTPServer/1.0\r\n                                │ │
    │  │    Cache-Control: max-age=3600\r\n                             │ │
    │  │    Access-Control-Allow-Origin: *\r\n                          │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    │  ┌─ EMPTY LINE (separator) ───────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    \r\n                                                         │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    │  ┌─ BODY ─────────────────────────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    {"message": "Hello World"}                                   │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
HTTP STATUS CODE CATEGORIES
=============================================================================

    ┌───────────┬──────────────────────────────────────────────────────────┐
    │   Range   │  Meaning                                                 │
    ├───────────┼──────────────────────────────────────────────────────────┤
    │  1xx      │  Informational - Request received, continuing           │
    │  2xx      │  Success - Request accepted and processed               │
    │  3xx      │  Redirection - Further action needed                    │
    │  4xx      │  Client Error - Bad request or unauthorized             │
    │  5xx      │  Server Error - Server failed to process                │
    └───────────┴──────────────────────────────────────────────────────────┘

    COMMON STATUS CODES:
    
    200 OK                 - Request succeeded
    201 Created            - Resource created (POST)
    204 No Content         - Success, no body (DELETE)
    301 Moved Permanently  - Resource moved forever
    302 Found              - Resource moved temporarily
    304 Not Modified       - Cached version is current
    400 Bad Request        - Malformed request syntax
    401 Unauthorized       - Authentication required
    403 Forbidden          - Permission denied
    404 Not Found          - Resource doesn't exist
    405 Method Not Allowed - Wrong HTTP method
    429 Too Many Requests  - Rate limited
    500 Internal Server Error - Server failed
    502 Bad Gateway        - Upstream server error
    503 Service Unavailable - Server overloaded

=============================================================================
BUILDER PATTERN
=============================================================================

This module uses the BUILDER PATTERN for constructing responses:

    Traditional approach (telescoping constructors):
        HTTPResponse(200, "application/json", body, {"X-Custom": "value"}, ...)
        # Hard to read, easy to get argument order wrong
    
    Builder approach (fluent interface):
        ResponseBuilder()
            .status(HTTPStatus.OK)
            .json({"message": "Hello"})
            .header("X-Custom", "value")
            .cache(max_age=3600)
            .build()
        # Self-documenting, order-independent, chainable

    Why use Builder pattern?
    - Readable: Each method clearly states its purpose
    - Flexible: Add only the settings you need
    - Chainable: Fluent API with method chaining
    - Safe: build() creates immutable final object

=============================================================================
INTERVIEW QUESTIONS ABOUT HTTP RESPONSES
=============================================================================

Q: "What headers are required in an HTTP response?"
A: "Technically only the status line is required. But in practice:
   - Content-Length (so client knows when body ends)
   - Content-Type (so client knows how to interpret body)
   - Date (RFC 7231 recommends servers include this)
   Connection headers for keep-alive behavior."

Q: "How does the client know when the response body ends?"
A: "Two methods:
   1. Content-Length header specifies exact byte count
   2. Transfer-Encoding: chunked - body sent in chunks with size prefixes
   Our server uses Content-Length for simplicity."

Q: "What's the difference between 401 and 403?"
A: "401 Unauthorized means 'I don't know who you are, please authenticate.'
   403 Forbidden means 'I know who you are, but you don't have permission.'"

=============================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
import json

from .status_codes import HTTPStatus
from .mime_types import get_content_type


@dataclass
class HTTPResponse:
    """
    Represents an HTTP response to be sent to the client.
    
    This is a simple data container that holds the response components.
    Use ResponseBuilder for a more convenient way to construct responses.
    
    =========================================================================
    RESPONSE LIFECYCLE
    =========================================================================
    
        Handler returns          to_bytes()              Socket sends
        HTTPResponse    ─────►   serializes    ─────►    raw bytes
            │                       │                        │
            │                       │                        │
        HTTPResponse(            b"HTTP/1.1 200 OK\r\n   socket.sendall(
          status=200,              Content-Type: ...\r\n     response_bytes
          headers={...},           \r\n                    )
          body=b"..."              {\"data\": ...}"
        )
    
    =========================================================================
    """
    
    status: HTTPStatus = HTTPStatus.OK       # HTTP status code (enum)
    headers: Dict[str, str] = field(default_factory=dict)  # Response headers
    body: bytes = b""                        # Response body
    version: str = "HTTP/1.1"                # HTTP version
    
    @property
    def status_line(self) -> str:
        """
        Get the HTTP status line.
        
        Format: HTTP-VERSION SP STATUS-CODE SP REASON-PHRASE
        Example: "HTTP/1.1 200 OK"
        
        The reason phrase is human-readable and technically optional
        in HTTP/1.1, but included for compatibility.
        """
        return f"{self.version} {self.status} {self.status.phrase}"
    
    def set_header(self, name: str, value: str) -> "HTTPResponse":
        """
        Set a response header.
        
        Returns self for method chaining:
            response.set_header("X-Custom", "value").set_header("X-Other", "val")
        
        Args:
            name: Header name (case-sensitive in responses)
            value: Header value
        
        Returns:
            Self for method chaining
        """
        self.headers[name] = value
        return self
    
    def set_content_type(self, content_type: str) -> "HTTPResponse":
        """Set the Content-Type header."""
        return self.set_header("Content-Type", content_type)
    
    def set_body(self, body: Union[str, bytes]) -> "HTTPResponse":
        """
        Set the response body.
        
        Automatically encodes strings to UTF-8 bytes.
        
        Args:
            body: Response body (string or bytes)
        
        Returns:
            Self for method chaining
        """
        if isinstance(body, str):
            self.body = body.encode("utf-8")
        else:
            self.body = body
        return self
    
    def to_bytes(self, server_name: str = "PyHTTPServer/1.0") -> bytes:
        """
        Serialize the response to bytes for sending over socket.
        
        =====================================================================
        SERIALIZATION FORMAT
        =====================================================================
        
            HTTP/1.1 200 OK\r\n          ← Status line
            Content-Type: application/json\r\n
            Content-Length: 27\r\n       ← Auto-calculated
            Date: Wed, 01 Jan 2026 ...\r\n  ← Auto-added
            Server: PyHTTPServer/1.0\r\n ← Auto-added
            \r\n                         ← Empty line (separator)
            {"message": "Hello"}         ← Body bytes
        
        =====================================================================
        
        Args:
            server_name: Server identifier for Server header.
        
        Returns:
            Complete HTTP response as bytes ready for socket.sendall()
        """
        # Copy headers to avoid modifying original
        response_headers = dict(self.headers)
        
        # =====================================================================
        # AUTO-ADD REQUIRED HEADERS
        # =====================================================================
        
        # Content-Length: Required so client knows when body ends
        # Without this, client doesn't know if there's more data coming
        if "Content-Length" not in response_headers:
            response_headers["Content-Length"] = str(len(self.body))
        
        # Date: RFC 7231 requires origin servers to send this
        # Format: Day, DD Mon YYYY HH:MM:SS GMT
        if "Date" not in response_headers:
            response_headers["Date"] = format_http_date(datetime.now(timezone.utc))
        
        # Server: Identifies server software (optional but standard)
        if "Server" not in response_headers:
            response_headers["Server"] = server_name
        
        # =====================================================================
        # BUILD RESPONSE STRING
        # =====================================================================
        lines = [self.status_line]  # First line is status
        
        # Add all headers
        for name, value in response_headers.items():
            lines.append(f"{name}: {value}")
        
        # Empty line separates headers from body
        lines.append("")
        
        # Join with CRLF and encode to bytes
        header_bytes = "\r\n".join(lines).encode("utf-8") + b"\r\n"
        
        # Concatenate header bytes and body bytes
        return header_bytes + self.body


class ResponseBuilder:
    """
    Fluent builder for constructing HTTP responses.
    
    ==========================================================================
    THE BUILDER PATTERN
    ==========================================================================
    
    The Builder pattern separates object construction from representation.
    It's especially useful when:
    - Objects have many optional parameters
    - Object construction is complex
    - You want a fluent, readable API
    
    BEFORE (without builder):
        response = HTTPResponse(
            status=HTTPStatus.OK,
            headers={"Content-Type": "application/json", "X-Custom": "value"},
            body=json.dumps(data).encode('utf-8'),
        )
    
    AFTER (with builder):
        response = (ResponseBuilder()
            .status(HTTPStatus.OK)
            .json(data)
            .header("X-Custom", "value")
            .build())
    
    ==========================================================================
    METHOD CHAINING (FLUENT INTERFACE)
    ==========================================================================
    
    Each method returns `self`, enabling chaining:
    
        builder.status(200).header("X-Key", "val").json(data).build()
        ────────┬───────────────────┬─────────────────┬────────────┬───
                │                   │                 │            │
                └───────────────────┴─────────────────┴────────────┘
                         All return 'self' except build()
    
    ==========================================================================
    USAGE EXAMPLES
    ==========================================================================
    
    # Simple JSON response
    response = ResponseBuilder().status(HTTPStatus.OK).json({"message": "Hello"}).build()
    
    # HTML page with caching
    response = (ResponseBuilder()
        .status(HTTPStatus.OK)
        .html("<h1>Welcome</h1>")
        .cache(max_age=3600)
        .build())
    
    # Error response with CORS
    response = (ResponseBuilder()
        .status(HTTPStatus.BAD_REQUEST)
        .json({"error": "Invalid input"})
        .cors(origin="https://example.com")
        .build())
    
    # Redirect
    response = ResponseBuilder().redirect("/new-location", permanent=True).build()
    
    ==========================================================================
    """
    
    def __init__(self, server_name: str = "PyHTTPServer/1.0"):
        """
        Initialize the response builder.
        
        Args:
            server_name: Server identifier for Server header.
                        This appears in responses as "Server: PyHTTPServer/1.0"
        """
        self._status = HTTPStatus.OK           # Default to 200 OK
        self._headers: Dict[str, str] = {}     # Headers to set
        self._body: bytes = b""                # Response body
        self._server_name = server_name        # Server identification
    
    # =========================================================================
    # STATUS METHODS
    # =========================================================================
    
    def status(self, status: HTTPStatus) -> "ResponseBuilder":
        """
        Set the HTTP status code.
        
        Args:
            status: HTTPStatus enum value (e.g., HTTPStatus.OK)
        
        Returns:
            Self for method chaining
        """
        self._status = status
        return self
    
    # =========================================================================
    # HEADER METHODS
    # =========================================================================
    
    def header(self, name: str, value: str) -> "ResponseBuilder":
        """
        Add a single response header.
        
        Args:
            name: Header name (e.g., "X-Request-Id")
            value: Header value
        
        Returns:
            Self for method chaining
        """
        self._headers[name] = value
        return self
    
    def headers(self, headers: Dict[str, str]) -> "ResponseBuilder":
        """
        Add multiple headers at once.
        
        Args:
            headers: Dictionary of header name → value
        
        Returns:
            Self for method chaining
        """
        self._headers.update(headers)
        return self
    
    def content_type(self, content_type: str) -> "ResponseBuilder":
        """
        Set the Content-Type header.
        
        Args:
            content_type: MIME type (e.g., "text/html; charset=utf-8")
        
        Returns:
            Self for method chaining
        """
        return self.header("Content-Type", content_type)
    
    # =========================================================================
    # BODY METHODS
    # =========================================================================
    
    def body(self, body: Union[str, bytes]) -> "ResponseBuilder":
        """
        Set the response body (raw bytes or string).
        
        For structured data, prefer json(), html(), or text() methods.
        
        Args:
            body: Response body (string auto-encoded to UTF-8)
        
        Returns:
            Self for method chaining
        """
        if isinstance(body, str):
            self._body = body.encode("utf-8")
        else:
            self._body = body
        return self
    
    def text(self, text: str, content_type: str = "text/plain; charset=utf-8") -> "ResponseBuilder":
        """
        Set a plain text response body.
        
        Sets Content-Type to text/plain with UTF-8 charset.
        
        Args:
            text: Text content
            content_type: Override Content-Type if needed
        
        Returns:
            Self for method chaining
        """
        self._body = text.encode("utf-8")
        self._headers["Content-Type"] = content_type
        return self
    
    def html(self, html: str) -> "ResponseBuilder":
        """
        Set an HTML response body.
        
        Sets Content-Type to text/html with UTF-8 charset.
        
        Args:
            html: HTML content
        
        Returns:
            Self for method chaining
        """
        self._body = html.encode("utf-8")
        self._headers["Content-Type"] = "text/html; charset=utf-8"
        return self
    
    def json(self, data: Any, pretty: bool = False) -> "ResponseBuilder":
        """
        Set a JSON response body.
        
        Serializes Python data to JSON and sets Content-Type.
        
        Args:
            data: Any JSON-serializable data (dict, list, str, number, etc.)
            pretty: If True, format with indentation for readability
        
        Returns:
            Self for method chaining
        
        Interview insight: We use ensure_ascii=False to properly handle
        Unicode characters (like émojis) without escaping them.
        """
        indent = 2 if pretty else None
        self._body = json.dumps(data, indent=indent, ensure_ascii=False).encode("utf-8")
        self._headers["Content-Type"] = "application/json; charset=utf-8"
        return self
    
    def file(self, content: bytes, filename: str) -> "ResponseBuilder":
        """
        Set a file response body.
        
        Automatically detects Content-Type from filename extension.
        
        Args:
            content: File content as bytes
            filename: Filename for Content-Type detection
        
        Returns:
            Self for method chaining
        """
        self._body = content
        self._headers["Content-Type"] = get_content_type(filename)
        return self
    
    # =========================================================================
    # REDIRECT METHODS
    # =========================================================================
    
    def redirect(
        self,
        location: str,
        permanent: bool = False
    ) -> "ResponseBuilder":
        """
        Create a redirect response.
        
        =====================================================================
        REDIRECT STATUS CODES
        =====================================================================
        
        301 Moved Permanently:
            - Resource has moved forever
            - Browsers/search engines update their links
            - Safe for GET requests
        
        302 Found (temporary redirect):
            - Resource temporarily at different URL
            - Browsers don't update bookmarks
            - Original URL should be used in future
        
        Other redirect codes (not implemented here):
            303 See Other  - Redirect after POST (use GET)
            307 Temporary  - Like 302 but preserves method
            308 Permanent  - Like 301 but preserves method
        
        =====================================================================
        
        Args:
            location: URL to redirect to
            permanent: If True, use 301; otherwise use 302
        
        Returns:
            Self for method chaining
        """
        self._status = HTTPStatus.MOVED_PERMANENTLY if permanent else HTTPStatus.FOUND
        self._headers["Location"] = location
        return self
    
    # =========================================================================
    # CACHING METHODS
    # =========================================================================
    
    def no_cache(self) -> "ResponseBuilder":
        """
        Add headers to prevent caching.
        
        This sets multiple headers for maximum compatibility:
        - Cache-Control: no-store (HTTP/1.1)
        - Pragma: no-cache (HTTP/1.0 fallback)
        - Expires: 0 (force revalidation)
        
        Use for sensitive data or rapidly changing content.
        
        Returns:
            Self for method chaining
        """
        self._headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        self._headers["Pragma"] = "no-cache"  # HTTP/1.0 compatibility
        self._headers["Expires"] = "0"
        return self
    
    def cache(self, max_age: int = 3600) -> "ResponseBuilder":
        """
        Add caching headers.
        
        Args:
            max_age: Cache duration in seconds (default: 1 hour)
        
        Returns:
            Self for method chaining
        
        Cache-Control directives:
        - public: Response can be cached by any cache
        - max-age: How long (in seconds) the response is fresh
        """
        self._headers["Cache-Control"] = f"public, max-age={max_age}"
        return self
    
    # =========================================================================
    # CORS METHODS
    # =========================================================================
    
    def cors(
        self,
        origin: str = "*",
        methods: Optional[list[str]] = None,
        headers: Optional[list[str]] = None,
        max_age: int = 86400
    ) -> "ResponseBuilder":
        """
        Add CORS (Cross-Origin Resource Sharing) headers.
        
        =====================================================================
        CORS EXPLAINED
        =====================================================================
        
        Browsers enforce Same-Origin Policy: JavaScript can only make
        requests to the same origin (protocol + domain + port).
        
        CORS headers allow servers to relax this restriction:
        
            Request from https://frontend.com to https://api.com:
            
            Browser: "Can I make this cross-origin request?"
            
            Server Response Headers:
              Access-Control-Allow-Origin: https://frontend.com
              Access-Control-Allow-Methods: GET, POST
              Access-Control-Allow-Headers: Content-Type
            
            Browser: "OK, server allows it. Proceed."
        
        =====================================================================
        
        Args:
            origin: Allowed origin ("*" for any, or specific URL)
            methods: Allowed HTTP methods (for preflight)
            headers: Allowed request headers (for preflight)
            max_age: How long browser can cache preflight response
        
        Returns:
            Self for method chaining
        """
        self._headers["Access-Control-Allow-Origin"] = origin
        
        if methods:
            self._headers["Access-Control-Allow-Methods"] = ", ".join(methods)
        
        if headers:
            self._headers["Access-Control-Allow-Headers"] = ", ".join(headers)
        
        self._headers["Access-Control-Max-Age"] = str(max_age)
        return self
    
    # =========================================================================
    # CONNECTION METHODS
    # =========================================================================
    
    def keep_alive(self, timeout: int = 5, max_requests: int = 100) -> "ResponseBuilder":
        """
        Set keep-alive connection headers.
        
        Tells client to reuse this connection for future requests.
        
        Args:
            timeout: Seconds to keep connection alive while idle
            max_requests: Maximum requests before closing connection
        
        Returns:
            Self for method chaining
        """
        self._headers["Connection"] = "keep-alive"
        self._headers["Keep-Alive"] = f"timeout={timeout}, max={max_requests}"
        return self
    
    def close_connection(self) -> "ResponseBuilder":
        """
        Set Connection: close header.
        
        Tells client to close connection after this response.
        Use when you want to force a fresh connection.
        
        Returns:
            Self for method chaining
        """
        self._headers["Connection"] = "close"
        return self
    
    # =========================================================================
    # BUILD METHODS
    # =========================================================================
    
    def build(self) -> HTTPResponse:
        """
        Build and return the HTTPResponse object.
        
        This is the terminal method that constructs the final response.
        Call this when you're done configuring the response.
        
        Returns:
            Constructed HTTPResponse object
        """
        return HTTPResponse(
            status=self._status,
            headers=self._headers,
            body=self._body,
        )
    
    def to_bytes(self) -> bytes:
        """
        Build and serialize the response to bytes in one step.
        
        Convenience method that combines build() and to_bytes().
        
        Returns:
            Complete HTTP response as bytes
        """
        return self.build().to_bytes(self._server_name)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_http_date(dt: datetime) -> str:
    """
    Format a datetime as an HTTP-date (RFC 7231).
    
    HTTP-date uses a specific format for the Date header and other
    date-related headers (Last-Modified, Expires, etc.).
    
    Format: Day, DD Mon YYYY HH:MM:SS GMT
    Example: Wed, 01 Jan 2026 12:00:00 GMT
    
    Important: HTTP dates are ALWAYS in GMT (UTC), never local time.
    
    Args:
        dt: Datetime to format (should be UTC).
    
    Returns:
        Formatted date string.
    """
    # Weekday names (0=Monday in Python's datetime)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Month names (1-indexed, so we subtract 1)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    return (
        f"{days[dt.weekday()]}, "
        f"{dt.day:02d} {months[dt.month - 1]} {dt.year} "
        f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} GMT"
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================
#
# These functions provide quick one-liners for common response patterns.
# Use them for simple responses; use ResponseBuilder for complex ones.
#
# Examples:
#     return ok({"message": "Success"})
#     return not_found("User not found")
#     return redirect("/login")
#
# =============================================================================

def ok(body: Union[str, bytes, dict, list] = "", content_type: Optional[str] = None) -> HTTPResponse:
    """
    Create a 200 OK response.
    
    The most common success response. Automatically handles different
    body types:
    - dict/list → JSON response
    - str → text response
    - bytes → raw response
    
    Args:
        body: Response body (auto-detected type)
        content_type: Override Content-Type if needed
    
    Returns:
        HTTPResponse with 200 status
    """
    builder = ResponseBuilder().status(HTTPStatus.OK)
    
    if isinstance(body, (dict, list)):
        builder.json(body)
    elif isinstance(body, str):
        builder.text(body, content_type or "text/plain; charset=utf-8")
    else:
        builder.body(body)
        if content_type:
            builder.content_type(content_type)
    
    return builder.build()


def created(body: Union[str, bytes, dict, list] = "", location: Optional[str] = None) -> HTTPResponse:
    """
    Create a 201 Created response.
    
    Used after successfully creating a new resource (POST requests).
    Often includes a Location header pointing to the new resource.
    
    Args:
        body: Response body (usually the created resource)
        location: URL of the created resource
    
    Returns:
        HTTPResponse with 201 status
    """
    builder = ResponseBuilder().status(HTTPStatus.CREATED)
    
    if isinstance(body, (dict, list)):
        builder.json(body)
    elif body:
        builder.body(body if isinstance(body, bytes) else body.encode())
    
    if location:
        builder.header("Location", location)
    
    return builder.build()


def no_content() -> HTTPResponse:
    """
    Create a 204 No Content response.
    
    Used when request succeeded but there's no body to return.
    Common for DELETE requests or updates that don't return data.
    
    Returns:
        HTTPResponse with 204 status and empty body
    """
    return ResponseBuilder().status(HTTPStatus.NO_CONTENT).build()


def redirect(location: str, permanent: bool = False) -> HTTPResponse:
    """
    Create a redirect response (301 or 302).
    
    Args:
        location: URL to redirect to
        permanent: True for 301 (permanent), False for 302 (temporary)
    
    Returns:
        HTTPResponse with redirect status and Location header
    """
    return ResponseBuilder().redirect(location, permanent).build()


def bad_request(message: str = "Bad Request") -> HTTPResponse:
    """
    Create a 400 Bad Request response.
    
    Used when the client sent a malformed or invalid request.
    Examples: missing required fields, invalid JSON, bad query params.
    
    Args:
        message: Error description for the client
    
    Returns:
        HTTPResponse with 400 status
    """
    return ResponseBuilder().status(HTTPStatus.BAD_REQUEST).json({"error": message}).build()


def unauthorized(message: str = "Unauthorized") -> HTTPResponse:
    """
    Create a 401 Unauthorized response.
    
    Used when authentication is required but not provided or invalid.
    Includes WWW-Authenticate header to indicate auth method.
    
    Note: Despite the name, 401 means "not authenticated" (identity unknown).
    For "authenticated but not permitted", use 403 Forbidden.
    
    Args:
        message: Error description
    
    Returns:
        HTTPResponse with 401 status and WWW-Authenticate header
    """
    return (ResponseBuilder()
        .status(HTTPStatus.UNAUTHORIZED)
        .header("WWW-Authenticate", 'Basic realm="Access Required"')
        .json({"error": message})
        .build())


def forbidden(message: str = "Forbidden") -> HTTPResponse:
    """
    Create a 403 Forbidden response.
    
    Used when the client is authenticated but not authorized for this action.
    "I know who you are, but you can't do this."
    
    Args:
        message: Error description
    
    Returns:
        HTTPResponse with 403 status
    """
    return ResponseBuilder().status(HTTPStatus.FORBIDDEN).json({"error": message}).build()


def not_found(message: str = "Not Found") -> HTTPResponse:
    """
    Create a 404 Not Found response.
    
    Used when the requested resource doesn't exist.
    One of the most common error responses.
    
    Args:
        message: Error description
    
    Returns:
        HTTPResponse with 404 status
    """
    return ResponseBuilder().status(HTTPStatus.NOT_FOUND).json({"error": message}).build()


def method_not_allowed(allowed_methods: list[str]) -> HTTPResponse:
    """
    Create a 405 Method Not Allowed response.
    
    Used when the HTTP method is not supported for this resource.
    Example: POST to a read-only endpoint.
    
    Includes Allow header listing valid methods (RFC 7231 requirement).
    
    Args:
        allowed_methods: List of valid methods for this resource
    
    Returns:
        HTTPResponse with 405 status and Allow header
    """
    return (ResponseBuilder()
        .status(HTTPStatus.METHOD_NOT_ALLOWED)
        .header("Allow", ", ".join(allowed_methods))
        .json({"error": "Method Not Allowed", "allowed": allowed_methods})
        .build())


def internal_error(message: str = "Internal Server Error") -> HTTPResponse:
    """
    Create a 500 Internal Server Error response.
    
    Used when the server encountered an unexpected error.
    In production, don't expose internal details in the message.
    
    Args:
        message: Error description (keep generic in production!)
    
    Returns:
        HTTPResponse with 500 status
    """
    return ResponseBuilder().status(HTTPStatus.INTERNAL_SERVER_ERROR).json({"error": message}).build()
