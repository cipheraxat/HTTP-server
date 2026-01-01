"""
=============================================================================
HTTP REQUEST PARSER
=============================================================================

Parses raw HTTP/1.1 request bytes into structured HTTPRequest objects.
Implements RFC 7230 (HTTP/1.1 Message Syntax and Routing).

=============================================================================
HTTP REQUEST ANATOMY
=============================================================================

An HTTP request is a text-based message with a specific structure:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     HTTP REQUEST STRUCTURE                          │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  ┌─ REQUEST LINE ─────────────────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    GET /api/users?page=1&limit=10 HTTP/1.1\r\n                 │ │
    │  │    ─┬─ ────────────┬──────────────  ────┬────                  │ │
    │  │     │              │                    │                       │ │
    │  │   Method          URI                 Version                   │ │
    │  │                    │                                            │ │
    │  │         ┌──────────┴──────────┐                                │ │
    │  │         │                     │                                 │ │
    │  │       Path           Query String                              │ │
    │  │    /api/users      page=1&limit=10                             │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    │  ┌─ HEADERS ──────────────────────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    Host: example.com\r\n                                       │ │
    │  │    User-Agent: Mozilla/5.0\r\n                                 │ │
    │  │    Accept: application/json\r\n                                │ │
    │  │    Content-Type: application/json\r\n                          │ │
    │  │    Content-Length: 42\r\n                                      │ │
    │  │    Authorization: Bearer eyJhbG...\r\n                         │ │
    │  │    Cookie: session=abc123\r\n                                  │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    │  ┌─ EMPTY LINE (separator) ───────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    \r\n                                                         │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    │  ┌─ BODY (optional) ──────────────────────────────────────────────┐ │
    │  │                                                                 │ │
    │  │    {"username": "alice", "email": "alice@example.com"}         │ │
    │  │                                                                 │ │
    │  └─────────────────────────────────────────────────────────────────┘ │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
HTTP METHODS EXPLAINED
=============================================================================

    ┌──────────┬────────────┬────────────┬──────────────────────────────────┐
    │  Method  │ Idempotent │  Has Body  │ Description                      │
    ├──────────┼────────────┼────────────┼──────────────────────────────────┤
    │  GET     │    Yes     │    No      │ Retrieve resource                │
    │  POST    │    No      │    Yes     │ Create resource / submit data    │
    │  PUT     │    Yes     │    Yes     │ Replace entire resource          │
    │  PATCH   │    No      │    Yes     │ Partial update                   │
    │  DELETE  │    Yes     │  Optional  │ Delete resource                  │
    │  HEAD    │    Yes     │    No      │ GET without body (metadata only) │
    │  OPTIONS │    Yes     │    No      │ Get allowed methods (CORS)       │
    └──────────┴────────────┴────────────┴──────────────────────────────────┘

    IDEMPOTENT: Calling it multiple times has the same effect as once
    
    Why this matters in interviews:
    - POST creates, PUT replaces, PATCH updates
    - GET should never modify state (browser can prefetch!)
    - Idempotent methods can be safely retried on failure

=============================================================================
PARSING CHALLENGES
=============================================================================

1. LINE ENDINGS: HTTP uses CRLF (\r\n), not just LF (\n)
   - Must handle both for compatibility
   - Headers end with \r\n\r\n

2. CASE SENSITIVITY:
   - Methods are UPPERCASE (case-sensitive)
   - Header names are case-INSENSITIVE ("Content-Type" = "content-type")
   - Header values are case-sensitive (mostly)

3. BODY DETECTION:
   - Body length determined by Content-Length header
   - Transfer-Encoding: chunked (not implemented here)
   - No body = Content-Length: 0 or missing

4. SECURITY CONCERNS:
   - Path traversal: "../../../etc/passwd"
   - Request smuggling: conflicting Content-Length values
   - Header injection: CRLF in header values

=============================================================================
INTERVIEW QUESTIONS ABOUT HTTP PARSING
=============================================================================

Q: "How do you know when the HTTP headers end?"
A: "Headers end with an empty line (\r\n\r\n). We scan for this
   delimiter, then split the request into header section and body."

Q: "How do you handle very large requests?"
A: "We set a max_request_size limit and reject requests that exceed it
   with a 413 Payload Too Large response. This prevents memory exhaustion."

Q: "What's the difference between path and URI?"
A: "The URI includes the query string (GET /path?query HTTP/1.1).
   The path is just /path. We parse and separate them."

Q: "How do you handle malformed requests?"
A: "We raise HTTPParseError with an appropriate status code:
   400 for bad syntax, 405 for invalid method, 505 for bad version."

=============================================================================
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from urllib.parse import parse_qs, urlparse, unquote
import re
import json


class HTTPParseError(Exception):
    """
    Raised when HTTP request parsing fails.
    
    This exception carries an HTTP status code that should be returned
    to the client. Different parse errors map to different codes:
    
        400 Bad Request     - Malformed request syntax
        405 Method Not Allowed - Unknown/unsupported method  
        413 Payload Too Large - Request exceeds size limit
        505 HTTP Version Not Supported - Unknown HTTP version
    
    Interview insight: Custom exceptions with metadata (like status_code)
    make error handling cleaner than passing tuples or using generic exceptions.
    """
    
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code  # HTTP status to return


@dataclass
class HTTPRequest:
    """
    Represents a parsed HTTP request.
    
    This dataclass holds all parsed components of an HTTP request,
    providing convenient access methods and computed properties.
    
    =========================================================================
    REQUEST LIFECYCLE
    =========================================================================
    
        Raw bytes                  HTTPRequest                 Handler
        from socket    ──parse──►   dataclass    ──route──►    function
           │                            │                          │
           │                            │                          │
        b"GET /..."              HTTPRequest(                def get_users(
                                   method="GET",               request):
                                   path="/users",               ...
                                   headers={...},
                                   ...)
    
    =========================================================================
    ATTRIBUTES EXPLAINED
    =========================================================================
    
        method:         The HTTP method (GET, POST, PUT, DELETE, etc.)
                        Used by router to match handler
        
        path:           Request path WITHOUT query string
                        "/api/users" not "/api/users?page=1"
        
        version:        HTTP version string ("HTTP/1.1" or "HTTP/1.0")
                        Affects keep-alive behavior
        
        headers:        Dictionary of headers with LOWERCASE keys
                        {"content-type": "application/json", ...}
        
        query_params:   Parsed query string as dict of lists
                        "?a=1&a=2&b=3" → {"a": ["1", "2"], "b": ["3"]}
        
        body:           Raw request body as bytes
                        For POST/PUT requests with Content-Length > 0
        
        path_params:    URL parameters extracted by router
                        Route "/users/:id" with "/users/123" → {"id": "123"}
        
        client_address: Tuple of (ip, port) identifying the client
                        Useful for logging and rate limiting
        
        raw:            The original unparsed request bytes
                        Useful for debugging and proxying
    
    =========================================================================
    INTERVIEW INSIGHT
    =========================================================================
    
    Why use a dataclass?
    - Automatic __init__, __repr__, __eq__ generation
    - Type hints are enforced by IDE/linters
    - Immutable-friendly (can use frozen=True)
    - Less boilerplate than regular class
    
    Why store headers as lowercase keys?
    - HTTP headers are case-insensitive per RFC 7230
    - Normalizing at parse time avoids .lower() everywhere
    - "Content-Type" and "content-type" are the same header
    
    =========================================================================
    """
    
    # Core request line components
    method: str                          # GET, POST, PUT, DELETE, etc.
    path: str                            # Request path without query string
    version: str = "HTTP/1.1"            # HTTP version
    
    # Parsed components
    headers: Dict[str, str] = field(default_factory=dict)           # Header name → value
    query_params: Dict[str, list[str]] = field(default_factory=dict)  # Query param → values
    body: bytes = b""                    # Raw body bytes
    
    # Router-injected parameters
    path_params: Dict[str, str] = field(default_factory=dict)  # :param values
    
    # Metadata
    client_address: tuple[str, int] = ("", 0)  # (IP, port) of client
    raw: bytes = b""                     # Original raw request bytes
    
    # Private cached values (computed lazily)
    _body_json: Optional[Any] = field(default=None, repr=False)
    _content_type: Optional[str] = field(default=None, repr=False)
    
    # =========================================================================
    # PROPERTIES - Computed values accessed like attributes
    # =========================================================================
    
    @property
    def content_type(self) -> Optional[str]:
        """
        Get the Content-Type header value (without parameters).
        
        Content-Type often includes charset: "application/json; charset=utf-8"
        This property strips parameters and returns just "application/json".
        
        Uses lazy caching - computed once on first access.
        """
        if self._content_type is None:
            ct = self.headers.get("content-type", "")
            # Strip parameters like ; charset=utf-8
            self._content_type = ct.split(";")[0].strip().lower()
        return self._content_type or None
    
    @property
    def content_length(self) -> int:
        """
        Get the Content-Length header value as integer.
        
        Returns 0 if header is missing or invalid.
        Used to read exactly the right number of body bytes.
        """
        try:
            return int(self.headers.get("content-length", 0))
        except ValueError:
            return 0
    
    @property
    def host(self) -> str:
        """
        Get the Host header value.
        
        Required in HTTP/1.1 requests. Identifies the target
        host when multiple domains are served from one IP
        (virtual hosting).
        """
        return self.headers.get("host", "")
    
    @property
    def user_agent(self) -> str:
        """
        Get the User-Agent header value.
        
        Identifies the client software making the request.
        Useful for analytics and browser-specific handling.
        """
        return self.headers.get("user-agent", "")
    
    @property
    def is_json(self) -> bool:
        """Check if the request body is JSON based on Content-Type."""
        return self.content_type == "application/json"
    
    @property
    def json(self) -> Any:
        """
        Parse the request body as JSON.
        
        Lazy evaluation with caching - only parses once.
        
        Returns:
            Parsed JSON data (dict, list, str, number, etc.)
        
        Raises:
            HTTPParseError: If body is not valid JSON.
        
        Interview insight: This is the "lazy property" pattern -
        expensive computation is deferred until first access and cached.
        """
        if self._body_json is None and self.body:
            try:
                self._body_json = json.loads(self.body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise HTTPParseError(f"Invalid JSON body: {e}")
        return self._body_json
    
    @property
    def is_keep_alive(self) -> bool:
        """
        Check if this connection should be kept alive.
        
        =====================================================================
        KEEP-ALIVE LOGIC
        =====================================================================
        
        HTTP/1.1 (default: keep-alive):
            Connection: close     → close after response
            (missing)             → keep alive
        
        HTTP/1.0 (default: close):
            Connection: keep-alive → keep alive
            (missing)              → close after response
        
        Why this matters:
        - Keep-alive reuses TCP connection for multiple requests
        - Avoids TCP handshake overhead (3 round trips!)
        - Browser limits parallel connections per host (usually 6)
        =====================================================================
        """
        connection = self.headers.get("connection", "").lower()
        
        if self.version == "HTTP/1.1":
            # HTTP/1.1 keeps alive unless explicitly closed
            return connection != "close"
        else:
            # HTTP/1.0 closes unless explicitly kept alive
            return connection == "keep-alive"
    
    # =========================================================================
    # ACCESSOR METHODS - Convenient ways to get parsed data
    # =========================================================================
    
    def get_header(self, name: str, default: str = "") -> str:
        """
        Get a header value (case-insensitive lookup).
        
        Args:
            name: Header name (any case)
            default: Value to return if header not found
        
        Returns:
            Header value or default
        
        Example:
            content_type = request.get_header("Content-Type")
            # Works because headers are stored lowercase
        """
        return self.headers.get(name.lower(), default)
    
    def get_query(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get the first value of a query parameter.
        
        Args:
            name: Parameter name
            default: Value if parameter not found
        
        Returns:
            First value or default
        
        Example:
            # URL: /users?page=1&page=2
            request.get_query("page")  # Returns "1"
        """
        values = self.query_params.get(name, [])
        return values[0] if values else default
    
    def get_query_list(self, name: str) -> list[str]:
        """
        Get all values of a query parameter.
        
        Args:
            name: Parameter name
        
        Returns:
            List of all values (empty list if not found)
        
        Example:
            # URL: /users?id=1&id=2&id=3
            request.get_query_list("id")  # Returns ["1", "2", "3"]
        """
        return self.query_params.get(name, [])


class RequestParser:
    """
    Parses raw HTTP request bytes into HTTPRequest objects.
    
    ==========================================================================
    PARSER ARCHITECTURE
    ==========================================================================
    
        Raw Request Bytes
              │
              ▼
        ┌───────────────────────────────────────────────────────────────────┐
        │  REQUEST PARSER                                                   │
        ├───────────────────────────────────────────────────────────────────┤
        │                                                                    │
        │  1. Size Check ──────────────────────────────────────────────────►│
        │     │  Too large? → HTTPParseError(413)                          │
        │     ▼                                                             │
        │  2. Find Header/Body Separator (\r\n\r\n) ──────────────────────►│
        │     │  Not found? → HTTPParseError("Incomplete")                 │
        │     ▼                                                             │
        │  3. Parse Request Line ─────────────────────────────────────────►│
        │     │  METHOD SP PATH SP VERSION                                  │
        │     │  Invalid? → HTTPParseError(400/405/505)                    │
        │     ▼                                                             │
        │  4. Parse Headers ──────────────────────────────────────────────►│
        │     │  "Name: Value" pairs, normalized to lowercase              │
        │     ▼                                                             │
        │  5. Extract Body ───────────────────────────────────────────────►│
        │     │  Based on Content-Length header                            │
        │     ▼                                                             │
        │  6. Build HTTPRequest Object ───────────────────────────────────►│
        │                                                                    │
        └───────────────────────────────────────────────────────────────────┘
              │
              ▼
        HTTPRequest dataclass
    
    ==========================================================================
    REGEX PATTERNS EXPLAINED
    ==========================================================================
    
    REQUEST_LINE_PATTERN: ^([A-Z]+) ([^ ]+) (HTTP/\d\.\d)$
    
        ^           - Start of string
        ([A-Z]+)    - Capture group 1: METHOD (uppercase letters)
        ` `         - Single space (SP in RFC)
        ([^ ]+)     - Capture group 2: URI (anything except space)
        ` `         - Single space
        (HTTP/\d\.\d) - Capture group 3: Version (HTTP/X.Y)
        $           - End of string
    
    HEADER_PATTERN: ^([^:]+):\s*(.*)$
    
        ^           - Start of string  
        ([^:]+)     - Capture group 1: Name (anything except colon)
        :           - Literal colon separator
        \s*         - Optional whitespace (OWS in RFC)
        (.*)        - Capture group 2: Value (rest of line)
        $           - End of string
    
    ==========================================================================
    SECURITY CONSIDERATIONS
    ==========================================================================
    
    1. SIZE LIMITS - Prevent memory exhaustion:
       - max_request_size limits total request size
       - Rejects with 413 Payload Too Large
    
    2. PATH TRAVERSAL - Prevent file system access:
       - Reject paths containing ".."
       - "../../../etc/passwd" → 400 Bad Request
    
    3. REQUEST SMUGGLING - Prevent bypass attacks:
       - Trust only Content-Length for body size
       - Don't allow conflicting length indicators
    
    ==========================================================================
    """
    
    # =========================================================================
    # VALID HTTP METHODS
    # =========================================================================
    # 
    # These are the standard HTTP methods defined in RFC 7231.
    # We reject requests with other methods as 405 Method Not Allowed.
    #
    VALID_METHODS = {
        "GET",      # Retrieve resource
        "POST",     # Create resource / submit data  
        "PUT",      # Replace resource
        "DELETE",   # Delete resource
        "PATCH",    # Partial update
        "HEAD",     # GET without body
        "OPTIONS",  # Get allowed methods (CORS preflight)
        "TRACE",    # Echo request (debugging)
        "CONNECT",  # Establish tunnel (HTTPS proxy)
    }
    
    # =========================================================================
    # COMPILED REGEX PATTERNS
    # =========================================================================
    #
    # Compiled once at class load time for efficiency.
    # Much faster than re.match(pattern, string) each time.
    #
    REQUEST_LINE_PATTERN = re.compile(r"^([A-Z]+) ([^ ]+) (HTTP/\d\.\d)$")
    HEADER_PATTERN = re.compile(r"^([^:]+):\s*(.*)$")
    
    def __init__(self, max_request_size: int = 10 * 1024 * 1024):
        """
        Initialize the request parser.
        
        Args:
            max_request_size: Maximum allowed request size in bytes.
                              Default is 10 MB. Larger requests will
                              be rejected with 413 Payload Too Large.
        
        Interview insight: This is a classic security/usability tradeoff.
        Too small = can't upload files. Too large = memory exhaustion attack.
        """
        self.max_request_size = max_request_size
    
    def parse(
        self,
        data: bytes,
        client_address: tuple[str, int] = ("", 0)
    ) -> HTTPRequest:
        """
        Parse raw HTTP request data into an HTTPRequest object.
        
        =====================================================================
        PARSING ALGORITHM
        =====================================================================
        
        1. Check size limit (security)
        2. Find \r\n\r\n separator between headers and body
        3. Decode header section as UTF-8
        4. Split into lines and parse request line (first line)
        5. Parse remaining lines as headers
        6. Extract body based on Content-Length
        7. Construct and return HTTPRequest
        
        =====================================================================
        
        Args:
            data: Raw HTTP request bytes from socket.
            client_address: Client's (ip, port) tuple for logging.
        
        Returns:
            Parsed HTTPRequest object.
        
        Raises:
            HTTPParseError: If the request is malformed.
        """
        # =====================================================================
        # STEP 1: Security check - reject oversized requests
        # =====================================================================
        # =====================================================================
        # STEP 1: Security check - reject oversized requests
        # =====================================================================
        if len(data) > self.max_request_size:
            raise HTTPParseError(
                f"Request too large: {len(data)} bytes",
                status_code=413  # 413 Payload Too Large
            )
        
        # =====================================================================
        # STEP 2: Split headers and body at the \r\n\r\n boundary
        # =====================================================================
        # HTTP messages use a blank line to separate headers from body.
        # This is always \r\n\r\n (CRLF CRLF).
        #
        # Example:
        #   GET /path HTTP/1.1\r\n
        #   Host: example.com\r\n
        #   \r\n                    <-- Header/body separator
        #   {"data": "body"}        <-- Body starts here
        #
        try:
            header_end = data.find(b"\r\n\r\n")
            if header_end == -1:
                # No separator found - incomplete request
                raise HTTPParseError("Incomplete request: no header terminator")
            
            # Decode header section as text (HTTP/1.1 uses ASCII/UTF-8)
            header_section = data[:header_end].decode("utf-8", errors="replace")
            
            # Body starts 4 bytes after header_end (\r\n\r\n = 4 bytes)
            body = data[header_end + 4:]
        except Exception as e:
            raise HTTPParseError(f"Failed to decode request: {e}")
        
        # =====================================================================
        # STEP 3: Split header section into lines
        # =====================================================================
        lines = header_section.split("\r\n")
        if not lines:
            raise HTTPParseError("Empty request")
        
        # =====================================================================
        # STEP 4: Parse the request line (first line)
        # =====================================================================
        # Format: METHOD SP REQUEST-URI SP HTTP-VERSION
        # Example: "GET /api/users?page=1 HTTP/1.1"
        #
        method, path, query_params, version = self._parse_request_line(lines[0])
        
        # =====================================================================
        # STEP 5: Parse headers (remaining lines)
        # =====================================================================
        headers = self._parse_headers(lines[1:])
        
        # =====================================================================
        # STEP 6: Validate and extract body
        # =====================================================================
        # Body length MUST match Content-Length header.
        # This prevents request smuggling attacks.
        #
        content_length = int(headers.get("content-length", 0))
        if len(body) < content_length:
            raise HTTPParseError(
                f"Incomplete body: expected {content_length} bytes, got {len(body)}"
            )
        
        # Truncate body to exactly Content-Length
        # (there might be extra data for next request in keep-alive)
        body = body[:content_length]
        
        # =====================================================================
        # STEP 7: Construct and return HTTPRequest
        # =====================================================================
        return HTTPRequest(
            method=method,
            path=path,
            version=version,
            headers=headers,
            query_params=query_params,
            body=body,
            client_address=client_address,
            raw=data,
        )
    
    def _parse_request_line(
        self,
        line: str
    ) -> tuple[str, str, Dict[str, list[str]], str]:
        """
        Parse the HTTP request line.
        
        =====================================================================
        REQUEST LINE FORMAT (RFC 7230)
        =====================================================================
        
            METHOD SP REQUEST-URI SP HTTP-VERSION CRLF
            
            Example: "GET /users?page=1 HTTP/1.1"
                     ─┬─ ─────┬─────── ────┬────
                      │       │            │
                    Method   URI       Version
        
        =====================================================================
        
        Args:
            line: The request line (e.g., "GET /path?query HTTP/1.1")
        
        Returns:
            Tuple of (method, path, query_params, version)
        
        Raises:
            HTTPParseError: If line is malformed
        """
        # Use regex to extract components
        match = self.REQUEST_LINE_PATTERN.match(line)
        if not match:
            raise HTTPParseError(f"Invalid request line: {line}")
        
        method, uri, version = match.groups()
        
        # ---------------------------------------------------------------------
        # Validate HTTP method
        # ---------------------------------------------------------------------
        if method not in self.VALID_METHODS:
            raise HTTPParseError(
                f"Invalid method: {method}",
                status_code=405  # Method Not Allowed
            )
        
        # ---------------------------------------------------------------------
        # Validate HTTP version
        # ---------------------------------------------------------------------
        if version not in ("HTTP/1.0", "HTTP/1.1"):
            raise HTTPParseError(
                f"Unsupported HTTP version: {version}",
                status_code=505  # HTTP Version Not Supported
            )
        
        # ---------------------------------------------------------------------
        # Parse URI into path and query string
        # ---------------------------------------------------------------------
        # URI: "/users/123?page=1&sort=name"
        # Path: "/users/123"
        # Query: {"page": ["1"], "sort": ["name"]}
        #
        parsed = urlparse(uri)
        path = unquote(parsed.path) or "/"  # URL-decode path
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        
        # ---------------------------------------------------------------------
        # Security: Prevent path traversal attacks
        # ---------------------------------------------------------------------
        # Path traversal: "GET /../../../etc/passwd HTTP/1.1"
        # Attacker tries to escape document root and read system files.
        #
        if ".." in path:
            raise HTTPParseError("Invalid path: contains ..", status_code=400)
        
        return method, path, query_params, version
    
    def _parse_headers(self, lines: list[str]) -> Dict[str, str]:
        """
        Parse HTTP headers into a dictionary.
        
        =====================================================================
        HEADER FORMAT (RFC 7230)
        =====================================================================
        
            field-name ":" OWS field-value OWS CRLF
            
            OWS = Optional WhiteSpace
            
            Examples:
                "Content-Type: application/json"
                "Accept:text/html"          (no space after colon is valid)
                "X-Custom:   value   "      (whitespace is trimmed)
        
        =====================================================================
        SPECIAL CASES HANDLED
        =====================================================================
        
        1. CASE NORMALIZATION: 
           "Content-Type" and "content-type" are the same header.
           We normalize all names to lowercase.
        
        2. HEADER CONTINUATION (obsolete but supported):
           "X-Long-Header: value\r\n"
           "    continued value"
           Lines starting with whitespace continue previous header.
        
        3. MULTIPLE VALUES:
           "Accept-Encoding: gzip\r\n"
           "Accept-Encoding: deflate"
           Same header repeated → combined with comma: "gzip, deflate"
        
        =====================================================================
        
        Args:
            lines: List of header lines (without request line).
        
        Returns:
            Dictionary of header name → value (names are lowercase).
        """
        headers: Dict[str, str] = {}
        current_name = None
        current_value = None
        
        for line in lines:
            if not line:
                continue
            
            # -----------------------------------------------------------------
            # Handle header continuation (obsolete RFC 2616 feature)
            # -----------------------------------------------------------------
            # Lines starting with space/tab continue the previous header.
            # Example:
            #   "X-Long: first part\r\n"
            #   "        second part"
            #
            if line[0] in (" ", "\t"):
                if current_name is not None:
                    current_value += " " + line.strip()
                    headers[current_name] = current_value
                continue
            
            # -----------------------------------------------------------------
            # Parse header line: "Name: Value"
            # -----------------------------------------------------------------
            match = self.HEADER_PATTERN.match(line)
            if not match:
                continue  # Skip malformed headers (lenient parsing)
            
            name, value = match.groups()
            name = name.strip().lower()  # Normalize to lowercase
            value = value.strip()
            
            current_name = name
            current_value = value
            
            # -----------------------------------------------------------------
            # Handle duplicate headers
            # -----------------------------------------------------------------
            # Per RFC 7230, multiple headers with same name are equivalent
            # to a single header with comma-separated values.
            # "Accept: text/html" + "Accept: text/json" = "Accept: text/html, text/json"
            #
            if name in headers:
                headers[name] += ", " + value
            else:
                headers[name] = value
        
        return headers


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def parse_request(
    data: bytes,
    client_address: tuple[str, int] = ("", 0),
    max_size: int = 10 * 1024 * 1024
) -> HTTPRequest:
    """
    Convenience function to parse an HTTP request.
    
    Creates a RequestParser instance and parses the data in one call.
    Use RequestParser directly if you need to parse multiple requests
    with the same settings.
    
    Args:
        data: Raw HTTP request bytes.
        client_address: Client's (ip, port) tuple.
        max_size: Maximum allowed request size.
    
    Returns:
        Parsed HTTPRequest object.
    """
    parser = RequestParser(max_request_size=max_size)
    return parser.parse(data, client_address)
