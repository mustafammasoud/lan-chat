"""
LAN Chat Server
================
A simple chat server that runs over a Local Area Network (LAN).

Core idea:
- The server opens a "socket" (a connection endpoint) and waits for
  clients to connect to it.
- Each connected client gets its own dedicated Thread, so the server
  can handle multiple clients at the same time without "blocking"
  (i.e. getting stuck on one client while everyone else waits).
- Whenever a message arrives from one client, the server "Broadcasts"
  it: relays it to all other connected clients.

Note on language support:
All text is read/sent as UTF-8 (see the .encode("utf-8") / .decode("utf-8")
calls below). UTF-8 covers Arabic, English, and virtually any other
language's characters, so users can type usernames and chat messages
in Arabic (or any language) and they will be transmitted and displayed
correctly — nothing extra is needed for that to work.
"""

import socket
import threading
import time

# ---------------------------------------------------------
# Server configuration
# ---------------------------------------------------------
HOST = "0.0.0.0"   # 0.0.0.0 means: listen on every network interface on this
                    # machine (not just localhost), so other devices on the
                    # same LAN can reach this server
PORT = 5555         # The port number the server will run on

# List of all clients currently connected
# Each entry is a dict holding the socket, username, and address
clients = []

# Lock used to protect the `clients` list from race conditions.
# If multiple threads tried to modify the list at the exact same
# moment, the list's data could get corrupted.
clients_lock = threading.Lock()


def broadcast(message: str, sender_socket=None):
    """
    Sends a message to every connected client, optionally skipping
    the client that sent it.

    Parameters:
        message (str): the message to send
        sender_socket: the socket of whoever sent the message
                        (so we don't echo it back to them)
    """
    # Prefix every broadcasted message with a timestamp, e.g. "[14:23:07]".
    # We do this here (in one single place) so every message that goes
    # through broadcast() — chat messages, join notices, leave notices —
    # automatically gets a timestamp, instead of repeating this logic
    # everywhere a message is constructed.
    timestamped = f"[{time.strftime('%H:%M:%S')}] {message}"
    encoded = timestamped.encode("utf-8")

    # Take the lock before touching the shared `clients` list, since
    # another thread could be reading/modifying it at the same time.
    with clients_lock:
        dead_clients = []
        for client in clients:
            if client["socket"] is sender_socket:
                continue  # don't send the message back to its own sender
            try:
                client["socket"].sendall(encoded)
            except (BrokenPipeError, ConnectionResetError, OSError):
                # If sending failed, this client's connection is dead
                dead_clients.append(client)

        # Remove any clients whose connection turned out to be dead
        for dead in dead_clients:
            if dead in clients:
                clients.remove(dead)


def send_user_list(requester_socket: socket.socket):
    """
    Replies to a single client (the one who asked) with the list of
    currently connected usernames. Unlike broadcast(), this sends to
    ONE socket only — it's a direct reply, not a relay to everyone.
    """
    with clients_lock:
        names = [c["username"] for c in clients]

    reply = "** Connected users: " + ", ".join(names) + " **"
    try:
        requester_socket.sendall(f"[{time.strftime('%H:%M:%S')}] {reply}".encode("utf-8"))
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass  # the requester disconnected right as we tried to reply


def handle_client(client_socket: socket.socket, address):
    """
    Runs in its own Thread for each connected client.
    Responsible for: receiving messages from this client and
    broadcasting them to everyone else.

    Parameters:
        client_socket: the socket for this specific client's connection
        address: the client's IP and port (provided automatically by accept())
    """
    username = None
    try:
        # The first message from a client is always their username
        # (this is a simple convention agreed between server and client)
        username = client_socket.recv(1024).decode("utf-8").strip()
        if not username:
            username = f"User-{address[1]}"  # fallback if no name was sent

        # Add this client to the list of connected clients
        with clients_lock:
            clients.append({"socket": client_socket, "username": username, "address": address})

        print(f"[+] {username} connected from {address}")
        broadcast(f"** {username} joined the chat **", sender_socket=client_socket)

        # Keep receiving messages from this client for as long as they're connected
        while True:
            data = client_socket.recv(1024)
            if not data:
                # An empty recv() means the client closed the connection
                break

            message = data.decode("utf-8")
            print(f"[{username}] {message}")

            # Commands start with "/" and are handled specially — they are
            # NOT broadcast to everyone, only answered directly to the
            # client that sent them.
            if message.strip() == "/list":
                send_user_list(client_socket)
                continue  # skip the normal broadcast below

            broadcast(f"{username}: {message}", sender_socket=client_socket)

    except (ConnectionResetError, ConnectionAbortedError):
        # The client closed abruptly or the network connection dropped
        pass
    finally:
        # No matter what happened (error or normal exit), clean up after this client
        with clients_lock:
            clients[:] = [c for c in clients if c["socket"] is not client_socket]

        client_socket.close()
        if username:
            print(f"[-] {username} left the chat")
            broadcast(f"** {username} left the chat **")


def start_server():
    """
    Builds the main server socket and makes it wait for incoming connections.
    """
    # AF_INET  = use IPv4
    # SOCK_STREAM = use TCP (a reliable protocol that preserves message order)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Lets us restart the server quickly without an "Address already in use" error
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))   # reserve this address and port
    server_socket.listen()             # start listening for incoming connections

    # Get this machine's actual LAN IP address to show the user
    local_ip = socket.gethostbyname(socket.gethostname())

    print("=" * 50)
    print(f"  Server running on port: {PORT}")
    print(f"  Connect from any device on the same network via: {local_ip}:{PORT}")
    print("=" * 50)

    try:
        while True:
            # accept() blocks until a new client connects, then returns
            # a brand new socket dedicated to that connection, plus its address
            client_socket, address = server_socket.accept()

            # Spin up a dedicated thread for this client, so the server
            # stays free to accept other clients at the same time
            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, address),
                daemon=True  # daemon=True means this thread auto-exits when the program exits
            )
            thread.start()
    except KeyboardInterrupt:
        print("\n[!] Shutting down the server...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()