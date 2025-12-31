
import socket
import threading
import json
import queue
import time


class SensorClient(threading.Thread):
    def __init__(self, host, port, data_queue):
        super().__init__()
        self.host = host
        self.port = port
        self.data_queue = data_queue
        self.running = True
        self.sock = None

    def run(self):
        """Main worker thread function with reconnect logic"""
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    self.sock = sock

                    # Try to connect; if simulator not ready, this will raise and we'll retry
                    sock.settimeout(5)
                    sock.connect((self.host, self.port))
                    sock.settimeout(None)
                    print("[CLIENT] Connected to sensor simulator")

                    buffer = ""

                    while self.running:
                        data = sock.recv(1024).decode()
                        if not data:
                            # Connection closed by server
                            raise ConnectionError("Socket closed by server")

                        buffer += data

                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            packet = json.loads(line)

                            # Send parsed data safely to main thread
                            self.data_queue.put(packet)

            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Error: {e}. Retrying in 1s...")
                    self.sock = None
                    time.sleep(1)
                else:
                    break

    def stop(self):
        self.running = False
        # Close socket if open
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass