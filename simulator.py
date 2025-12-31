import socket
import json
import time
import random
from datetime import datetime

HOST = "127.0.0.1"
PORT = 9000
import sys
# Allow overriding port via command-line argument (used when launched as subprocess)
if len(sys.argv) > 1:
    try:
        PORT = int(sys.argv[1])
    except ValueError:
        pass

SENSORS = {
    "TEMP_1": {"low": 20, "high": 80},
    "TEMP_2": {"low": 25, "high": 75},
    "PRESS_1": {"low": 1.0, "high": 5.0},
    "VIB_1": {"low": 0.1, "high": 3.0},
    "SPEED_1": {"low": 500, "high": 1500},
}

def generate_sensor_value(sensor):
    limits = SENSORS[sensor]
    value = random.uniform(limits["low"], limits["high"])

    # 10% chance to exceed limits
    if random.random() < 0.1:
        value *= random.choice([0.5, 1.5])

    # 5% chance sensor is faulty
    status = "OK"
    if random.random() < 0.05:
        status = "FAULT"

    return value, status


def start_simulator(host=HOST, port=PORT, stop_event=None):
    """Run the simulator server in the current process. If stop_event (threading.Event) is provided,
    the server will exit when stop_event.is_set() is True. Returns 0 on clean exit, 1 on bind failure.
    """
    import threading
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
    except OSError as e:
        print(f"[SIMULATOR] Failed to bind {host}:{port}: {e}")
        server.close()
        return 1
    server.listen(1)
    server.settimeout(1.0)

    print(f"[SIMULATOR] Listening on {host}:{port}")

    if stop_event is None:
        stop_event = threading.Event()

    try:
        while not stop_event.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue

            print(f"[SIMULATOR] Client connected from {addr}")
            conn.settimeout(1.0)

            try:
                while not stop_event.is_set():
                    for sensor in SENSORS:
                        value, status = generate_sensor_value(sensor)

                        packet = {
                            "sensor": sensor,
                            "value": round(value, 2),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "status": status
                        }

                        message = json.dumps(packet) + "\n"
                        try:
                            conn.sendall(message.encode())
                        except (BrokenPipeError, OSError):
                            # client disconnected
                            break

                        if stop_event.is_set():
                            break

                        time.sleep(0.5)  # 2 updates per second

                    # loop will restart to check stop_event or accept new client
                    if stop_event.is_set():
                        break

            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    finally:
        server.close()

    return 0


if __name__ == "__main__":
    import threading
    stop_ev = threading.Event()
    try:
        start_simulator(HOST, PORT, stop_ev)
    except KeyboardInterrupt:
        stop_ev.set()
        print("[SIMULATOR] Exiting")