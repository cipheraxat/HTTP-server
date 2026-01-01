"""
=============================================================================
HTTP STATUS CODES (RFC 7231)
=============================================================================

This module defines all standard HTTP status codes with their reason phrases.

=============================================================================
STATUS CODE CATEGORIES
=============================================================================

HTTP status codes are 3-digit numbers grouped by the first digit:

    ┌────────────────────────────────────────────────────────────────────┐
    │                      STATUS CODE CATEGORIES                        │
    ├────────┬───────────────────────────────────────────────────────────┤
    │  1xx   │ INFORMATIONAL: Request received, continuing process      │
    │        │                                                           │
    │        │ 100 Continue      - Keep sending request body            │
    │        │ 101 Switching     - Upgrading to WebSocket               │
    ├────────┼───────────────────────────────────────────────────────────┤
    │  2xx   │ SUCCESS: Request received, understood, accepted          │
    │        │                                                           │
    │        │ 200 OK            - Standard success response            │
    │        │ 201 Created       - Resource created (POST)              │
    │        │ 204 No Content    - Success with no body (DELETE)        │
    ├────────┼───────────────────────────────────────────────────────────┤
    │  3xx   │ REDIRECTION: Further action needed                       │
    │        │                                                           │
    │        │ 301 Moved Permanently - Resource moved forever           │
    │        │ 302 Found             - Temporary redirect               │
    │        │ 304 Not Modified      - Use cached version               │
    ├────────┼───────────────────────────────────────────────────────────┤
    │  4xx   │ CLIENT ERROR: Problem with the request                   │
    │        │                                                           │
    │        │ 400 Bad Request   - Malformed request syntax             │
    │        │ 401 Unauthorized  - Authentication required              │
    │        │ 403 Forbidden     - Authenticated but not allowed        │
    │        │ 404 Not Found     - Resource doesn't exist               │
    │        │ 405 Method Not Allowed - Wrong HTTP method               │
    │        │ 429 Too Many Requests  - Rate limited                    │
    ├────────┼───────────────────────────────────────────────────────────┤
    │  5xx   │ SERVER ERROR: Problem with the server                    │
    │        │                                                           │
    │        │ 500 Internal Error    - Unexpected server failure        │
    │        │ 502 Bad Gateway       - Upstream server error            │
    │        │ 503 Service Unavailable - Server overloaded/down         │
    │        │ 504 Gateway Timeout   - Upstream timeout                 │
    └────────┴───────────────────────────────────────────────────────────┘

=============================================================================
INTERVIEW QUESTIONS ABOUT STATUS CODES
=============================================================================

Q: "What's the difference between 401 and 403?"
A: "401 Unauthorized means 'I don't know who you are' (authentication).
   403 Forbidden means 'I know who you are, but you can't do this' (authorization).
   Despite the name, 401 is really about authentication."

Q: "When would you use 201 vs 200?"
A: "201 Created is for POST requests that create a new resource.
   200 OK is for successful GET, PUT, PATCH, or other operations.
   201 typically includes a Location header pointing to the new resource."

Q: "What's 204 No Content used for?"
A: "When the request succeeded but there's no body to return.
   Common for DELETE (resource gone, nothing to show) or PUT
   that doesn't need to return the updated resource."

Q: "What's the difference between 301 and 302?"
A: "301 is permanent (browsers cache it, SEO updates).
   302 is temporary (browser doesn't cache, original URL is canonical).
   Use 301 for domain migrations, 302 for temporary redirects."

Q: "What's 304 Not Modified?"
A: "Used with conditional requests (If-None-Match, If-Modified-Since).
   Tells the client 'your cached version is still valid, use it.'
   Saves bandwidth by not re-sending unchanged resources."

=============================================================================
"""

from enum import IntEnum


class HTTPStatus(IntEnum):
    """
    HTTP status codes and reason phrases.
    
    This enum extends IntEnum, so status codes can be used as integers:
    
        >>> HTTPStatus.OK
        <HTTPStatus.OK: 200>
        >>> HTTPStatus.OK == 200
        True
        >>> HTTPStatus.OK.phrase
        'OK'
    
    Each status code has a .phrase property for the reason phrase used
    in HTTP response lines.
    """
    
    # =========================================================================
    # 1xx INFORMATIONAL
    # =========================================================================
    # Request received, processing continues
    # These are rarely used in typical web applications
    #
    CONTINUE = 100               # Client should continue with request
    SWITCHING_PROTOCOLS = 101    # Server is switching protocols (WebSocket upgrade)
    PROCESSING = 102             # WebDAV: Request received, still processing
    EARLY_HINTS = 103            # Preload resources while server prepares response
    
    # =========================================================================
    # 2xx SUCCESS
    # =========================================================================
    # Request was successfully received, understood, and accepted
    #
    OK = 200                                # Standard success response
    CREATED = 201                           # New resource was created (POST)
    ACCEPTED = 202                          # Request accepted, processing later (async)
    NON_AUTHORITATIVE_INFORMATION = 203     # Response from cache/proxy
    NO_CONTENT = 204                        # Success but no body to return (DELETE)
    RESET_CONTENT = 205                     # Clear the form that sent this
    PARTIAL_CONTENT = 206                   # Range request fulfilled (video streaming)
    MULTI_STATUS = 207                      # WebDAV: Multiple status codes
    ALREADY_REPORTED = 208                  # WebDAV: Already enumerated
    IM_USED = 226                           # Delta encoding applied
    
    # =========================================================================
    # 3xx REDIRECTION
    # =========================================================================
    # Client needs to take additional action
    #
    MULTIPLE_CHOICES = 300      # Multiple representations available
    MOVED_PERMANENTLY = 301     # Resource moved permanently (update bookmarks)
    FOUND = 302                 # Resource temporarily at different URL
    SEE_OTHER = 303             # Redirect to GET another URL (after POST)
    NOT_MODIFIED = 304          # Cached version is still valid
    USE_PROXY = 305             # Must access through proxy (deprecated)
    TEMPORARY_REDIRECT = 307    # Like 302 but preserves HTTP method
    PERMANENT_REDIRECT = 308    # Like 301 but preserves HTTP method
    
    # =========================================================================
    # 4xx CLIENT ERRORS
    # =========================================================================
    # Problem with the client's request
    #
    BAD_REQUEST = 400                   # Malformed request syntax
    UNAUTHORIZED = 401                  # Authentication required (not logged in)
    PAYMENT_REQUIRED = 402              # Reserved for future use
    FORBIDDEN = 403                     # Authenticated but not permitted
    NOT_FOUND = 404                     # Resource doesn't exist
    METHOD_NOT_ALLOWED = 405            # HTTP method not supported for resource
    NOT_ACCEPTABLE = 406                # Can't satisfy Accept header
    PROXY_AUTHENTICATION_REQUIRED = 407 # Must authenticate with proxy
    REQUEST_TIMEOUT = 408               # Client took too long to send request
    CONFLICT = 409                      # Conflict with current resource state
    GONE = 410                          # Resource existed but was deleted
    LENGTH_REQUIRED = 411               # Missing Content-Length header
    PRECONDITION_FAILED = 412           # Conditional request (If-*) failed
    PAYLOAD_TOO_LARGE = 413             # Request body too large
    URI_TOO_LONG = 414                  # URL too long
    UNSUPPORTED_MEDIA_TYPE = 415        # Content-Type not supported
    RANGE_NOT_SATISFIABLE = 416         # Range header invalid
    EXPECTATION_FAILED = 417            # Expect header not satisfied
    IM_A_TEAPOT = 418                   # RFC 2324 April Fools joke :)
    MISDIRECTED_REQUEST = 421           # Request for wrong server
    UNPROCESSABLE_ENTITY = 422          # Well-formed but semantically wrong
    LOCKED = 423                        # WebDAV: Resource is locked
    FAILED_DEPENDENCY = 424             # WebDAV: Dependency failed
    TOO_EARLY = 425                     # Request replayed (TLS)
    UPGRADE_REQUIRED = 426              # Must upgrade protocol
    PRECONDITION_REQUIRED = 428         # Missing required conditional headers
    TOO_MANY_REQUESTS = 429             # Rate limited
    REQUEST_HEADER_FIELDS_TOO_LARGE = 431   # Headers too large
    UNAVAILABLE_FOR_LEGAL_REASONS = 451     # Censored/DMCA/court order
    
    # =========================================================================
    # 5xx SERVER ERRORS
    # =========================================================================
    # Server failed to fulfill a valid request
    #
    INTERNAL_SERVER_ERROR = 500         # Unexpected server error (catch-all)
    NOT_IMPLEMENTED = 501               # Server doesn't support this feature
    BAD_GATEWAY = 502                   # Invalid response from upstream server
    SERVICE_UNAVAILABLE = 503           # Server overloaded or in maintenance
    GATEWAY_TIMEOUT = 504               # Upstream server timeout
    HTTP_VERSION_NOT_SUPPORTED = 505    # HTTP version not supported
    VARIANT_ALSO_NEGOTIATES = 506       # Content negotiation error
    INSUFFICIENT_STORAGE = 507          # WebDAV: Not enough storage
    LOOP_DETECTED = 508                 # WebDAV: Infinite loop in request
    NOT_EXTENDED = 510                  # Extensions required but not provided
    NETWORK_AUTHENTICATION_REQUIRED = 511   # Captive portal (WiFi login)
    
    # =========================================================================
    # PROPERTIES
    # =========================================================================
    
    @property
    def phrase(self) -> str:
        """
        Get the reason phrase for this status code.
        
        The reason phrase is the text that appears after the status code
        in an HTTP response line:
        
            HTTP/1.1 200 OK
                     ─── ──
                      │   │
                      │   └── Reason phrase
                      └────── Status code
        
        Returns:
            Human-readable description of the status code
        """
        return _STATUS_PHRASES.get(self, "Unknown")
    
    @property
    def is_informational(self) -> bool:
        """
        Check if this is a 1xx (informational) status code.
        
        Informational responses indicate the request was received and
        the server is continuing to process it.
        """
        return 100 <= self < 200
    
    @property
    def is_success(self) -> bool:
        """
        Check if this is a 2xx (success) status code.
        
        Success responses indicate the request was received, understood,
        and accepted.
        """
        return 200 <= self < 300
    
    @property
    def is_redirect(self) -> bool:
        """
        Check if this is a 3xx (redirection) status code.
        
        Redirection responses indicate the client must take additional
        action to complete the request.
        """
        return 300 <= self < 400
    
    @property
    def is_client_error(self) -> bool:
        """
        Check if this is a 4xx (client error) status code.
        
        Client error responses indicate the request was invalid or
        cannot be fulfilled due to client-side issues.
        """
        return 400 <= self < 500
    
    @property
    def is_server_error(self) -> bool:
        """
        Check if this is a 5xx (server error) status code.
        
        Server error responses indicate the server failed to fulfill
        a valid request.
        """
        return 500 <= self < 600
    
    @property
    def is_error(self) -> bool:
        """
        Check if this is an error status code (4xx or 5xx).
        
        Useful for logging and error handling.
        """
        return self >= 400


# =============================================================================
# REASON PHRASES
# =============================================================================
#
# The reason phrase is the human-readable text that appears after the
# status code in the HTTP response line.
#
# HTTP/1.1 200 OK
#          ─── ──
#           │   │
#           │   └── Reason phrase (from this dict)
#           └────── Status code
#
# Per RFC 7230, reason phrases are purely informational and may be
# modified or ignored by clients.
#
# =============================================================================

_STATUS_PHRASES = {
    # 1xx Informational
    HTTPStatus.CONTINUE: "Continue",
    HTTPStatus.SWITCHING_PROTOCOLS: "Switching Protocols",
    HTTPStatus.PROCESSING: "Processing",
    HTTPStatus.EARLY_HINTS: "Early Hints",
    
    # 2xx Success
    HTTPStatus.OK: "OK",
    HTTPStatus.CREATED: "Created",
    HTTPStatus.ACCEPTED: "Accepted",
    HTTPStatus.NON_AUTHORITATIVE_INFORMATION: "Non-Authoritative Information",
    HTTPStatus.NO_CONTENT: "No Content",
    HTTPStatus.RESET_CONTENT: "Reset Content",
    HTTPStatus.PARTIAL_CONTENT: "Partial Content",
    HTTPStatus.MULTI_STATUS: "Multi-Status",
    HTTPStatus.ALREADY_REPORTED: "Already Reported",
    HTTPStatus.IM_USED: "IM Used",
    
    # 3xx Redirection
    HTTPStatus.MULTIPLE_CHOICES: "Multiple Choices",
    HTTPStatus.MOVED_PERMANENTLY: "Moved Permanently",
    HTTPStatus.FOUND: "Found",
    HTTPStatus.SEE_OTHER: "See Other",
    HTTPStatus.NOT_MODIFIED: "Not Modified",
    HTTPStatus.USE_PROXY: "Use Proxy",
    HTTPStatus.TEMPORARY_REDIRECT: "Temporary Redirect",
    HTTPStatus.PERMANENT_REDIRECT: "Permanent Redirect",
    
    # 4xx Client Errors
    HTTPStatus.BAD_REQUEST: "Bad Request",
    HTTPStatus.UNAUTHORIZED: "Unauthorized",
    HTTPStatus.PAYMENT_REQUIRED: "Payment Required",
    HTTPStatus.FORBIDDEN: "Forbidden",
    HTTPStatus.NOT_FOUND: "Not Found",
    HTTPStatus.METHOD_NOT_ALLOWED: "Method Not Allowed",
    HTTPStatus.NOT_ACCEPTABLE: "Not Acceptable",
    HTTPStatus.PROXY_AUTHENTICATION_REQUIRED: "Proxy Authentication Required",
    HTTPStatus.REQUEST_TIMEOUT: "Request Timeout",
    HTTPStatus.CONFLICT: "Conflict",
    HTTPStatus.GONE: "Gone",
    HTTPStatus.LENGTH_REQUIRED: "Length Required",
    HTTPStatus.PRECONDITION_FAILED: "Precondition Failed",
    HTTPStatus.PAYLOAD_TOO_LARGE: "Payload Too Large",
    HTTPStatus.URI_TOO_LONG: "URI Too Long",
    HTTPStatus.UNSUPPORTED_MEDIA_TYPE: "Unsupported Media Type",
    HTTPStatus.RANGE_NOT_SATISFIABLE: "Range Not Satisfiable",
    HTTPStatus.EXPECTATION_FAILED: "Expectation Failed",
    HTTPStatus.IM_A_TEAPOT: "I'm a teapot",  # RFC 2324 April Fools joke, but real!
    HTTPStatus.MISDIRECTED_REQUEST: "Misdirected Request",
    HTTPStatus.UNPROCESSABLE_ENTITY: "Unprocessable Entity",
    HTTPStatus.LOCKED: "Locked",
    HTTPStatus.FAILED_DEPENDENCY: "Failed Dependency",
    HTTPStatus.TOO_EARLY: "Too Early",
    HTTPStatus.UPGRADE_REQUIRED: "Upgrade Required",
    HTTPStatus.PRECONDITION_REQUIRED: "Precondition Required",
    HTTPStatus.TOO_MANY_REQUESTS: "Too Many Requests",
    HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE: "Request Header Fields Too Large",
    HTTPStatus.UNAVAILABLE_FOR_LEGAL_REASONS: "Unavailable For Legal Reasons",
    
    # 5xx Server Errors
    HTTPStatus.INTERNAL_SERVER_ERROR: "Internal Server Error",
    HTTPStatus.NOT_IMPLEMENTED: "Not Implemented",
    HTTPStatus.BAD_GATEWAY: "Bad Gateway",
    HTTPStatus.SERVICE_UNAVAILABLE: "Service Unavailable",
    HTTPStatus.GATEWAY_TIMEOUT: "Gateway Timeout",
    HTTPStatus.HTTP_VERSION_NOT_SUPPORTED: "HTTP Version Not Supported",
    HTTPStatus.VARIANT_ALSO_NEGOTIATES: "Variant Also Negotiates",
    HTTPStatus.INSUFFICIENT_STORAGE: "Insufficient Storage",
    HTTPStatus.LOOP_DETECTED: "Loop Detected",
    HTTPStatus.NOT_EXTENDED: "Not Extended",
    HTTPStatus.NETWORK_AUTHENTICATION_REQUIRED: "Network Authentication Required",
}
