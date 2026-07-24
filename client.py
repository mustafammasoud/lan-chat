"""
LAN Chat Client
================
Connects to the chat server and sends/receives messages.

Idea:
- We run a separate Thread to receive messages, so we can receive and
  send at the same time (if we used only one thread, we'd either be
  stuck waiting to receive, or unable to type — not both at once).
- The main thread is responsible for reading what the user types and
  sending it to the server.

Note on language support:
Messages are sent/received as UTF-8 (see .encode("utf-8") / .decode("utf-8")
below). This means you can type your username or chat messages in
Arabic (or any other language) and they will work correctly —
no extra setup needed.
"""

import socket
import threading
import sys

BUFFER_SIZE = 1024


def receive_messages(client_socket: socket.socket):
    """
    Runs in its own Thread. Its only job: wait for messages from the
    server and print them to the screen as soon as they arrive.
    """
    while True:
        try:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                print("\n[!] Connection to the server was closed.")
                break
            print(f"\r{data.decode('utf-8')}\n> ", end="")
        except (ConnectionResetError, OSError):
            print("\n[!] Lost connection to the server.")
            break

    # If we exited the loop, the connection is dead — close the app
    client_socket.close()
    sys.exit(0)


def start_client():
    server_ip = input("Enter the server's IP (e.g. 192.168.1.10): ").strip()
    server_port = input("Enter the port (default 5555): ").strip()
    port = int(server_port) if server_port else 5555

    username = input("Enter your chat username: ").strip() or "Guest"

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect((server_ip, port))
    except (ConnectionRefusedError, OSError) as e:
        print(f"[!] Could not connect to the server: {e}")
        return

    # The first thing we send to the server is the username (part of our
    # simple hand-shake protocol)
    client_socket.sendall(username.encode("utf-8"))

    print(f"[+] Connected to server {server_ip}:{port} as '{username}'")
    print("Type your message and press Enter. Type 'exit' to leave.\n")

    # Run a background thread that continuously listens for incoming messages
    receive_thread = threading.Thread(
        target=receive_messages,
        args=(client_socket,),
        daemon=True
    )
    receive_thread.start()

    # The main thread keeps reading user input and sending it to the server
    try:
        while True:
            message = input("> ")
            if message.lower() == "exit":
                break
            if message.strip():
                client_socket.sendall(message.encode("utf-8"))
    except KeyboardInterrupt:
        pass
    finally:
        client_socket.close()
        print("[!] You left the chat.")


if __name__ == "__main__":
    start_client()
