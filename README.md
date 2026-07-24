# LAN Chat — Real-Time Terminal Chat Application

A multi-user, real-time text chat application built with **pure Python** (no external
libraries) using raw TCP sockets and threading. It follows a classic
**server-client architecture**: one server process routes messages between
multiple connected clients over a Local Area Network (LAN).

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Connecting Over a Local Network (LAN)](#connecting-over-a-local-network-lan)
- [How It Works Under the Hood](#how-it-works-under-the-hood)
  - [Sockets: the basic building block](#sockets-the-basic-building-block)
  - [Server architecture](#server-architecture)
  - [Concurrency: why threads are needed](#concurrency-why-threads-are-needed)
  - [Message routing (broadcast)](#message-routing-broadcast)
  - [The client-side design](#the-client-side-design)
  - [Wire protocol](#wire-protocol)
- [Known Limitations](#known-limitations)
- [Possible Improvements](#possible-improvements)

---

## Features

- Real-time multi-user text chat over TCP
- Broadcast messaging — every message is relayed to all connected clients
- Join/leave notifications
- Graceful handling of disconnects (crashes, closed terminals, network drops)
- No external dependencies — only Python's standard library (`socket`, `threading`, `time`, `hashlib`)
- Works on any machine on the same LAN (Wi-Fi or Ethernet)
- **Timestamps** — every message is tagged with the time it was sent, e.g. `[14:23:07]`
- **`/list` command** — see who's currently connected without leaving the chat
- **Per-user colors** — each username is consistently colorized in the terminal, making it easy to tell participants apart at a glance

---

## Language Support

The application's interface (prompts, logs, and instructions) is entirely in
English. However, all messages are transmitted using **UTF-8 encoding**
(`.encode("utf-8")` / `.decode("utf-8")`), which fully supports Arabic and
most other languages. This means usernames and chat messages can be typed
in Arabic (e.g. `أحمد`, `مرحبا بالجميع`) and they will be sent, routed, and
displayed correctly — no extra configuration required.

## Requirements

- Python 3.7+
- No `pip install` needed — everything used is part of the Python standard library

---

## Project Structure

```
lan-chat/
├── server.py    # The chat server: accepts connections, routes messages
├── client.py    # The chat client: connects to the server, sends/receives messages
└── README.md    # This file
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/mustafammasoud/lan-chat.git
cd lan-chat
```

### 2. Start the server

Run this on **one** machine — this machine will act as the chat hub:

```bash
python3 server.py
```

You'll see output like this:

```
==================================================
  Server running on port: 5555
  Connect from any device on the same network via: 192.168.1.10:5555
==================================================
```

Note the IP address printed — you'll need it in the next step. This is the
server machine's **local network IP**, not `127.0.0.1` (localhost only works
for connections from the same machine).

### 3. Start a client

On the **same machine** or **any other machine on the same LAN**, run:

```bash
python3 client.py
```

You'll be prompted for:

1. **Server IP** — the IP printed by the server (e.g. `192.168.1.10`)
2. **Server port** — default is `5555`, just press Enter to use it
3. **Your username**

Repeat this on as many machines/terminals as you like to add more chat
participants.

### 4. Chat!

Type a message and press `Enter` to broadcast it to everyone. Type `exit` to
leave the chat.

---

## Connecting Over a Local Network (LAN)

To connect from a **different physical machine** (not just multiple terminals
on the same machine), both machines must be on the **same network** (e.g. the
same Wi-Fi router or the same office/home LAN).

1. **Find the server machine's local IP address:**
   - Linux/macOS: `ifconfig` or `ip addr` → look for something like `192.168.x.x`
   - Windows: `ipconfig` → look for "IPv4 Address"
   - Or simply read it from the server's own startup log (it prints it
     automatically using `socket.gethostbyname(socket.gethostname())`).

2. **Make sure the port is not blocked by a firewall.** On Linux you can
   temporarily allow it with:
   ```bash
   sudo ufw allow 5555/tcp
   ```
   On Windows/macOS, you may get a firewall prompt the first time the server
   runs — allow it.

3. **On the other machine**, run `client.py` and enter the server's IP
   (e.g. `192.168.1.10`) and port `5555` when prompted.

4. Both machines must be on the same subnet — a phone on mobile data or a
   machine on a different Wi-Fi network **will not** be able to reach the
   server, since `192.168.x.x` addresses are private/local and not routable
   over the public internet.

---

## How It Works Under the Hood

### Sockets: the basic building block

A **socket** is an endpoint for network communication — think of it as a
"phone line" between two programs. This project uses:

- `AF_INET` — IPv4 addressing (an IP + a port number identifies each endpoint)
- `SOCK_STREAM` — TCP, a connection-oriented, reliable, ordered byte stream
  (as opposed to `SOCK_DGRAM`/UDP, which is connectionless and doesn't
  guarantee delivery or order — not suitable for a chat where message order
  matters)

The server side of a TCP conversation follows this exact sequence
(implemented in `server.py`'s `start_server()`):

```python
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))   # reserve this IP:port combination
server_socket.listen()             # start accepting incoming connections
client_socket, address = server_socket.accept()  # blocks until a client connects
```

- `bind()` reserves the address `(HOST, PORT)` so the OS routes any traffic
  sent to that address into this process.
- `listen()` puts the socket into a passive, "waiting for connections" state
  and sets up a backlog queue for incoming connection requests.
- `accept()` **blocks** (pauses execution) until a client actually connects,
  then returns a **brand new socket object** dedicated to that one client,
  plus their address. The original `server_socket` keeps listening for
  *more* incoming connections — this distinction (listening socket vs.
  per-connection socket) is the whole reason multiple clients can connect at
  once.

On the client side (`client.py`), it's simpler:

```python
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((server_ip, port))  # performs the TCP handshake
```

`connect()` performs the underlying TCP three-way handshake (SYN, SYN-ACK,
ACK) transparently — by the time it returns, a reliable bidirectional byte
stream exists between client and server.

### Server architecture

The server maintains a global list of connected clients:

```python
clients = []  # each entry: {"socket": ..., "username": ..., "address": ...}
clients_lock = threading.Lock()
```

Every time `accept()` returns a new client socket, the server spins up a
**dedicated thread** to handle that one client (`handle_client()`), then
immediately loops back to `accept()` to wait for the *next* client. This
means the main loop's only job is accepting connections; all actual message
handling happens in per-client threads.

### Concurrency: why threads are needed

`socket.recv()` is a **blocking call** — it pauses the calling thread until
data arrives (or the connection closes). If the server tried to `recv()`
from client A and client B sequentially on a single thread, it would get
stuck waiting on whichever client sent data second, freezing the whole
server for everyone else.

By giving each client its own `threading.Thread`, the server can block on
`recv()` for client A in one thread while simultaneously blocking on
`recv()` for client B in another — the OS scheduler interleaves them, and
from the user's perspective everything happens "at the same time."

**Race condition risk:** all these threads share the same `clients` list.
If two threads try to add/remove entries at the exact same moment, the list
can end up corrupted or an entry can go missing. That's what
`clients_lock` (a `threading.Lock`) is for — any code that reads or
modifies `clients` first acquires the lock (`with clients_lock:`), so only
one thread can touch the list at a time. This is a classic **mutual
exclusion** pattern.

### Message routing (broadcast)

When `handle_client()` receives a message from its client, it calls
`broadcast()`:

```python
def broadcast(message, sender_socket=None):
    with clients_lock:
        for client in clients:
            if client["socket"] is sender_socket:
                continue  # don't echo the message back to its sender
            client["socket"].sendall(message.encode("utf-8"))
```

This is the **routing logic**: the server doesn't try to figure out "who
should receive this" based on any addressing scheme — it simply relays
every incoming message to *every other* connected socket. This is the
simplest possible routing strategy (a "star topology" broadcast), suitable
for a single shared chat room. If a `send()` fails (e.g. `BrokenPipeError`),
that client is assumed disconnected and is cleaned up from the list.

### The client-side design

The client also needs to do two things at once: **listen for incoming
messages** and **read what the user types**. Since `recv()` blocks, the
client uses the same threading trick:

- The **main thread** loops on `input()`, reading what the user types and
  sending it to the server.
- A **background thread** (`receive_messages`) loops on `recv()`,
  printing anything the server sends, independently of what the main thread
  is doing.

This is what allows a user to receive a message from someone else while
they're still in the middle of typing their own.

### Timestamps

Timestamps are added in exactly **one place**: inside `broadcast()` on the
server. Every message that goes through `broadcast()` — chat messages, join
notices, leave notices — automatically gets prefixed with
`[HH:MM:SS]` (via `time.strftime('%H:%M:%S')`) before being sent out. This
keeps the timestamp logic centralized instead of repeating it everywhere a
message is built.

### The `/list` command

`/list` demonstrates a **direct reply** as opposed to a broadcast. When the
server receives a message from a client, it first checks whether that
message is a recognized command (currently just `/list`) before treating it
as a normal chat message:

```python
if message.strip() == "/list":
    send_user_list(client_socket)
    continue  # skip the normal broadcast below
```

`send_user_list()` sends the reply to **only** `client_socket` — the socket
of whoever asked — instead of looping over the whole `clients` list like
`broadcast()` does. This is the same underlying mechanism (`sendall()` on a
socket), just aimed at one recipient instead of many, which is the basis for
how a feature like private messaging would work too.

### Per-user colors (client-side)

Colors are handled entirely on the **client**, not the server — the server
has no concept of color, it just sends plain UTF-8 text. Each client
independently decides how to *display* incoming text:

1. `format_incoming()` splits a raw message like `[14:23:07] Ahmed: hi` into
   its timestamp and the rest.
2. If the rest starts with `**`, it's treated as a system message
   (join/leave/`/list` reply) and colored yellow.
3. Otherwise, it's treated as `username: message`. The username is hashed
   with `hashlib.md5()` and the hash is used to pick one color from a fixed
   palette (`% len(USERNAME_COLORS)`), so the **same username always maps to
   the same color** for the lifetime of that client session.
4. Colors are applied using **ANSI escape codes** — special character
   sequences like `\033[34m` that terminals interpret as "switch to this
   color" rather than printing visible characters. `\033[0m` resets back to
   the default color afterward.

Because coloring is purely a client-side display choice, different users
could theoretically see different colors for the same person (since each
client computes colors independently) — this doesn't affect the actual
message content or routing at all.

### Wire protocol

This project uses a minimal, informal protocol over the raw TCP byte
stream:

1. Immediately after connecting, the client sends **one message containing
   only their username** (UTF-8 encoded).
2. After that, every message the client sends is treated as a chat message
   and is broadcast as `"<username>: <message>"`.
3. The server never sends structured data (no JSON/length-prefixing) — it's
   plain UTF-8 text per `send()`/`recv()` call. This keeps the code simple
   but has the trade-off described below.

---

## Known Limitations

- **No message framing:** TCP is a *byte stream*, not a *message stream* —
  it does not guarantee that one `send()` call corresponds to exactly one
  `recv()` call on the other end. Under high load or large messages, two
  messages could theoretically arrive concatenated in a single `recv()`, or
  a single message could be split across two `recv()` calls. For a simple
  low-traffic LAN chat this is rarely an issue in practice, but a
  production-grade protocol would prefix each message with its length (or
  use a delimiter) to parse frames reliably. You can actually observe this:
  if a broadcast message and a `/list` reply arrive at a client back-to-back
  fast enough, a single `recv()` call can return both concatenated together.
- **No encryption:** messages are sent in plaintext. Fine for a trusted LAN
  demo; not suitable for sensitive data.
- **No authentication:** any client can claim any username.
- **Single chat room:** no support for private messages or multiple rooms.

## Possible Improvements

- Add length-prefixed framing for robust message parsing
- Add a simple web-based UI using WebSockets instead of raw TCP
- Add private messaging (`/msg <username> <text>`)
- Persist chat history to a file or database
- Add TLS for encrypted connections

---

## License

MIT
