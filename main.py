"""
=============================================================================
STEP 1: MINIMAL TCP SERVER
=============================================================================

Before we write any code, let's understand the fundamental concepts of
computer networking. This knowledge will make everything else make sense.

=============================================================================
PART A: THE INTERNET - A LAYERED SYSTEM (OSI/TCP-IP Model)
=============================================================================

When you visit a website, data travels through multiple LAYERS, each with
a specific job. Think of it like sending a letter:

    ┌─────────────────────────────────────────────────────────────────┐
    │  LAYER 7: APPLICATION (HTTP, FTP, SMTP, DNS)                    │
    │  ─────────────────────────────────────────────────────────────  │
    │  "The letter content" - What you actually want to send          │
    │  HTTP says: "GET /index.html please"                            │
    │  This is what WE will build!                                    │
    ├─────────────────────────────────────────────────────────────────┤
    │  LAYER 4: TRANSPORT (TCP, UDP)                                  │
    │  ─────────────────────────────────────────────────────────────  │
    │  "Registered mail vs postcard" - Reliability guarantees         │
    │  TCP ensures your letter arrives, UDP just sends it             │
    │  This is what the socket module handles!                        │
    ├─────────────────────────────────────────────────────────────────┤
    │  LAYER 3: NETWORK (IP)                                          │
    │  ─────────────────────────────────────────────────────────────  │
    │  "The address on the envelope" - Where to send it               │
    │  IP addresses: 192.168.1.1, 10.0.0.1, etc.                      │
    │  Routers read this to forward packets                           │
    ├─────────────────────────────────────────────────────────────────┤
    │  LAYER 2: DATA LINK (Ethernet, WiFi)                            │
    │  ─────────────────────────────────────────────────────────────  │
    │  "The mail truck" - How to reach the next stop                  │
    │  MAC addresses: aa:bb:cc:dd:ee:ff                               │
    ├─────────────────────────────────────────────────────────────────┤
    │  LAYER 1: PHYSICAL (Cables, Radio waves)                        │
    │  ─────────────────────────────────────────────────────────────  │
    │  "The road" - Actual electrical signals or radio waves          │
    │  Ethernet cables, fiber optics, WiFi radio                      │
    └─────────────────────────────────────────────────────────────────┘

Each layer WRAPS the layer above it:

    Your Data: "Hello World"
         ↓ HTTP adds headers
    HTTP: "GET / HTTP/1.1\r\nHost: example.com\r\n\r\nHello World"
         ↓ TCP adds sequence numbers, checksums
    TCP:  [TCP Header | HTTP data]
         ↓ IP adds source/destination addresses
    IP:   [IP Header | TCP Header | HTTP data]
         ↓ Ethernet adds MAC addresses
    Frame: [Ethernet Header | IP Header | TCP Header | HTTP data | Checksum]
         ↓ Physical layer
    Wire: 010110101001010101010101010101010...


=============================================================================
PART B: TCP vs UDP - WHY TCP FOR HTTP?
=============================================================================

┌─────────────────────────────────────────────────────────────────────────┐
│                              TCP                                         │
│                    Transmission Control Protocol                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ANALOGY: Registered Mail with Delivery Confirmation                     │
│                                                                          │
│  ✓ Connection-oriented: Must establish connection first (handshake)     │
│  ✓ Reliable: Guarantees data arrives                                    │
│  ✓ Ordered: Data arrives in the same order it was sent                  │
│  ✓ Error-checked: Corrupted data is retransmitted                       │
│  ✓ Flow control: Sender slows down if receiver is overwhelmed           │
│                                                                          │
│  HOW IT WORKS - The 3-Way Handshake:                                    │
│                                                                          │
│      Client                    Server                                    │
│         │                         │                                      │
│         │   SYN (seq=100)         │  "Hey, wanna talk? Starting at 100" │
│         │ ───────────────────────►│                                      │
│         │                         │                                      │
│         │   SYN-ACK (seq=300,     │  "Sure! I'm at 300, got your 100"   │
│         │           ack=101)      │                                      │
│         │ ◄───────────────────────│                                      │
│         │                         │                                      │
│         │   ACK (ack=301)         │  "Great, got your 300, let's go!"   │
│         │ ───────────────────────►│                                      │
│         │                         │                                      │
│         │   ═══ CONNECTION ESTABLISHED ═══                               │
│                                                                          │
│  RELIABILITY - Sequence Numbers & ACKs:                                  │
│                                                                          │
│      Client                    Server                                    │
│         │                         │                                      │
│         │   Packet 1 (seq=1)      │                                      │
│         │ ───────────────────────►│                                      │
│         │   Packet 2 (seq=2)      │  (Packet 2 gets lost!)              │
│         │ ─ ─ ─ ─ ─ ─ ✗           │                                      │
│         │   Packet 3 (seq=3)      │                                      │
│         │ ───────────────────────►│                                      │
│         │                         │                                      │
│         │   ACK (ack=2)           │  "Got 1 and 3, missing 2!"          │
│         │ ◄───────────────────────│                                      │
│         │                         │                                      │
│         │   Packet 2 (seq=2)      │  (Retransmit!)                       │
│         │ ───────────────────────►│                                      │
│         │                         │                                      │
│         │   ACK (ack=4)           │  "Got everything!"                   │
│         │ ◄───────────────────────│                                      │
│                                                                          │
│  USE CASES:                                                              │
│  • HTTP/HTTPS (web browsing) - You need the COMPLETE page               │
│  • Email (SMTP, IMAP) - Emails must arrive intact                       │
│  • File transfer (FTP) - Files must be complete                         │
│  • SSH - Commands must execute in order                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                              UDP                                         │
│                     User Datagram Protocol                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ANALOGY: Throwing postcards out of a car window                         │
│                                                                          │
│  ✓ Connectionless: Just send, no handshake needed                       │
│  ✓ Fast: No waiting for acknowledgments                                 │
│  ✗ Unreliable: Packets may be lost, duplicated, or reordered           │
│  ✗ No flow control: Sender can overwhelm receiver                       │
│                                                                          │
│  HOW IT WORKS:                                                          │
│                                                                          │
│      Client                    Server                                    │
│         │                         │                                      │
│         │   Packet 1              │  (Just send it!)                    │
│         │ ───────────────────────►│                                      │
│         │   Packet 2              │  (Maybe it arrives, maybe not!)     │
│         │ ─ ─ ─ ─ ─ ─ ✗           │                                      │
│         │   Packet 3              │  (Server never knows 2 was lost!)   │
│         │ ───────────────────────►│                                      │
│         │                         │                                      │
│         │   (No acknowledgments, no retries, no guarantees)              │
│                                                                          │
│  USE CASES:                                                              │
│  • Video streaming - Missing a frame? Just show the next one            │
│  • Online gaming - Old position data is useless, send new one           │
│  • Voice calls (VoIP) - A little static is better than delay            │
│  • DNS queries - Small, simple, retry if no response                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    TCP vs UDP COMPARISON                                 │
├───────────────────────┬───────────────────────┬─────────────────────────┤
│ Feature               │ TCP                   │ UDP                     │
├───────────────────────┼───────────────────────┼─────────────────────────┤
│ Connection            │ Required (handshake)  │ Not required            │
│ Reliability           │ Guaranteed delivery   │ Best effort             │
│ Ordering              │ Guaranteed order      │ No ordering             │
│ Speed                 │ Slower (overhead)     │ Faster (no overhead)    │
│ Header size           │ 20-60 bytes           │ 8 bytes                 │
│ Use case              │ Accuracy critical     │ Speed critical          │
│ Example               │ Web, Email, Files     │ Video, Games, VoIP      │
└───────────────────────┴───────────────────────┴─────────────────────────┘

WHY TCP FOR HTTP?
─────────────────
When you load a webpage:
1. You need the COMPLETE HTML (missing tags = broken page)
2. CSS must arrive fully (partial CSS = ugly page)
3. JavaScript must be intact (partial JS = errors)
4. Images need every byte (partial image = corrupted)

A missing packet in a webpage is UNACCEPTABLE.
A slightly delayed webpage is ACCEPTABLE.

Therefore: TCP is perfect for HTTP!


=============================================================================
PART C: IP ADDRESSES AND PORTS
=============================================================================

IP ADDRESS - "Which Computer?"
──────────────────────────────
• IPv4: 32-bit number, written as 4 octets (192.168.1.1)
  - ~4.3 billion possible addresses (running out!)
  - Private ranges: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
  
• IPv6: 128-bit number (2001:0db8:85a3:0000:0000:8a2e:0370:7334)
  - 340 undecillion addresses (enough for every atom on Earth!)

• Special addresses:
  - 127.0.0.1 = localhost (this computer, never leaves the machine)
  - 0.0.0.0 = all interfaces (listen on all network cards)
  - 255.255.255.255 = broadcast (send to everyone on network)

PORT NUMBER - "Which Program?"
──────────────────────────────
• 16-bit number: 0-65535
• Identifies which SERVICE on a computer should receive data

• Well-known ports (0-1023) - Require admin/root privileges:
  - 20, 21: FTP (file transfer)
  - 22: SSH (secure shell)
  - 25: SMTP (email sending)
  - 53: DNS (domain name lookup)
  - 80: HTTP (web)
  - 443: HTTPS (secure web)

• Registered ports (1024-49151) - Common applications:
  - 3000: Node.js dev servers
  - 3306: MySQL database
  - 5432: PostgreSQL database
  - 8080: HTTP alternate (development)

• Dynamic ports (49152-65535) - Assigned to clients temporarily

EXAMPLE:
When you visit http://google.com:
    Your computer (192.168.1.100:54321) ──► Google (142.250.80.46:80)
    
    Source IP:Port     Destination IP:Port
    192.168.1.100:54321 → 142.250.80.46:80

The source port (54321) is randomly assigned by YOUR operating system.
The destination port (80) is fixed - that's where web servers listen.


=============================================================================
PART D: WHAT IS A SOCKET?
=============================================================================

A socket is an ENDPOINT for network communication.

ANALOGY: A socket is like a phone
──────────────────────────────────
1. You need a phone (create socket)
2. Your phone has a number (bind to IP + port)
3. You wait for calls (listen)
4. Someone calls, you pick up (accept)
5. You talk (send/receive data)
6. You hang up (close)

TYPES OF SOCKETS:
─────────────────
• Server socket: Listens for incoming connections (the receptionist)
• Client socket: Connects to a server (you making a call)
• Connection socket: Created when connection is accepted (the call itself)

                    ┌─────────────────────┐
                    │    Server Socket    │
                    │   (Receptionist)    │
                    │  Listening on :8080 │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │ Connection 1  │  │ Connection 2  │  │ Connection 3  │
    │ Client Socket │  │ Client Socket │  │ Client Socket │
    │ Browser #1    │  │ Browser #2    │  │ curl command  │
    └───────────────┘  └───────────────┘  └───────────────┘

When accept() is called:
- The SERVER socket keeps listening (doesn't change)
- A NEW socket is created just for that client
- This allows handling multiple clients!


=============================================================================
PART E: THE SOCKET LIFECYCLE (What We're Implementing)
=============================================================================

SERVER SIDE:                          CLIENT SIDE (Browser):
────────────                          ─────────────────────

1. socket()                           1. socket()
   Create a socket                       Create a socket
        │                                     │
        ▼                                     │
2. bind()                                     │
   Assign IP:Port                             │
        │                                     │
        ▼                                     │
3. listen()                                   │
   Start accepting                            │
        │                                     │
        ▼                                     ▼
4. accept() ◄─────────────────────────── 2. connect()
   Wait & accept                          Connect to server
        │                                     │
        ▼                                     ▼
5. recv() ◄───────────────────────────── 3. send()
   Receive request                        Send HTTP request
        │                                     │
        ▼                                     ▼
6. send() ────────────────────────────► 4. recv()
   Send response                          Receive response
        │                                     │
        ▼                                     ▼
7. close()                              5. close()
   End connection                         End connection


=============================================================================
NOW LET'S WRITE THE CODE!
=============================================================================
"""

import socket  # Python's interface to OS networking - a thin wrapper around C syscalls

# =============================================================================
# CONFIGURATION
# =============================================================================

HOST = '127.0.0.1'  # localhost - only accessible from this computer
                     # This IP is special - packets never leave your machine
                     # They go: App → Kernel → Loopback interface → Kernel → App
                     # Use '0.0.0.0' to allow connections from other computers

PORT = 8080          # The port number to listen on
                     # We use 8080 because:
                     # 1. Port 80 requires root/admin privileges
                     # 2. 8080 is the convention for development HTTP servers
                     # 3. It's easy to remember (80 + 80 = "double 80")

BUFFER_SIZE = 4096   # How many bytes to read at once (4 KB)
                     # Why 4096? It's a common memory page size
                     # Too small = many recv() calls
                     # Too large = wasted memory

# =============================================================================
# STEP 1: CREATE THE SOCKET
# =============================================================================
# socket.socket(address_family, socket_type, protocol=0)
#
# address_family: What type of addresses we use
#   - socket.AF_INET   = IPv4 (e.g., 192.168.1.1)
#   - socket.AF_INET6  = IPv6 (e.g., 2001:db8::1)
#   - socket.AF_UNIX   = Unix domain sockets (local only, uses file paths)
#
# socket_type: What transport protocol to use
#   - socket.SOCK_STREAM = TCP (reliable, ordered, connection-based)
#   - socket.SOCK_DGRAM  = UDP (fast, unreliable, connectionless)
#   - socket.SOCK_RAW    = Raw IP packets (requires root)
#
# protocol: Usually 0 (auto-select based on type)
#   - IPPROTO_TCP for SOCK_STREAM
#   - IPPROTO_UDP for SOCK_DGRAM

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print(f"✓ Socket created")
print(f"  └─ Family: AF_INET (IPv4)")
print(f"  └─ Type: SOCK_STREAM (TCP)")

# =============================================================================
# STEP 1.5: SOCKET OPTIONS
# =============================================================================
# setsockopt(level, option, value)
#
# SO_REUSEADDR: Allows reusing the address immediately after closing
# 
# WHY IS THIS NEEDED?
# When you close a TCP connection, the OS keeps the socket in TIME_WAIT state
# for about 60 seconds (to handle any delayed packets from the old connection).
# Without SO_REUSEADDR, you'd get "Address already in use" error!
#
# Technical detail: TIME_WAIT prevents old packets from being misinterpreted
# as belonging to a new connection on the same port.

server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

print(f"✓ Socket options set")
print(f"  └─ SO_REUSEADDR: enabled (can restart server immediately)")

# =============================================================================
# STEP 2: BIND TO ADDRESS
# =============================================================================
# bind(address) assigns the socket to a specific network interface and port
#
# address is a tuple: (host, port)
#   - host: IP address or hostname
#   - port: Port number (0-65535)
#
# After bind(), this socket is associated with that address.
# No other socket can bind to the same address (unless SO_REUSEADDR is set).
#
# WHAT HAPPENS INTERNALLY:
# 1. OS checks if the port is available
# 2. OS associates this socket with the IP:Port in its internal tables
# 3. Any packets arriving at that IP:Port are routed to this socket

server_socket.bind((HOST, PORT))

print(f"✓ Socket bound to {HOST}:{PORT}")
print(f"  └─ Packets to {HOST}:{PORT} will be delivered to this socket")

# =============================================================================
# STEP 3: START LISTENING
# =============================================================================
# listen(backlog) puts the socket in listening state
#
# backlog: The maximum number of queued connections
#   - These are connections that have completed the TCP handshake
#   - But haven't been accepted by our code yet
#   - If the queue is full, new connections are REFUSED
#
# WHAT HAPPENS:
# 1. OS marks this socket as a "listening" socket
# 2. OS will now accept incoming TCP connections on this address
# 3. Completed connections go into the "accept queue"
# 4. Our accept() call pulls connections from this queue

server_socket.listen(5)

print(f"✓ Server is listening (backlog=5)")
print(f"  └─ Up to 5 connections can wait in queue")
print(f"")
print(f"╔══════════════════════════════════════════════════════════════╗")
print(f"║  🌐 Server running at: http://{HOST}:{PORT}                  ║")
print(f"║  Open this URL in your browser!                              ║")
print(f"║  Press Ctrl+C to stop the server                             ║")
print(f"╚══════════════════════════════════════════════════════════════╝")
print(f"")

# =============================================================================
# STEP 4: ACCEPT CONNECTIONS (The Main Loop)
# =============================================================================

while True:
    # accept() BLOCKS (the program pauses here) until a client connects
    #
    # WHAT HAPPENS WHEN A CLIENT CONNECTS:
    # 1. Client sends SYN packet (start of TCP handshake)
    # 2. OS responds with SYN-ACK
    # 3. Client sends ACK (handshake complete)
    # 4. OS puts the connection in the accept queue
    # 5. accept() returns with the new connection
    #
    # RETURNS:
    # - client_socket: A NEW socket for this specific connection
    #                  (The server socket continues listening!)
    # - client_address: Tuple of (client_ip, client_port)
    
    print("⏳ Waiting for a connection...")
    
    client_socket, client_address = server_socket.accept()
    
    print(f"")
    print(f"✓ NEW CONNECTION!")
    print(f"  └─ Client IP: {client_address[0]}")
    print(f"  └─ Client Port: {client_address[1]} (randomly assigned by client OS)")
    
    # =========================================================================
    # STEP 5: RECEIVE DATA FROM CLIENT
    # =========================================================================
    # recv(buffer_size) reads data from the socket
    #
    # IMPORTANT: recv() may NOT return all the data at once!
    # It returns AVAILABLE data up to buffer_size bytes.
    # For complete HTTP handling, we'd need to keep calling recv()
    # until we see the end of the request (more on this later).
    #
    # RETURNS: bytes object (NOT a string!)
    #
    # BLOCKING: recv() waits until data is available or connection closes
    
    raw_request = client_socket.recv(BUFFER_SIZE)
    
    # HTTP is text-based, so we decode bytes → string
    # UTF-8 is the standard encoding for modern HTTP
    request_text = raw_request.decode('utf-8')
    
    print(f"")
    print(f"📨 RECEIVED HTTP REQUEST ({len(raw_request)} bytes):")
    print(f"{'━' * 60}")
    print(request_text)
    print(f"{'━' * 60}")
    
    # =========================================================================
    # STEP 6: SEND RESPONSE TO CLIENT
    # =========================================================================
    # HTTP Response format (we'll parse this in detail in Step 2):
    #
    # Status-Line\r\n           ← "HTTP/1.1 200 OK"
    # Header1: Value1\r\n       ← "Content-Type: text/html"
    # Header2: Value2\r\n       ← "Content-Length: 123"
    # \r\n                      ← Empty line marks end of headers
    # Body                      ← The actual content
    #
    # \r\n = CRLF (Carriage Return + Line Feed)
    # This is REQUIRED by the HTTP specification (RFC 7230)
    # Windows uses \r\n for newlines, Unix uses \n
    # HTTP always uses \r\n regardless of OS
    
    html_body = "<html><body><h1>Hello World from Python!</h1></body></html>"
    
    http_response = (
        "HTTP/1.1 200 OK\r\n"                      # Status line
        "Content-Type: text/html; charset=utf-8\r\n"  # What kind of content
        f"Content-Length: {len(html_body)}\r\n"   # How many bytes in body
        "Connection: close\r\n"                    # We'll close after response
        "\r\n"                                     # Empty line = end of headers
        f"{html_body}"                             # The actual HTML
    )
    
    # send() transmits data through the socket
    # Must send bytes, not string, so we encode()
    # 
    # IMPORTANT: send() may not send ALL data at once!
    # It returns the number of bytes actually sent.
    # For production code, we'd use sendall() or loop until all sent.
    
    bytes_sent = client_socket.send(http_response.encode('utf-8'))
    
    print(f"")
    print(f"📤 SENT HTTP RESPONSE ({bytes_sent} bytes)")
    print(f"  └─ Status: 200 OK")
    print(f"  └─ Content-Type: text/html")
    print(f"  └─ Body: {len(html_body)} bytes")
    
    # =========================================================================
    # STEP 7: CLOSE THE CLIENT CONNECTION
    # =========================================================================
    # close() terminates this specific connection
    #
    # WHAT HAPPENS:
    # 1. Python sends FIN packet to client (TCP graceful close)
    # 2. Client acknowledges with ACK
    # 3. Client sends its own FIN
    # 4. We acknowledge with ACK
    # 5. Socket enters TIME_WAIT state (handled by OS)
    #
    # NOTE: The SERVER socket is NOT closed - it keeps listening!
    # We only close the connection socket for this specific client.
    
    client_socket.close()
    
    print(f"")
    print(f"✓ Connection closed")
    print(f"{'═' * 60}")
    print(f"")

