# HTTP Server in Python - Learning Plan

## Project Overview
Building an HTTP server from scratch in Python to understand how web servers work at a fundamental level.

---

## Step 1: Minimal TCP Server ✅
**Status:** Completed

### Concepts Covered:
- **OSI/TCP-IP Model** - Understanding the layered network architecture
  - Layer 7: Application (HTTP, FTP, SMTP, DNS)
  - Layer 4: Transport (TCP, UDP)
  - Layer 3: Network (IP)
  - Layer 2: Data Link (Ethernet, WiFi)
  - Layer 1: Physical (Cables, Radio waves)

- **TCP vs UDP** - Why TCP for HTTP
  - TCP: Connection-oriented, reliable, ordered, error-checked
  - The 3-way handshake (SYN, SYN-ACK, ACK)

- **Sockets** - The programming interface
  - File descriptor concept
  - Socket creation with `socket.socket()`
  - Binding to address and port
  - Listening for connections
  - Accepting client connections
  - Receiving and sending data

- **Ports** - Understanding port numbers
  - Well-known ports (0-1023)
  - Registered ports (1024-49151)
  - Dynamic/Ephemeral ports (49152-65535)

### Implementation:
- Created a minimal TCP server that accepts connections
- Server listens on localhost:4221
- Echoes back a simple HTTP response

---

## Step 2: HTTP Protocol Parser
**Status:** Not Started

### Goals:
- Parse HTTP request line (method, path, version)
- Parse HTTP headers
- Handle different HTTP methods (GET, POST, etc.)
- Return proper HTTP responses with status codes

---

## Step 3: Routing & Request Handling
**Status:** Not Started

### Goals:
- Implement URL routing
- Handle different endpoints
- Serve static files
- Return appropriate content types

---

## Step 4: Advanced Features
**Status:** Not Started

### Goals:
- Concurrent connections (threading/async)
- Keep-alive connections
- Error handling
- Logging

---

## Resources
- Python `socket` module documentation
- RFC 7230-7235 (HTTP/1.1 specification)
- TCP/IP networking fundamentals
