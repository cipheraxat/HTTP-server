"""
Unit tests for HTTP request parsing.
"""

import pytest

from httpserver.http.request import (
    HTTPRequest,
    RequestParser,
    HTTPParseError,
    parse_request,
)


class TestRequestParser:
    """Tests for RequestParser class."""
    
    def test_parse_simple_get(self, sample_get_request: bytes):
        """Test parsing a simple GET request."""
        parser = RequestParser()
        request = parser.parse(sample_get_request, ("127.0.0.1", 12345))
        
        assert request.method == "GET"
        assert request.path == "/api/users"
        assert request.version == "HTTP/1.1"
        assert request.client_address == ("127.0.0.1", 12345)
    
    def test_parse_headers(self, sample_get_request: bytes):
        """Test that headers are parsed correctly."""
        request = parse_request(sample_get_request)
        
        assert request.host == "localhost:8080"
        assert request.user_agent == "pytest"
        assert request.headers["accept"] == "application/json"
        assert request.is_keep_alive is True
    
    def test_parse_query_params(self, sample_get_request: bytes):
        """Test query parameter parsing."""
        request = parse_request(sample_get_request)
        
        assert request.get_query("page") == "1"
        assert request.get_query("limit") == "10"
        assert request.get_query("missing") is None
        assert request.get_query("missing", "default") == "default"
    
    def test_parse_post_with_body(self, sample_post_request: bytes):
        """Test parsing POST request with JSON body."""
        request = parse_request(sample_post_request)
        
        assert request.method == "POST"
        assert request.path == "/api/users"
        assert request.content_type == "application/json"
        assert request.is_json is True
        assert len(request.body) > 0
        
        # Test JSON parsing
        json_body = request.json
        assert json_body["name"] == "John"
        assert json_body["email"] == "john@example.com"
    
    def test_parse_path_with_special_chars(self):
        """Test URL-encoded path parsing."""
        raw = b"GET /search?q=hello%20world HTTP/1.1\r\nHost: test\r\n\r\n"
        request = parse_request(raw)
        
        assert request.path == "/search"
        assert request.get_query("q") == "hello world"
    
    def test_parse_invalid_method(self):
        """Test that invalid methods are rejected."""
        raw = b"INVALID /path HTTP/1.1\r\nHost: test\r\n\r\n"
        
        with pytest.raises(HTTPParseError) as exc_info:
            parse_request(raw)
        
        assert exc_info.value.status_code == 405
    
    def test_parse_invalid_request_line(self):
        """Test handling of malformed request line."""
        raw = b"GET\r\nHost: test\r\n\r\n"
        
        with pytest.raises(HTTPParseError):
            parse_request(raw)
    
    def test_parse_missing_headers(self):
        """Test parsing request with no headers."""
        raw = b"GET / HTTP/1.1\r\n\r\n"
        request = parse_request(raw)
        
        assert request.method == "GET"
        assert request.path == "/"
        assert len(request.headers) == 0
    
    def test_parse_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        raw = b"GET /../../../etc/passwd HTTP/1.1\r\nHost: test\r\n\r\n"
        
        with pytest.raises(HTTPParseError) as exc_info:
            parse_request(raw)
        
        assert "path" in str(exc_info.value).lower()
    
    def test_parse_request_too_large(self):
        """Test that oversized requests are rejected."""
        parser = RequestParser(max_request_size=100)
        raw = b"GET / HTTP/1.1\r\n" + b"X-Large: " + b"A" * 200 + b"\r\n\r\n"
        
        with pytest.raises(HTTPParseError) as exc_info:
            parser.parse(raw)
        
        assert exc_info.value.status_code == 413
    
    def test_http_version_parsing(self):
        """Test HTTP/1.0 and HTTP/1.1 version handling."""
        # HTTP/1.0 (Connection: close by default)
        raw_10 = b"GET / HTTP/1.0\r\nHost: test\r\n\r\n"
        request_10 = parse_request(raw_10)
        assert request_10.version == "HTTP/1.0"
        assert request_10.is_keep_alive is False
        
        # HTTP/1.1 (keep-alive by default)
        raw_11 = b"GET / HTTP/1.1\r\nHost: test\r\n\r\n"
        request_11 = parse_request(raw_11)
        assert request_11.version == "HTTP/1.1"
        assert request_11.is_keep_alive is True
    
    def test_content_length_handling(self):
        """Test Content-Length validation."""
        body = b"test body"
        raw = (
            b"POST / HTTP/1.1\r\n"
            b"Content-Length: 9\r\n"
            b"\r\n"
        ) + body
        
        request = parse_request(raw)
        assert request.content_length == 9
        assert request.body == body
    
    def test_case_insensitive_headers(self):
        """Test that header names are case-insensitive."""
        raw = b"GET / HTTP/1.1\r\nCONTENT-TYPE: text/html\r\n\r\n"
        request = parse_request(raw)
        
        assert request.content_type == "text/html"
        assert request.get_header("Content-Type") == "text/html"
        assert request.get_header("content-type") == "text/html"


class TestHTTPRequest:
    """Tests for HTTPRequest dataclass."""
    
    def test_get_header_default(self):
        """Test get_header with default value."""
        request = HTTPRequest(method="GET", path="/")
        
        assert request.get_header("X-Missing") == ""
        assert request.get_header("X-Missing", "default") == "default"
    
    def test_query_list(self):
        """Test getting multiple values for same query param."""
        request = HTTPRequest(
            method="GET",
            path="/",
            query_params={"tags": ["python", "http", "server"]},
        )
        
        assert request.get_query_list("tags") == ["python", "http", "server"]
        assert request.get_query("tags") == "python"  # First value
