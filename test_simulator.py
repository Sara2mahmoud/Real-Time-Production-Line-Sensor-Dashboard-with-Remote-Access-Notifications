import socket
import json
import threading
import time

from simulator import start_simulator, SENSORS


def run_simulator_test():
    HOST = "127.0.0.1"
    PORT = 9100

    print("\n[TEST] Starting sensor simulator...")
    stop_event = threading.Event()

    sim_thread = threading.Thread(
        target=start_simulator,
        args=(HOST, PORT, stop_event),
        daemon=True
    )
    sim_thread.start()

    time.sleep(0.5)

    print("[TEST] Connecting to simulator...")
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2.0)
        client.connect((HOST, PORT))
        print("[OK] Connected successfully")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        stop_event.set()
        return

    print("[TEST] Waiting for sensor data...")
    try:
        data = client.recv(1024).decode().strip()
        print("[OK] Data received")
        print("[RAW DATA]", data)
    except Exception as e:
        print(f"[ERROR] Failed to receive data: {e}")
        client.close()
        stop_event.set()
        return

    print("[TEST] Parsing JSON...")
    try:
        packet = json.loads(data)
        print("[OK] JSON parsed successfully")
        print("[PACKET]", packet)
    except Exception as e:
        print(f"[ERROR] Invalid JSON: {e}")
        client.close()
        stop_event.set()
        return

    print("[TEST] Checking packet fields...")

    required_fields = ["sensor", "value", "timestamp", "status"]
    for field in required_fields:
        if field in packet:
            print(f"[OK] Field '{field}' exists")
        else:
            print(f"[ERROR] Field '{field}' is missing")

    sensor = packet.get("sensor")
    if sensor in SENSORS:
        print(f"[OK] Sensor name '{sensor}' is valid")
    else:
        print(f"[WARNING] Unknown sensor name: {sensor}")

    print("[TEST] Cleaning up...")
    client.close()
    stop_event.set()
    sim_thread.join(timeout=1)

    print("[TEST] Simulator test finished\n")


if __name__ == "__main__":
    run_simulator_test()
