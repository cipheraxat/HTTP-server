"""
Unit tests for HTTP response building.
"""

import pytest
import json

from httpserver.http.response import (
    HTTPResponse,
    ResponseBuilder,
    HTTPStatus,
    ok,
    created,
    not_found,
    bad_request,
    internal_error,
    redirect,
    format_http_date,
)


class TestHTTPResponse:
    """Tests for HTTPResponse class."""
    
    def test_status_line(self):
        """Test status line generation."""
        response = HTTPResponse(status=HTTPStatus.OK)
        assert response.status_line == "HTTP/1.1 200 OK"
        
        response = HTTPResponse(status=HTTPStatus.NOT_FOUND)
        assert response.status_line == "HTTP/1.1 404 Not Found"
    
    def test_to_bytes_includes_headers(self):
        """Test that to_bytes includes all headers."""
        response = HTTPResponse(
            status=HTTPStatus.OK,
            headers={"X-Custom": "value"},
            body=b"test",
        )
        
        result = response.to_bytes()
        
        assert b"HTTP/1.1 200 OK\r\n" in result
        assert b"X-Custom: value\r\n" in result
        assert b"Content-Length: 4\r\n" in result
        assert b"\r\n\r\ntest" in result
    
    def test_to_bytes_sets_content_length(self):
        """Test that Content-Length is auto-set."""
        response = HTTPResponse(body=b"hello world")
        result = response.to_bytes()
        
        assert b"Content-Length: 11\r\n" in result
    
    def test_set_header_chaining(self):
        """Test method chaining for headers."""
        response = (HTTPResponse()
            .set_header("X-One", "1")
            .set_header("X-Two", "2"))
        
        assert response.headers["X-One"] == "1"
        assert response.headers["X-Two"] == "2"


class TestResponseBuilder:
    """Tests for ResponseBuilder class."""
    
    def test_status(self):
        """Test setting status code."""
        response = ResponseBuilder().status(HTTPStatus.CREATED).build()
        assert response.status == HTTPStatus.CREATED
    
    def test_json_body(self):
        """Test JSON body encoding."""
        data = {"name": "John", "age": 30}
        response = ResponseBuilder().json(data).build()
        
        assert response.headers["Content-Type"] == "application/json; charset=utf-8"
        assert json.loads(response.body) == data
    
    def test_html_body(self):
        """Test HTML body."""
        html = "<html><body>Hello</body></html>"
        response = ResponseBuilder().html(html).build()
        
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"
        assert response.body == html.encode()
    
    def test_text_body(self):
        """Test plain text body."""
        text = "Hello, World!"
        response = ResponseBuilder().text(text).build()
        
        assert response.headers["Content-Type"] == "text/plain; charset=utf-8"
        assert response.body == text.encode()
    
    def test_redirect(self):
        """Test redirect response."""
        response = ResponseBuilder().redirect("/new-location").build()
        
        assert response.status == HTTPStatus.FOUND
        assert response.headers["Location"] == "/new-location"
    
    def test_redirect_permanent(self):
        """Test permanent redirect."""
        response = ResponseBuilder().redirect("/new", permanent=True).build()
        
        assert response.status == HTTPStatus.MOVED_PERMANENTLY
    
    def test_cors_headers(self):
        """Test CORS header setting."""
        response = ResponseBuilder().cors(
            origin="https://example.com",
            methods=["GET", "POST"],
            headers=["X-Custom"],
        ).build()
        
        assert response.headers["Access-Control-Allow-Origin"] == "https://example.com"
        assert "GET" in response.headers["Access-Control-Allow-Methods"]
        assert "X-Custom" in response.headers["Access-Control-Allow-Headers"]
    
    def test_cache_headers(self):
        """Test cache header setting."""
        response = ResponseBuilder().cache(max_age=3600).build()
        assert response.headers["Cache-Control"] == "public, max-age=3600"
        
        response = ResponseBuilder().no_cache().build()
        assert "no-store" in response.headers["Cache-Control"]
    
    def test_keep_alive(self):
        """Test keep-alive headers."""
        response = ResponseBuilder().keep_alive(timeout=10, max_requests=50).build()
        
        assert response.headers["Connection"] == "keep-alive"
        assert "timeout=10" in response.headers["Keep-Alive"]
        assert "max=50" in response.headers["Keep-Alive"]
    
    def test_close_connection(self):
        """Test connection close header."""
        response = ResponseBuilder().close_connection().build()
        assert response.headers["Connection"] == "close"
    
    def test_method_chaining(self):
        """Test fluent API chaining."""
        response = (ResponseBuilder()
            .status(HTTPStatus.OK)
            .header("X-Custom", "value")
            .json({"key": "value"})
            .build())
        
        assert response.status == HTTPStatus.OK
        assert response.headers["X-Custom"] == "value"
        assert b'"key"' in response.body


class TestConvenienceFunctions:
    """Tests for convenience response functions."""
    
    def test_ok(self):
        """Test ok() function."""
        response = ok("Hello")
        assert response.status == HTTPStatus.OK
        assert response.body == b"Hello"
        
        response = ok({"msg": "hello"})
        assert b'"msg"' in response.body
    
    def test_created(self):
        """Test created() function."""
        response = created({"id": 123}, location="/items/123")
        assert response.status == HTTPStatus.CREATED
        assert response.headers["Location"] == "/items/123"
    
    def test_not_found(self):
        """Test not_found() function."""
        response = not_found("Resource not found")
        assert response.status == HTTPStatus.NOT_FOUND
        assert b"Resource not found" in response.body
    
    def test_bad_request(self):
        """Test bad_request() function."""
        response = bad_request("Invalid input")
        assert response.status == HTTPStatus.BAD_REQUEST
        assert b"Invalid input" in response.body
    
    def test_internal_error(self):
        """Test internal_error() function."""
        response = internal_error()
        assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR


class TestHTTPStatus:
    """Tests for HTTPStatus enum."""
    
    def test_status_phrases(self):
        """Test that all statuses have phrases."""
        assert HTTPStatus.OK.phrase == "OK"
        assert HTTPStatus.NOT_FOUND.phrase == "Not Found"
        assert HTTPStatus.INTERNAL_SERVER_ERROR.phrase == "Internal Server Error"
    
    def test_status_categories(self):
        """Test status category helpers."""
        assert HTTPStatus.CONTINUE.is_informational
        assert HTTPStatus.OK.is_success
        assert HTTPStatus.FOUND.is_redirect
        assert HTTPStatus.NOT_FOUND.is_client_error
        assert HTTPStatus.INTERNAL_SERVER_ERROR.is_server_error
        
        assert HTTPStatus.NOT_FOUND.is_error
        assert HTTPStatus.INTERNAL_SERVER_ERROR.is_error
        assert not HTTPStatus.OK.is_error


class TestFormatHTTPDate:
    """Tests for HTTP date formatting."""
    
    def test_format(self):
        """Test HTTP date format."""
        from datetime import datetime, timezone
        
        dt = datetime(2026, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = format_http_date(dt)
        
        # Should be: Thu, 15 Jan 2026 12:30:45 GMT
        assert "15 Jan 2026" in result
        assert "12:30:45 GMT" in result
