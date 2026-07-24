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

# ---------------------------------------------------------
# Server configuration
# ---------------------------------------------------------
HOST = "0.0.0.0"   # 0.0.0.0 means: listen on every network interface on this
                    # machine (not just localhost), so other devices on the
                    # same LAN can reach this server
PORT = 5555         # The port number the server will run on

clients = []


clients_lock = threading.Lock()


def broadcast(message: str, sender_socket=None):

    encoded = message.encode("utf-8")

    with clients_lock:
        dead_clients = []
        for client in clients:
            if client["socket"] is sender_socket:
                continue  
            try:
                client["socket"].sendall(encoded)
            except (BrokenPipeError, ConnectionResetError, OSError):
                dead_clients.append(client)

        for dead in dead_clients:
            if dead in clients:
                clients.remove(dead)


def handle_client(client_socket: socket.socket, address):

    username = None
    try:
        username = client_socket.recv(1024).decode("utf-8").strip()
        if not username:
            username = f"User-{address[1]}" 

        with clients_lock:
            clients.append({"socket": client_socket, "username": username, "address": address})

        print(f"[+] {username} connected from {address}")
        broadcast(f"** {username} joined the chat **", sender_socket=client_socket)

        while True:
            data = client_socket.recv(1024)
            if not data:
                break

            message = data.decode("utf-8")
            print(f"[{username}] {message}")
            broadcast(f"{username}: {message}", sender_socket=client_socket)

    except (ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        with clients_lock:
            clients[:] = [c for c in clients if c["socket"] is not client_socket]

        client_socket.close()
        if username:
            print(f"[-] {username} left the chat")
            broadcast(f"** {username} left the chat **")


def start_server():
   
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))  
    server_socket.listen()             
    local_ip = socket.gethostbyname(socket.gethostname())

    print("=" * 50)
    print(f"  Server running on port: {PORT}")
    print(f"  Connect from any device on the same network via: {local_ip}:{PORT}")
    print("=" * 50)

    try:
        while True:
            
            client_socket, address = server_socket.accept()


            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, address),
                daemon=True 
            )
            thread.start()
    except KeyboardInterrupt:
        print("\n[!] Shutting down the server...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()
