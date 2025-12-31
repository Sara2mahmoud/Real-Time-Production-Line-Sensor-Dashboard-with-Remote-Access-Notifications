# Sensor Dashboard 

✅ This repository contains a simple sensor dashboard application with a built-in sensor simulator, TCP client, alarm manager, and notification handlers.

---

## Table of Contents

- **Overview**
- **Setup** ✅
- **Running the app** ▶️
- **Protocol Description** 🔧 (TCP)
- **API Documentation** 📚
- **Troubleshooting** ⚠️

---

## Overview

The application is a Tkinter-based dashboard that displays simulated sensor data, checks limits using an `AlarmManager`, and dispatches notifications via `NotificationManager`. The repository includes a TCP-based sensor simulator (`simulator.py`) and a TCP client (`tcp_client.py`) that receives newline-delimited JSON packets.

---

## Setup

**Requirements**
- Python 3.8+ (tested with 3.8–3.11)

Steps:

1. Clone the repo and change into the `app` directory:

   ```bash
   git clone <repo-url>
   cd app
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

---

## Running the app

Start the GUI dashboard (this will automatically start an in-process sensor simulator if a free port is available):

```bash
python APP.py
```

Notes:
- The app finds a free TCP port (preferred 9000) and launches the simulator thread automatically.
- If you prefer to run the simulator in a separate process, start it manually:

```bash
python simulator.py [port]
```

Then run `APP.py` (or use an external client) and point it to the simulator port.

---

## Protocol Description (Transport & Message Format)

### TCP (Implemented)
- Transport: TCP (IPv4), client connects to the simulator server socket.
- Framing: newline-delimited JSON messages (UTF-8). Each message ends with `\n`.
- Update rate (simulator): ~2 updates per second per sensor (0.5s delay between sends inside loop).

Message fields (example):

```json
{"sensor": "TEMP_1", "value": 42.37, "timestamp": "2025-12-31 23:59:59", "status": "OK"}
```

Field descriptions:
- `sensor` (string): sensor ID (e.g., `TEMP_1`, `PRESS_1`)
- `value` (number): numeric sensor value (rounded to 2 decimals in the simulator)
- `timestamp` (string): human-readable timestamp (YYYY-MM-DD HH:MM:SS)
- `status` (string): `OK` or `FAULT`

Client behavior (implemented by `SensorClient`):
- Connect to host:port
- Receive bytes, split on `\n` boundaries, parse each JSON object, and push to an internal queue for the GUI to process
- On connection loss, retry with a backoff

## API Documentation

This section documents the main modules/classes/functions used in the project.

### `simulator.py`
- `start_simulator(host='127.0.0.1', port=9000, stop_event=None)`
  - Starts a TCP server that sends periodic sensor packets. Can be run in a separate process or as a thread inside the app. Returns 0 on clean exit.
  - Command-line usage: `python simulator.py [port]`

### `tcp_client.py`
- `class SensorClient(threading.Thread)`
  - `SensorClient(host, port, data_queue)` — connect to server and push parsed packets into `data_queue`
  - `start()` — inherit from `Thread.start()` to run background reader
  - `stop()` — signal to stop and close the socket

Packet format: newline-delimited JSON objects (see Protocol section)

### `alarms/alarm_manager.py`
- `class AlarmManager`
  - `AlarmManager(sensor_limits, notifier=None)` — create manager with sensor limits dict and optional notifier
  - `check(packet)` — evaluate a packet and return an alarm dict if a limit/status breach occurs

Alarm dict fields: `time`, `sensor`, `value`, `type` (e.g., `LOW_LIMIT`, `HIGH_LIMIT`, `SENSOR_FAULT`)

### `notifications.py`
- `class NotificationManager`
  - `add_notifier(notifier)` / `remove_notifier(notifier)`
  - `notify(alarm)` — asynchronous dispatch to registered notifiers
  - `send_test()` — send a `TEST` alarm to demonstrate flow

- `class DesktopNotifier` — shows messagebox popups (via Tkinter)
- `class WebhookNotifier(url)` — posts alarm JSON to provided URL

### `APP.py` (GUI)
- `SensorDashboard(data_queue, alarm_manager, client)` — main Tkinter GUI that consumes `data_queue` and shows sensor values and alarms
- `find_free_port(preferred=9000, host='127.0.0.1')` — helper to pick an available port
- `main()` — starts GUI, simulator, and TCP client

---

## Troubleshooting

- If the simulator fails to start: check for port conflicts or firewall rules. The app tries to find a free port by default.
- If no data appears: confirm the client is connected to the same host/port where the simulator is listening.
- Notifications failing: webhook network errors are logged; desktop notifications fall back to console messages if GUI popups fail.

---
"# Real-Time-Production-Line-Sensor-Dashboard-with-Remote-Access-Notifications" 
