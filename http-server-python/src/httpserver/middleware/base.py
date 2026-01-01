"""
=============================================================================
BASE MIDDLEWARE INTERFACE
=============================================================================

Defines the middleware protocol and the pipeline for chaining middleware.
Implements the Chain of Responsibility design pattern.

=============================================================================
CHAIN OF RESPONSIBILITY PATTERN
=============================================================================

This is one of the Gang of Four design patterns. In this pattern:

1. A chain of handlers (middleware) is created
2. Each handler can either:
   - Process the request and return a response (short-circuit)
   - Pass the request to the next handler in the chain
3. Response flows back through the chain in reverse order

    ┌─────────────────────────────────────────────────────────────────────┐
    │              CHAIN OF RESPONSIBILITY - REQUEST FLOW                 │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   Request ────────────────────────────────────────────────►         │
    │                                                                      │
    │   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
    │   │  Logging │───►│   CORS   │───►│   Rate   │───►│ Handler  │     │
    │   │    MW    │    │    MW    │    │  Limit   │    │          │     │
    │   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘     │
    │        │               │               │               │            │
    │        │               │               │               │            │
    │        ▼               ▼               ▼               ▼            │
    │   [before]        [before]        [before]         [exec]          │
    │   log start       add vary        check rate       handle          │
    │                                                    request          │
    │        ▲               ▲               ▲               │            │
    │        │               │               │               │            │
    │        │               │               │               ▼            │
    │   [after]         [after]         [after]          [done]          │
    │   log end,        add CORS        add rate                         │
    │   timing          headers         headers                          │
    │                                                                      │
    │   ◄──────────────────────────────────────────────── Response        │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
INTERVIEW INSIGHT: CHAIN OF RESPONSIBILITY
=============================================================================

Q: "What design pattern would you use for middleware?"
A: "Chain of Responsibility. Each middleware is a handler that can either
   process the request or delegate to the next handler. This allows:
   - Decoupling sender from receiver
   - Adding/removing handlers dynamically
   - Each handler has single responsibility
   - Order can be easily changed"

Q: "How does middleware differ from decorators?"
A: "Decorators wrap at definition time (static). Middleware wraps at 
   runtime (dynamic). You can add/remove middleware without changing code.
   Middleware also has access to the full request/response context."

=============================================================================
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional
import logging

from ..http.request import HTTPRequest
from ..http.response import HTTPResponse


logger = logging.getLogger(__name__)


# =============================================================================
# TYPE ALIAS
# =============================================================================

# NextHandler is the signature for the next middleware or final handler.
# It takes a request and returns a response.
# Each middleware receives this and must call it to continue the chain.
NextHandler = Callable[[HTTPRequest], HTTPResponse]


class Middleware(ABC):
    """
    Abstract base class for middleware.
    
    =========================================================================
    THE MIDDLEWARE CONTRACT
    =========================================================================
    
    Every middleware must implement __call__ with this signature:
    
        def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse
    
    The `next` parameter is crucial - it's the next handler in the chain.
    You MUST call it (unless short-circuiting) to continue processing.
    
    =========================================================================
    MIDDLEWARE ANATOMY
    =========================================================================
    
        class MyMiddleware(Middleware):
            def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse:
                # ═══════════════════════════════════════════════════════════
                # PRE-PROCESSING (before handler runs)
                # ═══════════════════════════════════════════════════════════
                # - Validate request
                # - Extract/verify authentication
                # - Log request start
                # - Modify request (add headers, parse data)
                # - SHORT-CIRCUIT: Return response without calling next()
                
                if not self.is_valid(request):
                    return bad_request("Invalid request")  # Short-circuit!
                
                # ═══════════════════════════════════════════════════════════
                # CALL NEXT HANDLER
                # ═══════════════════════════════════════════════════════════
                # This continues the chain. If you don't call this,
                # the request never reaches the handler!
                
                response = next(request)  # <-- CRITICAL: Call next!
                
                # ═══════════════════════════════════════════════════════════
                # POST-PROCESSING (after handler runs)
                # ═══════════════════════════════════════════════════════════
                # - Modify response (add headers, compress body)
                # - Log response status
                # - Track metrics
                # - Handle errors
                
                response.set_header("X-Processed-By", "MyMiddleware")
                
                return response
    
    =========================================================================
    """
    
    @abstractmethod
    def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse:
        """
        Process the request.
        
        This method MUST:
        1. Optionally pre-process the request
        2. Call next(request) to continue the chain (unless short-circuiting)
        3. Optionally post-process the response
        4. Return the response
        
        Args:
            request: The incoming HTTP request
            next: The next handler in the chain (call this to continue!)
        
        Returns:
            HTTP response (either from next() or short-circuited)
        """
        pass
    
    @property
    def name(self) -> str:
        """Get the middleware name for logging."""
        return self.__class__.__name__


class MiddlewarePipeline:
    """
    Chains multiple middleware together with a final handler.
    
    =========================================================================
    PIPELINE ARCHITECTURE
    =========================================================================
    
    The pipeline wraps middleware around each other like layers of an onion:
    
        pipeline.add(LoggingMiddleware())    # First added = outermost
        pipeline.add(CORSMiddleware())       # Second
        pipeline.add(CompressionMiddleware())# Third = closest to handler
        
        Resulting structure:
        
            ┌─────────────────────────────────────────────────────────┐
            │  LoggingMiddleware                                      │
            │  ┌───────────────────────────────────────────────────┐  │
            │  │  CORSMiddleware                                   │  │
            │  │  ┌─────────────────────────────────────────────┐  │  │
            │  │  │  CompressionMiddleware                      │  │  │
            │  │  │  ┌─────────────────────────────────────┐    │  │  │
            │  │  │  │                                     │    │  │  │
            │  │  │  │         FINAL HANDLER               │    │  │  │
            │  │  │  │       (router.handle)               │    │  │  │
            │  │  │  │                                     │    │  │  │
            │  │  │  └─────────────────────────────────────┘    │  │  │
            │  │  └─────────────────────────────────────────────┘  │  │
            │  └───────────────────────────────────────────────────┘  │
            └─────────────────────────────────────────────────────────┘
    
    =========================================================================
    EXECUTION ORDER
    =========================================================================
    
    Request flows INWARD (first middleware first):
        1. LoggingMiddleware (before)
        2. CORSMiddleware (before)
        3. CompressionMiddleware (before)
        4. HANDLER
    
    Response flows OUTWARD (last middleware first):
        5. CompressionMiddleware (after) - compress response
        6. CORSMiddleware (after) - add CORS headers
        7. LoggingMiddleware (after) - log response
    
    =========================================================================
    USAGE
    =========================================================================
    
        # Create pipeline
        pipeline = MiddlewarePipeline()
        pipeline.add(LoggingMiddleware())
        pipeline.add(CORSMiddleware())
        
        # Wrap your handler
        handler = pipeline.wrap(router.handle)
        
        # Now handler includes all middleware
        response = handler(request)
    
    =========================================================================
    """
    
    def __init__(self):
        """Initialize an empty middleware pipeline."""
        self._middleware: List[Middleware] = []
    
    def add(self, middleware: Middleware) -> "MiddlewarePipeline":
        """
        Add middleware to the pipeline.
        
        Middleware is executed in the order added (first added = outermost).
        
        Args:
            middleware: Middleware instance to add
        
        Returns:
            Self for method chaining
        """
        self._middleware.append(middleware)
        logger.debug(f"Added middleware: {middleware.name}")
        return self  # Enable chaining: pipeline.add(A).add(B).add(C)
    
    def use(self, *middleware: Middleware) -> "MiddlewarePipeline":
        """
        Add multiple middleware at once.
        
        Convenience method for adding several middleware in one call.
        
        Args:
            *middleware: Middleware instances to add
        
        Returns:
            Self for method chaining
        
        Example:
            pipeline.use(LoggingMiddleware(), CORSMiddleware(), RateLimitMiddleware())
        """
        for mw in middleware:
            self.add(mw)
        return self
    
    def wrap(self, handler: NextHandler) -> NextHandler:
        """
        Wrap a handler with all middleware in the pipeline.
        
        This is the key method that creates the actual chain.
        
        =====================================================================
        HOW WRAPPING WORKS
        =====================================================================
        
        Given: [MW1, MW2, MW3] and handler
        
        Step 1: current = handler
        Step 2: current = MW3.wrap(current)  # MW3 calls handler
        Step 3: current = MW2.wrap(current)  # MW2 calls MW3
        Step 4: current = MW1.wrap(current)  # MW1 calls MW2
        
        Final: MW1 → MW2 → MW3 → handler
        
        We wrap in REVERSE order so that the first-added middleware
        is the outermost wrapper.
        
        =====================================================================
        
        Args:
            handler: The final request handler
        
        Returns:
            Wrapped handler function that includes all middleware
        """
        # Start with the final handler
        current = handler
        
        # Wrap in reverse order so first middleware is outermost
        # reversed([A, B, C]) = [C, B, A]
        # After wrapping: A(B(C(handler)))
        for middleware in reversed(self._middleware):
            current = self._create_wrapped_handler(middleware, current)
        
        return current
    
    def _create_wrapped_handler(
        self,
        middleware: Middleware,
        next_handler: NextHandler
    ) -> NextHandler:
        """
        Create a handler that calls middleware with next.
        
        This creates a CLOSURE that captures both the middleware
        and the next handler. When called, it invokes the middleware
        with the request and the next handler.
        
        =====================================================================
        CLOSURE PATTERN
        =====================================================================
        
        A closure is a function that "remembers" variables from its
        enclosing scope even after that scope has finished executing.
        
        Here, `wrapped` closes over `middleware` and `next_handler`.
        
        =====================================================================
        
        Args:
            middleware: The middleware to wrap
            next_handler: The next handler in the chain
        
        Returns:
            A new handler that invokes the middleware
        """
        def wrapped(request: HTTPRequest) -> HTTPResponse:
            return middleware(request, next_handler)
        
        return wrapped
    
    def __len__(self) -> int:
        """Get the number of middleware in the pipeline."""
        return len(self._middleware)
    
    def __iter__(self):
        """Iterate over middleware."""
        return iter(self._middleware)


# =============================================================================
# FUNCTION MIDDLEWARE
# =============================================================================
#
# Sometimes you want a quick one-off middleware without creating a class.
# FunctionMiddleware wraps a simple function as middleware.
#
# =============================================================================

class FunctionMiddleware(Middleware):
    """
    Wraps a simple function as middleware.
    
    Useful for quick inline middleware without creating a class.
    
    Usage:
        @function_middleware
        def add_header(request, next):
            response = next(request)
            response.set_header("X-Custom", "value")
            return response
        
        pipeline.add(add_header)
    
    Or without decorator:
        def my_func(request, next):
            return next(request)
        
        pipeline.add(FunctionMiddleware(my_func, name="my_func"))
    """
    
    def __init__(
        self,
        func: Callable[[HTTPRequest, NextHandler], HTTPResponse],
        name: Optional[str] = None
    ):
        """
        Create middleware from a function.
        
        Args:
            func: Function with signature (request, next) → response
            name: Optional name for logging (defaults to function name)
        """
        self._func = func
        self._name = name or func.__name__
    
    def __call__(self, request: HTTPRequest, next: NextHandler) -> HTTPResponse:
        """Delegate to the wrapped function."""
        return self._func(request, next)
    
    @property
    def name(self) -> str:
        """Return the middleware name."""
        return self._name


def function_middleware(
    func: Callable[[HTTPRequest, NextHandler], HTTPResponse]
) -> FunctionMiddleware:
    """
    Decorator to create middleware from a function.
    
    This is syntactic sugar for creating FunctionMiddleware.
    
    Usage:
        @function_middleware
        def my_middleware(request, next):
            # Pre-processing
            print(f"Processing {request.path}")
            
            # Continue chain
            response = next(request)
            
            # Post-processing
            response.set_header("X-Processed", "true")
            
            return response
        
        # Now use it like any middleware:
        pipeline.add(my_middleware)
    """
    return FunctionMiddleware(func)
