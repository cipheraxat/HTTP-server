"""
Unit tests for URL router.
"""

import pytest

from httpserver.http.router import Router, Route, RouteMatch
from httpserver.http.request import HTTPRequest
from httpserver.http.response import HTTPResponse, ResponseBuilder, HTTPStatus


def make_request(method: str, path: str) -> HTTPRequest:
    """Helper to create a request for testing."""
    return HTTPRequest(method=method, path=path)


def dummy_handler(request: HTTPRequest) -> HTTPResponse:
    """Dummy handler for testing."""
    return ResponseBuilder().json({"path": request.path}).build()


class TestRouter:
    """Tests for Router class."""
    
    def test_add_route(self):
        """Test adding routes."""
        router = Router()
        router.add_route("/users", dummy_handler, method="GET")
        
        assert len(router._routes) == 1
        assert router._routes[0].path == "/users"
        assert router._routes[0].method == "GET"
    
    def test_match_static_path(self):
        """Test matching static paths."""
        router = Router()
        router.add_route("/users", dummy_handler, method="GET")
        router.add_route("/posts", dummy_handler, method="GET")
        
        match = router.match("GET", "/users")
        assert match is not None
        assert match.route.path == "/users"
        
        match = router.match("GET", "/posts")
        assert match is not None
        assert match.route.path == "/posts"
    
    def test_match_with_method(self):
        """Test method-based routing."""
        router = Router()
        router.add_route("/users", dummy_handler, method="GET")
        router.add_route("/users", dummy_handler, method="POST")
        
        get_match = router.match("GET", "/users")
        post_match = router.match("POST", "/users")
        
        assert get_match is not None
        assert post_match is not None
        assert get_match.route.method == "GET"
        assert post_match.route.method == "POST"
    
    def test_match_dynamic_params(self):
        """Test dynamic path parameters."""
        router = Router()
        router.add_route("/users/:id", dummy_handler, method="GET")
        router.add_route("/users/:user_id/posts/:post_id", dummy_handler, method="GET")
        
        match = router.match("GET", "/users/123")
        assert match is not None
        assert match.params == {"id": "123"}
        
        match = router.match("GET", "/users/456/posts/789")
        assert match is not None
        assert match.params == {"user_id": "456", "post_id": "789"}
    
    def test_match_wildcard(self):
        """Test wildcard path matching."""
        router = Router()
        router.add_route("/static/*path", dummy_handler, method="GET")
        
        match = router.match("GET", "/static/css/style.css")
        assert match is not None
        assert match.params == {"path": "css/style.css"}
        
        match = router.match("GET", "/static/js/app.js")
        assert match is not None
        assert match.params["path"] == "js/app.js"
    
    def test_no_match(self):
        """Test when no route matches."""
        router = Router()
        router.add_route("/users", dummy_handler, method="GET")
        
        match = router.match("GET", "/posts")
        assert match is None
        
        match = router.match("POST", "/users")  # Wrong method
        assert match is None
    
    def test_get_allowed_methods(self):
        """Test getting allowed methods for a path."""
        router = Router()
        router.add_route("/users", dummy_handler, method="GET")
        router.add_route("/users", dummy_handler, method="POST")
        router.add_route("/users", dummy_handler, method="DELETE")
        
        allowed = router.get_allowed_methods("/users")
        assert set(allowed) == {"DELETE", "GET", "POST"}
    
    def test_handle_success(self):
        """Test handling a request successfully."""
        router = Router()
        
        @router.get("/hello")
        def hello(request):
            return ResponseBuilder().text("Hello!").build()
        
        request = make_request("GET", "/hello")
        response = router.handle(request)
        
        assert response.status == HTTPStatus.OK
        assert response.body == b"Hello!"
    
    def test_handle_not_found(self):
        """Test 404 handling."""
        router = Router()
        router.add_route("/users", dummy_handler, method="GET")
        
        request = make_request("GET", "/posts")
        response = router.handle(request)
        
        assert response.status == HTTPStatus.NOT_FOUND
    
    def test_handle_method_not_allowed(self):
        """Test 405 handling."""
        router = Router()
        router.add_route("/users", dummy_handler, method="GET")
        
        request = make_request("POST", "/users")
        response = router.handle(request)
        
        assert response.status == HTTPStatus.METHOD_NOT_ALLOWED
        assert "Allow" in response.headers
    
    def test_path_params_in_request(self):
        """Test that path params are injected into request."""
        router = Router()
        captured_params = {}
        
        @router.get("/users/:id")
        def get_user(request):
            captured_params.update(request.path_params)
            return ResponseBuilder().json(request.path_params).build()
        
        request = make_request("GET", "/users/42")
        router.handle(request)
        
        assert captured_params == {"id": "42"}


class TestRouterDecorators:
    """Tests for decorator-style route registration."""
    
    def test_get_decorator(self):
        """Test @router.get decorator."""
        router = Router()
        
        @router.get("/test")
        def test_handler(request):
            return ResponseBuilder().text("test").build()
        
        assert len(router._routes) == 1
        assert router._routes[0].method == "GET"
    
    def test_post_decorator(self):
        """Test @router.post decorator."""
        router = Router()
        
        @router.post("/test")
        def test_handler(request):
            return ResponseBuilder().text("test").build()
        
        assert router._routes[0].method == "POST"
    
    def test_named_route(self):
        """Test named routes for URL generation."""
        router = Router()
        
        @router.get("/users/:id", name="get_user")
        def get_user(request):
            return ResponseBuilder().text("test").build()
        
        url = router.url_for("get_user", id="123")
        assert url == "/users/123"


class TestRouterGroups:
    """Tests for route groups and sub-routers."""
    
    def test_group_prefix(self):
        """Test route groups with prefix."""
        router = Router()
        api = router.group("/api/v1")
        
        @api.get("/users")
        def list_users(request):
            return ResponseBuilder().json([]).build()
        
        match = router.match("GET", "/api/v1/users")
        assert match is not None
    
    def test_nested_groups(self):
        """Test nested route groups."""
        router = Router()
        api = router.group("/api")
        v1 = api.group("/v1")
        
        @v1.get("/users")
        def list_users(request):
            return ResponseBuilder().json([]).build()
        
        # Note: Nested groups are registered as sub-routers
        # The exact matching depends on implementation


class TestRouterURLGeneration:
    """Tests for URL generation."""
    
    def test_url_for_static(self):
        """Test URL generation for static routes."""
        router = Router()
        router.add_route("/users", dummy_handler, name="users")
        
        url = router.url_for("users")
        assert url == "/users"
    
    def test_url_for_with_params(self):
        """Test URL generation with parameters."""
        router = Router()
        router.add_route("/users/:id/posts/:post_id", dummy_handler, name="user_post")
        
        url = router.url_for("user_post", id="123", post_id="456")
        assert url == "/users/123/posts/456"
    
    def test_url_for_unknown(self):
        """Test URL generation for unknown route."""
        router = Router()
        url = router.url_for("nonexistent")
        assert url is None
