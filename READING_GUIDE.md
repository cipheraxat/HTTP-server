# 📚 HTTP Server Project - Reading Guide

> **A structured learning path to deeply understand this production-grade HTTP server built from scratch.**

This guide is designed for developers who want to understand how web servers work at a fundamental level. Follow this reading order to build knowledge progressively from foundational concepts to advanced patterns.

---

## 🎯 How to Use This Guide

1. **Read in order** - Each section builds on the previous
2. **Run the code** - After each section, experiment with the components
3. **Check the ASCII diagrams** - They visualize complex flows
4. **Review interview Q&A** - Each file has relevant interview questions
5. **Take notes** - Jot down concepts that are new to you

---

## 📖 Recommended Reading Order

### Phase 1: The Foundation (Start Here)
*Understand what you're building and the networking basics*

```
┌─────────────────────────────────────────────────────────────────────────┐
│  START HERE                                                             │
│  ──────────                                                             │
│                                                                         │
│  1. main.py (root)                                                      │
│     └── THE MOST IMPORTANT FILE                                         │
│     └── Contains ~550 lines of networking fundamentals                  │
│     └── OSI model, TCP/IP, sockets, 3-way handshake                    │
│     └── Read this like a textbook before anything else                 │
│                                                                         │
│  2. src/httpserver/__init__.py                                         │
│     └── Project overview and architecture diagram                       │
│     └── Package structure explanation                                   │
│     └── Quick start example                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Concepts You'll Learn:**
- OSI 7-layer model and TCP/IP 4-layer model
- How TCP works (reliable, ordered, connection-oriented)
- Socket programming fundamentals
- The 3-way handshake (SYN → SYN-ACK → ACK)
- Why we use sockets for network programming

**Time Estimate:** 30-45 minutes

---

### Phase 2: Low-Level Networking (The Core)
*How raw TCP connections are handled*

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CORE MODULE - src/httpserver/core/                                    │
│  ────────────────────────────────────                                  │
│                                                                         │
│  Read in this order:                                                   │
│                                                                         │
│  3. core/__init__.py                                                   │
│     └── Module overview                                                │
│                                                                         │
│  4. core/socket_server.py                                              │
│     └── TCP socket lifecycle                                           │
│     └── socket(), bind(), listen(), accept() explained                │
│     └── Accept loop implementation                                     │
│                                                                         │
│  5. core/connection.py                                                 │
│     └── Connection state machine                                       │
│     └── Reading/writing bytes from socket                             │
│     └── Buffer management                                              │
│                                                                         │
│  6. core/thread_pool.py                                                │
│     └── Why we need concurrency                                        │
│     └── Thread pool pattern                                            │
│     └── Task queue and worker threads                                  │
│     └── Graceful shutdown                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Concepts You'll Learn:**
- Socket lifecycle (create → bind → listen → accept → close)
- Connection state management
- Thread pool concurrency pattern
- Why threading vs async for this use case
- Graceful shutdown handling

**Time Estimate:** 45-60 minutes

---

### Phase 3: HTTP Protocol (The Protocol)
*How HTTP messages are parsed and built*

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HTTP MODULE - src/httpserver/http/                                    │
│  ──────────────────────────────────                                    │
│                                                                         │
│  Read in this order:                                                   │
│                                                                         │
│  7. http/__init__.py                                                   │
│     └── HTTP request-response cycle overview                           │
│                                                                         │
│  8. http/status_codes.py                                               │
│     └── HTTP status code categories (1xx-5xx)                         │
│     └── When to use each status code                                   │
│                                                                         │
│  9. http/request.py ⭐ CRITICAL FILE                                   │
│     └── HTTP request anatomy                                           │
│     └── Request line parsing (method, path, version)                  │
│     └── Header parsing                                                 │
│     └── Body handling (Content-Length, chunked)                       │
│     └── Query string parsing                                           │
│     └── Security: path traversal, request smuggling                   │
│                                                                         │
│  10. http/response.py ⭐ CRITICAL FILE                                 │
│      └── HTTP response structure                                       │
│      └── ResponseBuilder pattern                                       │
│      └── JSON, HTML, file responses                                    │
│      └── Redirect handling                                             │
│                                                                         │
│  11. http/mime_types.py                                                │
│      └── Content-Type detection                                        │
│      └── Why MIME types matter                                         │
│                                                                         │
│  12. http/router.py                                                    │
│      └── URL routing architecture                                      │
│      └── Pattern matching with regex                                   │
│      └── Dynamic path parameters (:id)                                │
│      └── Wildcard routes (*)                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Concepts You'll Learn:**
- HTTP message format (request line, headers, body)
- HTTP methods (GET, POST, PUT, DELETE, etc.)
- Status code categories and when to use them
- Content negotiation
- URL routing patterns
- Builder design pattern

**Time Estimate:** 60-90 minutes

---

### Phase 4: Middleware (Cross-Cutting Concerns)
*How to add features without modifying core code*

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MIDDLEWARE MODULE - src/httpserver/middleware/                        │
│  ─────────────────────────────────────────────                         │
│                                                                         │
│  Read in this order:                                                   │
│                                                                         │
│  13. middleware/__init__.py                                            │
│      └── Middleware pipeline diagram                                   │
│      └── What are cross-cutting concerns?                              │
│                                                                         │
│  14. middleware/base.py ⭐ DESIGN PATTERN                              │
│      └── Chain of Responsibility pattern                               │
│      └── Middleware contract (before/after)                            │
│      └── How the pipeline wraps handlers                               │
│                                                                         │
│  15. middleware/logging.py                                             │
│      └── Request logging implementation                                │
│      └── X-Request-ID for distributed tracing                         │
│      └── Apache log format vs JSON                                     │
│                                                                         │
│  16. middleware/cors.py                                                │
│      └── What is CORS and why it exists                               │
│      └── Preflight requests (OPTIONS)                                 │
│      └── CORS headers explained                                        │
│                                                                         │
│  17. middleware/compression.py                                         │
│      └── gzip compression                                              │
│      └── Content negotiation (Accept-Encoding)                        │
│      └── When to compress                                              │
│                                                                         │
│  18. middleware/rate_limit.py ⭐ ALGORITHM                             │
│      └── Token Bucket algorithm (interview favorite!)                  │
│      └── Rate limiting strategies                                      │
│      └── Distributed rate limiting concepts                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Concepts You'll Learn:**
- Chain of Responsibility design pattern
- Middleware architecture
- CORS (Cross-Origin Resource Sharing)
- Token Bucket rate limiting algorithm
- HTTP compression (gzip)
- Distributed tracing with request IDs

**Time Estimate:** 45-60 minutes

---

### Phase 5: Handlers (Business Logic)
*Practical request handlers*

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HANDLERS MODULE - src/httpserver/handlers/                            │
│  ─────────────────────────────────────────                             │
│                                                                         │
│  19. handlers/__init__.py                                              │
│      └── Handler types overview                                        │
│                                                                         │
│  20. handlers/health.py                                                │
│      └── Kubernetes liveness vs readiness probes                      │
│      └── Health check patterns                                         │
│      └── Why Cache-Control: no-store?                                  │
│                                                                         │
│  21. handlers/static.py                                                │
│      └── Static file serving                                           │
│      └── Path traversal attack prevention                              │
│      └── ETag caching                                                  │
│      └── HTTP caching headers                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Concepts You'll Learn:**
- Kubernetes health probes (liveness, readiness)
- Static file serving security
- HTTP caching (ETag, Last-Modified, Cache-Control)
- Path traversal attack prevention

**Time Estimate:** 30 minutes

---

### Phase 6: Putting It All Together
*The orchestration layer*

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SERVER ORCHESTRATION                                                  │
│  ───────────────────                                                   │
│                                                                         │
│  22. config.py                                                         │
│      └── 12-factor app configuration                                  │
│      └── Environment variables                                         │
│      └── Configuration validation                                      │
│                                                                         │
│  23. server.py ⭐ THE HEART                                            │
│      └── How all components connect                                    │
│      └── Request lifecycle (accept → parse → route → respond)         │
│      └── Keep-alive connection handling                                │
│      └── Error handling                                                │
│                                                                         │
│  24. __main__.py                                                       │
│      └── CLI entry point                                               │
│      └── Argument parsing                                              │
│      └── Application bootstrap                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Concepts You'll Learn:**
- How all components integrate
- Request lifecycle end-to-end
- Configuration management
- CLI design patterns

**Time Estimate:** 30-45 minutes

---

## 🗺️ Visual Learning Path

```
                            START
                              │
                              ▼
                    ┌─────────────────┐
                    │    main.py      │ ← Networking Fundamentals
                    │   (textbook)    │
                    └────────┬────────┘
                             │
                             ▼
        ┌────────────────────┴────────────────────┐
        │                                          │
        ▼                                          ▼
┌───────────────┐                        ┌───────────────┐
│    core/      │ ← Sockets, Threads     │    http/      │ ← Protocol
│ socket_server │                        │   request     │
│ connection    │                        │   response    │
│ thread_pool   │                        │   router      │
└───────┬───────┘                        └───────┬───────┘
        │                                        │
        └────────────────┬───────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │    middleware/      │ ← Cross-cutting
              │  logging, cors,     │
              │  rate_limit, gzip   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │     handlers/       │ ← Business Logic
              │  health, static     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │     server.py       │ ← Orchestration
              │   (ties it all)     │
              └──────────┬──────────┘
                         │
                         ▼
                       DONE!
```

---

## ⏱️ Total Estimated Reading Time

| Phase | Topic | Time |
|-------|-------|------|
| 1 | Foundation (main.py, __init__.py) | 30-45 min |
| 2 | Core (sockets, connections, threads) | 45-60 min |
| 3 | HTTP (request, response, routing) | 60-90 min |
| 4 | Middleware (logging, CORS, rate limit) | 45-60 min |
| 5 | Handlers (health, static) | 30 min |
| 6 | Orchestration (config, server) | 30-45 min |
| **Total** | | **4-6 hours** |

---

## 🎓 Key Concepts Checklist

After reading this project, you should understand:

### Networking
- [ ] OSI model layers and TCP/IP model
- [ ] TCP vs UDP differences
- [ ] 3-way handshake
- [ ] Socket API (socket, bind, listen, accept, recv, send)
- [ ] Connection states

### HTTP Protocol
- [ ] HTTP request format (request line, headers, body)
- [ ] HTTP response format (status line, headers, body)
- [ ] HTTP methods and when to use them
- [ ] Status code categories (1xx-5xx)
- [ ] HTTP/1.1 keep-alive

### Concurrency
- [ ] Thread pool pattern
- [ ] Task queues
- [ ] Thread synchronization (locks, conditions)
- [ ] Graceful shutdown

### Design Patterns
- [ ] Chain of Responsibility (middleware)
- [ ] Builder (response building)
- [ ] Factory (handlers)
- [ ] Strategy (routing)

### Security
- [ ] Path traversal prevention
- [ ] Request size limits
- [ ] Rate limiting
- [ ] CORS

### Production Concepts
- [ ] Health checks (liveness, readiness)
- [ ] Structured logging
- [ ] Configuration management
- [ ] HTTP caching

---

## 🚀 Hands-On Exercises

After reading, try these exercises to solidify your understanding:

### Beginner
1. **Run the server** and make requests with `curl`
2. **Add a new route** - Create a `/api/time` endpoint
3. **Modify logging** - Add a custom field to the log output

### Intermediate
4. **Create custom middleware** - Add a request ID validation middleware
5. **Add a new status code handler** - Implement 429 retry logic
6. **Extend static handler** - Add support for range requests

### Advanced
7. **Implement basic auth middleware** - Check Authorization header
8. **Add metrics middleware** - Count requests per endpoint
9. **Implement request caching** - Cache GET responses in memory

---

## 📝 Interview Preparation Tips

Each file contains interview Q&A sections. Here are the **must-know** topics:

1. **From main.py**: TCP vs UDP, 3-way handshake, socket lifecycle
2. **From thread_pool.py**: Thread pool pattern, why not unlimited threads
3. **From request.py**: HTTP parsing, security (request smuggling)
4. **From rate_limit.py**: Token Bucket algorithm
5. **From cors.py**: Same-origin policy, preflight requests
6. **From health.py**: Liveness vs readiness probes

---

## 🔗 Quick Reference Links

- [RFC 7230 - HTTP/1.1 Message Syntax](https://tools.ietf.org/html/rfc7230)
- [RFC 7231 - HTTP/1.1 Semantics](https://tools.ietf.org/html/rfc7231)
- [Python socket documentation](https://docs.python.org/3/library/socket.html)
- [Python threading documentation](https://docs.python.org/3/library/threading.html)

---

*Happy Learning! 🎉*
