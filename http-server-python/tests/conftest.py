"""
pytest configuration and fixtures.
"""

import socket
import threading
import time
from typing import Generator
import pytest

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from httpserver import HTTPServer, ServerConfig
from httpserver.http import HTTPRequest, HTTPResponse, ResponseBuilder, HTTPStatus


@pytest.fixture
def sample_get_request() -> bytes:
    """Sample HTTP GET request."""
    return (
        b"GET /api/users?page=1&limit=10 HTTP/1.1\r\n"
        b"Host: localhost:8080\r\n"
        b"User-Agent: pytest\r\n"
        b"Accept: application/json\r\n"
        b"Connection: keep-alive\r\n"
        b"\r\n"
    )


@pytest.fixture
def sample_post_request() -> bytes:
    """Sample HTTP POST request with JSON body."""
    body = b'{"name": "John", "email": "john@example.com"}'
    return (
        b"POST /api/users HTTP/1.1\r\n"
        b"Host: localhost:8080\r\n"
        b"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n".encode()
        b"Connection: close\r\n"
        b"\r\n"
    ) + body


@pytest.fixture
def config() -> ServerConfig:
    """Default test server configuration."""
    return ServerConfig(
        host="127.0.0.1",
        port=0,  # Let OS pick a free port
        min_workers=2,
        max_workers=4,
        timeout=5.0,
    )


@pytest.fixture
def free_port() -> int:
    """Get a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class TestServer:
    """Test server helper that runs in a background thread."""
    
    def __init__(self, server: HTTPServer, port: int):
        self.server = server
        self.port = port
        self._thread: threading.Thread = None
    
    def start(self):
        """Start server in background thread."""
        self._thread = threading.Thread(
            target=self.server.run,
            kwargs={"port": self.port},
            daemon=True
        )
        self._thread.start()
        
        # Wait for server to be ready
        for _ in range(50):  # 5 seconds max
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(('127.0.0.1', self.port))
                    return
            except ConnectionRefusedError:
                time.sleep(0.1)
        
        raise RuntimeError("Server failed to start")
    
    def stop(self):
        """Stop the server."""
        if self.server._running:
            self.server._socket_server.shutdown()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)


@pytest.fixture
def test_server(free_port: int) -> Generator[TestServer, None, None]:
    """Create a test server."""
    server = HTTPServer(ServerConfig(
        host="127.0.0.1",
        port=free_port,
        min_workers=2,
        max_workers=4,
        log_level="WARNING",
    ))
    
    # Add test route
    @server.get("/test")
    def test_route(request: HTTPRequest) -> HTTPResponse:
        return ResponseBuilder().json({"status": "ok"}).build()
    
    @server.post("/echo")
    def echo_route(request: HTTPRequest) -> HTTPResponse:
        return ResponseBuilder().json({"received": request.json}).build()
    
    test_srv = TestServer(server, free_port)
    test_srv.start()
    
    yield test_srv
    
    test_srv.stop()
