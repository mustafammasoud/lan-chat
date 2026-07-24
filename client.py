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
import hashlib

BUFFER_SIZE = 1024

# ---------------------------------------------------------
# Terminal colors (ANSI escape codes)
# ---------------------------------------------------------
# These are special character sequences that most terminals interpret
# as "change text color" instead of printing visible characters.
# \033 is the ESC character; [3<n>m selects a foreground color.
RESET = "\033[0m"
DIM = "\033[2m"
SYSTEM_COLOR = "\033[33m"  # yellow, used for join/leave/system messages

# A small palette of distinct colors to assign to usernames
USERNAME_COLORS = [
    "\033[31m",  # red
    "\033[32m",  # green
    "\033[34m",  # blue
    "\033[35m",  # magenta
    "\033[36m",  # cyan
    "\033[91m",  # bright red
    "\033[92m",  # bright green
    "\033[94m",  # bright blue
]


def color_for_username(name: str) -> str:
    """
    Picks a color for a given username. The same username always maps
    to the same color, because we base the choice on a hash of the
    name itself rather than on arrival order (which could change).

    We use MD5 here purely as a fast, well-distributed hash function
    (NOT for any security purpose) — it spreads different names across
    the color palette much more evenly than a simple sum of character
    codes would, which reduces (but never fully eliminates) the chance
    of two different usernames landing on the same color.
    """
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(USERNAME_COLORS)
    return USERNAME_COLORS[index]


def format_incoming(raw_message: str) -> str:
    """
    Takes a raw message as sent by the server (e.g.
    "[14:23:07] Ahmed: hello there" or "[14:23:07] ** Ahmed joined **")
    and returns a colorized version for display.
    """
    # Split off the "[HH:MM:SS] " timestamp prefix, if present
    if raw_message.startswith("[") and "] " in raw_message:
        timestamp, _, rest = raw_message.partition("] ")
        timestamp += "]"
    else:
        timestamp, rest = "", raw_message

    # System messages (join/leave/user list) are wrapped in "** ... **"
    if rest.startswith("**"):
        return f"{DIM}{timestamp}{RESET} {SYSTEM_COLOR}{rest}{RESET}"

    # Regular chat messages look like "username: message text"
    if ": " in rest:
        name, _, text = rest.partition(": ")
        color = color_for_username(name)
        return f"{DIM}{timestamp}{RESET} {color}{name}{RESET}: {text}"

    # Fallback: anything that doesn't match the expected shape
    return f"{DIM}{timestamp}{RESET} {rest}"


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
            formatted = format_incoming(data.decode("utf-8"))
            print(f"\r{formatted}\n> ", end="")
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
    print("Type your message and press Enter.")
    print("Commands: '/list' shows connected users, 'exit' leaves the chat.\n")

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