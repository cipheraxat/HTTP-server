"""
=============================================================================
HTTP PROTOCOL IMPLEMENTATION
=============================================================================

This module contains the core HTTP/1.1 protocol handling. It implements
the application layer (Layer 7) of our server, translating raw bytes
from TCP into structured HTTP messages.

=============================================================================
HTTP PROTOCOL OVERVIEW
=============================================================================

HTTP (HyperText Transfer Protocol) is a REQUEST-RESPONSE protocol:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    HTTP Request-Response Cycle                       │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   CLIENT                                         SERVER              │
    │      │                                              │                │
    │      │   HTTP Request                               │                │
    │      │  ─────────────────────────────────────────►  │                │
    │      │   GET /api/users HTTP/1.1                   │                │
    │      │   Host: example.com                         │                │
    │      │   Accept: application/json                  │                │
    │      │                                              │                │
    │      │                              HTTP Response   │                │
    │      │  ◄─────────────────────────────────────────  │                │
    │      │               HTTP/1.1 200 OK               │                │
    │      │               Content-Type: application/json │                │
    │      │               {"users": [...]}               │                │
    │      │                                              │                │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
MODULE COMPONENTS
=============================================================================

    ┌─────────────────────────────────────────────────────────────────────┐
    │ REQUEST PARSER (request.py)                                         │
    │ ─────────────────────────────────────────────────────────────────── │
    │ Parses raw bytes into HTTPRequest objects                           │
    │                                                                      │
    │ Input:   b"GET /users?id=1 HTTP/1.1\r\nHost: ...\r\n\r\n"          │
    │ Output:  HTTPRequest(method="GET", path="/users", ...)              │
    │                                                                      │
    │ Handles:                                                             │
    │   • Request line parsing (method, path, version)                    │
    │   • Header parsing (case-insensitive)                               │
    │   • Query string parsing (?key=value&...)                           │
    │   • Body extraction (based on Content-Length)                       │
    │   • JSON body parsing                                                │
    │   • Security (path traversal prevention)                            │
    └─────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │ RESPONSE BUILDER (response.py)                                      │
    │ ─────────────────────────────────────────────────────────────────── │
    │ Builds HTTPResponse objects and serializes to bytes                 │
    │                                                                      │
    │ Input:   ResponseBuilder().status(200).json({"ok": True})          │
    │ Output:  b"HTTP/1.1 200 OK\r\nContent-Type: ...\r\n\r\n{...}"      │
    │                                                                      │
    │ Features:                                                            │
    │   • Fluent builder pattern                                          │
    │   • Content-Type auto-detection                                     │
    │   • JSON serialization                                              │
    │   • CORS headers                                                    │
    │   • Caching headers                                                 │
    │   • Convenience functions (ok, not_found, redirect, etc.)          │
    └─────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │ ROUTER (router.py)                                                  │
    │ ─────────────────────────────────────────────────────────────────── │
    │ Maps URL paths to handler functions                                 │
    │                                                                      │
    │ Input:   GET /users/123                                             │
    │ Output:  calls get_user(request) with path_params={"id": "123"}    │
    │                                                                      │
    │ Features:                                                            │
    │   • Static paths: /users, /api/health                               │
    │   • Dynamic params: /users/:id → {"id": "123"}                     │
    │   • Wildcards: /static/*path → {"path": "css/style.css"}          │
    │   • Method routing: GET, POST, PUT, DELETE                          │
    │   • Route groups: Prefixed sub-routers                              │
    └─────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STATUS CODES (status_codes.py)                                      │
    │ ─────────────────────────────────────────────────────────────────── │
    │ HTTP status codes with reason phrases (RFC 7231)                    │
    │                                                                      │
    │ Example:  HTTPStatus.OK → 200, phrase="OK"                          │
    │           HTTPStatus.NOT_FOUND → 404, phrase="Not Found"            │
    │                                                                      │
    │ Categories:                                                          │
    │   • 1xx: Informational                                              │
    │   • 2xx: Success                                                    │
    │   • 3xx: Redirection                                                │
    │   • 4xx: Client Error                                               │
    │   • 5xx: Server Error                                               │
    └─────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │ MIME TYPES (mime_types.py)                                          │
    │ ─────────────────────────────────────────────────────────────────── │
    │ Maps file extensions to MIME types for Content-Type header         │
    │                                                                      │
    │ Example:  .html → text/html                                         │
    │           .json → application/json                                  │
    │           .png  → image/png                                         │
    │                                                                      │
    │ Used by static file handler to set correct Content-Type            │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
HTTP MESSAGE FORMAT (RFC 7230)
=============================================================================

    REQUEST:                          RESPONSE:
    ─────────                         ──────────
    GET /path HTTP/1.1\r\n            HTTP/1.1 200 OK\r\n
    Header: Value\r\n                 Header: Value\r\n
    Header: Value\r\n                 Header: Value\r\n
    \r\n                              \r\n
    [body]                            [body]

Key points:
- Lines end with CRLF (\r\n), not just \n
- Headers and body separated by empty line (\r\n\r\n)
- Header names are case-insensitive ("Content-Type" = "content-type")
- Body length specified by Content-Length header

=============================================================================
"""

from .request import HTTPRequest, RequestParser, HTTPParseError
from .response import (
    HTTPResponse, 
    ResponseBuilder,
    # Convenience functions for common responses
    ok,             # 200 OK
    created,        # 201 Created
    no_content,     # 204 No Content
    redirect,       # 301/302 Redirect
    bad_request,    # 400 Bad Request
    unauthorized,   # 401 Unauthorized
    forbidden,      # 403 Forbidden
    not_found,      # 404 Not Found
    method_not_allowed,  # 405 Method Not Allowed
    internal_error,      # 500 Internal Server Error
)
from .router import Router, Route
from .status_codes import HTTPStatus
from .mime_types import get_mime_type, get_content_type

# Public API - what you get when you do:
# from httpserver.http import *
__all__ = [
    # Request parsing
    "HTTPRequest",
    "RequestParser",
    "HTTPParseError",
    
    # Response building
    "HTTPResponse",
    "ResponseBuilder",
    
    # Response convenience functions
    "ok",
    "created",
    "no_content",
    "redirect",
    "bad_request",
    "unauthorized",
    "forbidden",
    "not_found",
    "method_not_allowed",
    "internal_error",
    
    # Routing
    "Router",
    "Route",
    
    # Status codes
    "HTTPStatus",
    
    # MIME types
    "get_mime_type",
    "get_content_type",
]
