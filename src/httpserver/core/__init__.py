"""
=============================================================================
CORE SERVER COMPONENTS
=============================================================================

This module contains the low-level networking infrastructure that powers
our HTTP server. These are the foundational building blocks that handle
the "plumbing" of network communication.

=============================================================================
ARCHITECTURE OVERVIEW
=============================================================================

The core module is organized into three main components:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                         SOCKET SERVER                                │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • Creates the main TCP listening socket                            │
    │  • Binds to IP:PORT and listens for connections                     │
    │  • Runs the accept() loop in the main thread                        │
    │  • Handles graceful shutdown via signals (SIGTERM, SIGINT)         │
    │                                                                      │
    │  ANALOGY: The receptionist at a hotel front desk                    │
    │  - Waits for guests (connections) to arrive                         │
    │  - Greets them and hands them off to a bellhop (worker thread)     │
    │  - Doesn't handle guests personally, just coordinates               │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Hands off new connections
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                          THREAD POOL                                 │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • Maintains a pool of worker threads                               │
    │  • Workers pull tasks from a shared queue                           │
    │  • Limits max concurrent connections (prevents resource exhaustion) │
    │  • Scales up/down based on load                                     │
    │                                                                      │
    │  ANALOGY: A team of bellhops at the hotel                           │
    │  - Each bellhop can handle one guest at a time                      │
    │  - They wait for work in a break room (queue)                       │
    │  - When busy, more bellhops can be called in (up to max)           │
    │  - At quiet times, some can go home (scale down)                    │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Worker processes connection
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                          CONNECTION                                  │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • Wraps a client socket with helper methods                        │
    │  • Handles buffered reading (TCP is a stream, not messages!)       │
    │  • Manages connection state (NEW → READING → PROCESSING → WRITING) │
    │  • Supports HTTP keep-alive (multiple requests per connection)     │
    │                                                                      │
    │  ANALOGY: The bellhop escorting a guest to their room               │
    │  - Carries their luggage (request data)                             │
    │  - Waits for them to be ready (keep-alive)                         │
    │  - Eventually says goodbye (close connection)                       │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
WHY THIS ARCHITECTURE?
=============================================================================

1. SEPARATION OF CONCERNS
   Each component has ONE job:
   - SocketServer: Accept connections
   - ThreadPool: Manage concurrency
   - Connection: Handle I/O
   
   This makes the code easier to test, debug, and modify.

2. THREAD-PER-CONNECTION MODEL
   Each connection is handled by one worker thread. This is:
   - Simple to understand and debug
   - Good for I/O-bound workloads (like HTTP)
   - Supported by Python's socket API
   
   ALTERNATIVES:
   - Event loop (asyncio): More scalable but more complex
   - Process pool: Better CPU utilization but more overhead
   - Hybrid: Event loop + thread pool (what nginx does)

3. GRACEFUL SHUTDOWN
   The server can be stopped cleanly without dropping active requests:
   - Stop accepting new connections
   - Wait for in-progress requests to complete
   - Close all sockets properly

=============================================================================
IMPORTS AND EXPORTS
=============================================================================
"""

from .socket_server import SocketServer
from .connection import Connection, ConnectionState
from .thread_pool import ThreadPool

# __all__ defines what gets exported when someone does:
# from httpserver.core import *
#
# It's good practice to be explicit about your public API.
# Internal/private classes should NOT be in __all__.

__all__ = [
    "SocketServer",     # Main TCP server - accepts connections
    "Connection",       # Wrapper for client socket - handles I/O
    "ConnectionState",  # Enum for connection lifecycle states
    "ThreadPool",       # Manages worker threads for concurrency
]
