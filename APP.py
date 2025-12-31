import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
from tkinter import scrolledtext
import queue
import threading
import time
from datetime import datetime
from tcp_client import SensorClient
from alarms.alarm_manager import AlarmManager
from notifications import NotificationManager, DesktopNotifier, WebhookNotifier
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import subprocess
import sys
import os
import socket

SENSOR_LIMITS = {
    "TEMP_1": {"low": 20, "high": 80},
    "TEMP_2": {"low": 25, "high": 75},
    "PRESS_1": {"low": 1.0, "high": 5.0},
    "VIB_1": {"low": 0.1, "high": 3.0},
    "SPEED_1": {"low": 500, "high": 1500},
}

SENSOR_COLORS = {
    "OK": "#b6fcd5",
    "WARN": "#fff59d",
    "ALARM": "#ff8a80"
}


def find_free_port(preferred=9000, host='127.0.0.1'):
    """Try to use the preferred port if available, otherwise return an ephemeral free port.
    Returns the chosen port number or None if binding was not possible (e.g., permissions/firewall)."""
    # First try preferred port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, preferred))
        s.close()
        return preferred
    except OSError:
        try:
            # Let OS pick an ephemeral port
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.bind((host, 0))
            port = s2.getsockname()[1]
            s2.close()
            return port
        except OSError:
            return None

class SensorDashboard(tk.Tk):
    def __init__(self, data_queue, alarm_manager, client):
        super().__init__()
        self.title("Sensor Dashboard")
        self.geometry("1100x700")
        self.data_queue = data_queue
        self.client = client

        # Notification manager: add desktop notifier by default
        self.notification_manager = NotificationManager(log_callback=lambda m: self.log_queue.put(m))
        self.notification_manager.add_notifier(DesktopNotifier())

        # Attach notification manager to alarm manager
        self.alarm_manager = alarm_manager
        self.alarm_manager.notifier = self.notification_manager
        self.sensor_data = {}
        self.sensor_history = {}
        self.max_history = 200

        # --- Notebook for tabs ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # --- Dashboard Tab ---
        self.dashboard_frame = tk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="Dashboard")

        # --- Scrollable main area ---
        self.canvas = tk.Canvas(self.dashboard_frame, borderwidth=0, background="#f0f0f0")
        self.v_scroll = tk.Scrollbar(self.dashboard_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)
        self.v_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner_frame = tk.Frame(self.canvas, background="#f0f0f0")
        self.inner_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        def _on_canvas_configure(event):
            # Update the inner_frame's width to match the canvas width
            canvas_width = event.width
            self.canvas.itemconfig(self.inner_window, width=canvas_width)

        self.canvas.bind("<Configure>", _on_canvas_configure)

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # --- Content inside inner_frame ---

        # 1. Status label and sensor table (row 0)
        top_frame = tk.Frame(self.inner_frame)
        top_frame.grid(row=0, column=0, sticky="nsew")
        self.inner_frame.grid_rowconfigure(0, weight=1)
        self.inner_frame.grid_columnconfigure(0, weight=1)

        self.status_label = tk.Label(top_frame, text="System Status: OK", font=("Arial", 16), bg="#b6fcd5")
        self.status_label.pack(fill=tk.X, pady=5)

        columns = ("sensor", "value", "timestamp", "status")
        self.tree = ttk.Treeview(top_frame, columns=columns, show="headings", height=8)
        for col in columns:
            self.tree.heading(col, text=col)
        # Table
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10)

        # 2. Plots (row 1)
        self.plot_frame = tk.Frame(self.inner_frame)
        self.plot_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=2)
        self.inner_frame.grid_rowconfigure(1, weight=1)

        self.figures = {}
        self.canvases = {}
        col = 0
        for sensor in SENSOR_LIMITS:
            fig = Figure(figsize=(4, 4), dpi=80)
            ax = fig.add_subplot(111)
            ax.set_title(sensor)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Value")
            self.figures[sensor] = (fig, ax)
            canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            widget = canvas.get_tk_widget()
            # Plots
            widget.grid(row=0, column=col, padx=5, pady=2, sticky="nsew")
            self.plot_frame.grid_columnconfigure(col, weight=1)
            self.canvases[sensor] = canvas
            col += 1
        self.plot_frame.grid_rowconfigure(0, weight=1)

        # 3. Alarm log (row 2)
        log_frame = tk.Frame(self.inner_frame)
        log_frame.grid(row=2, column=0, sticky="nsew")
        self.inner_frame.grid_rowconfigure(2, weight=1)

        self.log_columns = ("time", "sensor", "value", "type")
        self.log_table = ttk.Treeview(log_frame, columns=self.log_columns, show="headings", height=8)
        for col in self.log_columns:
            self.log_table.heading(col, text=col.capitalize())
        # Alarm log
        self.log_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_table.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_table.configure(yscrollcommand=log_scrollbar.set)

        self.sensor_rows = {}

        self.tree.tag_configure("OK", background="#b6fcd5")
        self.tree.tag_configure("WARN", background="#fff59d")
        self.tree.tag_configure("ALARM", background="#ff8a80")

        # After creating self.inner_frame
        for i in range(3):
            self.inner_frame.grid_rowconfigure(i, weight=1)
        self.inner_frame.grid_columnconfigure(0, weight=1)

        self.after(100, self.update_gui)

        # --- Maintenance Console Tab ---
        self.maintenance_frame = tk.Frame(self.notebook)
        self.notebook.add(self.maintenance_frame, text="Maintenance Console")

        # Access Control
        self.maintenance_locked = True
        self.maintenance_password = "admin123"  # Change as needed

        self.lock_frame = tk.Frame(self.maintenance_frame)
        self.lock_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.lock_frame, text="Enter password to access Maintenance Console:").pack(pady=10)
        self.pw_entry = tk.Entry(self.lock_frame, show="*")
        self.pw_entry.pack()
        tk.Button(self.lock_frame, text="Unlock", command=self.unlock_maintenance).pack(pady=5)

        # Maintenance content (hidden until unlocked)
        self.maintenance_content = tk.Frame(self.maintenance_frame)

        # Live Log Viewer
        tk.Label(self.maintenance_content, text="Live Log Viewer", font=("Arial", 12, "bold")).pack()
        self.log_viewer = scrolledtext.ScrolledText(self.maintenance_content, height=12, state="disabled")
        self.log_viewer.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Remote Commands
        tk.Label(self.maintenance_content, text="Remote Commands", font=("Arial", 12, "bold")).pack(pady=(10,0))
        cmd_frame = tk.Frame(self.maintenance_content)
        cmd_frame.pack(pady=5)
        tk.Button(cmd_frame, text="Restart Sensor Simulator", command=self.restart_simulator).pack(side=tk.LEFT, padx=5)
        tk.Button(cmd_frame, text="Request Detailed Snapshot", command=self.request_snapshot).pack(side=tk.LEFT, padx=5)
        tk.Button(cmd_frame, text="Send Test Notification", command=lambda: self.send_test_notification()).pack(side=tk.LEFT, padx=5)
        tk.Button(cmd_frame, text="Clear Alarms", command=self.clear_alarms).pack(side=tk.LEFT, padx=5)

        # (Bonus) Event Streaming Placeholder
        tk.Label(self.maintenance_content, text="Event Streaming (WebSocket feed placeholder)", fg="gray").pack(pady=10)

        # Start background log thread
        self.log_queue = queue.Queue()
        self.log_thread = threading.Thread(target=self.background_log_collector, daemon=True)
        self.log_thread.start()
        self.after(500, self.update_log_viewer)

        self.simulator_thread = None
        self.simulator_stop_event = None
        # Choose a port for the simulator and start it
        self.simulator_port = find_free_port(9000)
        if self.simulator_port is None:
            messagebox.showerror("Simulator Error", "No available port could be bound for simulator. Check firewall/permissions.")
        else:
            self.start_simulator_process(self.simulator_port)

    def start_simulator_process(self, port=None):
        # Start the simulator in-process (thread) on the given port by importing simulator.start_simulator
        if self.simulator_thread and self.simulator_thread.is_alive():
            return  # Already running
        if port is None:
            port = getattr(self, "simulator_port", 9000)
        try:
            import simulator
        except Exception as e:
            messagebox.showerror("Simulator Error", f"Failed to import simulator module: {e}")
            return
        self.simulator_stop_event = threading.Event()
        self.simulator_thread = threading.Thread(
            target=simulator.start_simulator,
            args=("127.0.0.1", port, self.simulator_stop_event),
            daemon=True
        )
        self.simulator_thread.start()
        # brief wait to detect immediate failure
        #time.sleep(0.2)
        if not self.simulator_thread.is_alive():
            messagebox.showerror("Simulator Error", f"Simulator thread failed to start on port {port}. Check port/firewall.")
        print(f"[APP] Started simulator thread on port {port}")

    def stop_simulator_process(self):
        # Stop simulator thread if running
        if self.simulator_thread and self.simulator_thread.is_alive():
            self.simulator_stop_event.set()
            self.simulator_thread.join(timeout=5)
            if self.simulator_thread and self.simulator_thread.is_alive():
                print("[APP] Simulator thread did not stop within timeout")
            self.simulator_thread = None
            self.simulator_stop_event = None

    def unlock_maintenance(self):
        if self.pw_entry.get() == self.maintenance_password:
            self.lock_frame.pack_forget()
            self.maintenance_content.pack(fill=tk.BOTH, expand=True)
            self.maintenance_locked = False
        else:
            messagebox.showerror("Access Denied", "Incorrect password!")

    # --- Remote Command Handlers ---
    def restart_simulator(self):
        self.log_queue.put("Simulator restart initiated by user.")

        # Stop the simulator thread
        self.stop_simulator_process()
        time.sleep(1)  # Wait briefly before clearing and restarting

        # --- Clear application state ---
        # Clear any pending incoming sensor packets
        try:
            while not self.data_queue.empty():
                self.data_queue.get_nowait()
        except Exception:
            pass

        # Clear sensor data and history
        self.sensor_data.clear()
        self.sensor_history.clear()

        # Remove sensor rows from the tree view
        try:
            for iid in list(self.sensor_rows.values()):
                try:
                    self.tree.delete(iid)
                except Exception:
                    pass
        finally:
            self.sensor_rows.clear()

        # Clear alarms and alarm log
        try:
            self.alarm_manager.active_alarms.clear()
        except Exception:
            pass
        for item in self.log_table.get_children():
            self.log_table.delete(item)

        # Clear log queue and log viewer
        try:
            while not self.log_queue.empty():
                self.log_queue.get_nowait()
            self.log_viewer.config(state="normal")
            self.log_viewer.delete("1.0", tk.END)
            self.log_viewer.config(state="disabled")
        except Exception:
            pass

        # Reset UI status and plots
        self.status_label.config(text="System Status: OK", bg=SENSOR_COLORS["OK"])
        for sensor, (fig, ax) in self.figures.items():
            ax.clear()
            ax.set_title(sensor)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Value")
            self.canvases[sensor].draw()

        # Restart with the same port (or pick one if missing)
        if getattr(self, "simulator_port", None) is None:
            self.simulator_port = find_free_port(9000)
            if self.simulator_port is None:
                self.log_queue.put("Failed to restart simulator: no available port.")
                messagebox.showerror("Simulator Error", "Failed to restart simulator: no available port.")
                return

        self.start_simulator_process(self.simulator_port)
        self.log_queue.put("Simulator restarted and state cleared by user.")

    def request_snapshot(self):
        """
        Gather the current sensor values and display them in a popup window.
        """
        if not self.sensor_data:
            messagebox.showinfo("Snapshot", "No sensor data available yet.")
            return

        snapshot_window = tk.Toplevel(self)
        snapshot_window.title("Detailed Sensor Snapshot")
        snapshot_window.geometry("500x300")

        columns = ("sensor", "value", "timestamp", "status")
        tree = ttk.Treeview(snapshot_window, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col.capitalize())
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Insert current sensor data
        for sensor, data in self.sensor_data.items():
            tree.insert("", "end", values=(
                sensor, data["value"], data["timestamp"], data["status"]
            ))

        # Add a close button
        tk.Button(snapshot_window, text="Close", command=snapshot_window.destroy).pack(pady=5)

    def send_test_notification(self):
        if hasattr(self, "notification_manager"):
            alarm = self.notification_manager.send_test()
            self.log_queue.put(f"Test notification queued: {alarm}")
        else:
            messagebox.showwarning("Notifications", "Notification manager not configured.")

    def clear_alarms(self):
        self.log_queue.put("Alarms cleared by user.")
        self.alarm_manager.active_alarms.clear()
        # Clear the alarm log table
        for item in self.log_table.get_children():
            self.log_table.delete(item)

    # --- Background Log Collector Example ---
    def background_log_collector(self):
        import random, time
        while True:
            # Simulate log messages
            msg = f"[{datetime.now().strftime('%H:%M:%S')}] System log entry {random.randint(1,100)}"
            self.log_queue.put(msg)
            time.sleep(2)

    def update_log_viewer(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_viewer.config(state="normal")
            self.log_viewer.insert(tk.END, msg + "\n")
            self.log_viewer.see(tk.END)
            self.log_viewer.config(state="disabled")
        self.after(500, self.update_log_viewer)

    def update_gui(self):
        global_status = "OK"
        global_color = SENSOR_COLORS["OK"]

        try:
            while True:
                packet = self.data_queue.get_nowait()
                sensor = packet["sensor"]
                value = packet["value"]
                status = packet["status"]
                timestamp = datetime.now().strftime("%H:%M:%S")

                alarm = self.alarm_manager.check(packet)

                # Determine status color
                if status == "FAULT":
                    row_status = "ALARM"
                else:
                    limits = SENSOR_LIMITS[sensor]
                    if value < limits["low"] or value > limits["high"]:
                        row_status = "ALARM"
                    elif (value - limits["low"] < 5) or (limits["high"] - value < 5):
                        row_status = "WARN"
                    else:
                        row_status = "OK"

                # Update global status
                if row_status == "ALARM":
                    global_status = "ALARM"
                    global_color = SENSOR_COLORS["ALARM"]
                elif row_status == "WARN" and global_status != "ALARM":
                    global_status = "WARN"
                    global_color = SENSOR_COLORS["WARN"]

                # Update sensor data
                self.sensor_data[sensor] = {
                    "value": value,
                    "timestamp": timestamp,
                    "status": row_status
                }
                # Update history
                if sensor not in self.sensor_history:
                    self.sensor_history[sensor] = []
                now = time.time()
                self.sensor_history[sensor].append((now, value))
                self.sensor_history[sensor] = [
                    (t, v) for t, v in self.sensor_history[sensor] if now - t < 20
                ]

                # Update or insert row
                if sensor in self.sensor_rows:
                    iid = self.sensor_rows[sensor]
                    self.tree.item(iid, values=(sensor, value, timestamp, row_status))
                else:
                    iid = self.tree.insert("", "end", values=(sensor, value, timestamp, row_status))
                    self.sensor_rows[sensor] = iid

                # Row color
                tags = (row_status,)
                self.tree.item(iid, tags=tags)

                # Alarm log
                if alarm:
                    self.log_table.insert("", "end", values=(
                        alarm["time"], sensor, value, alarm["type"]
                    ))
                    self.log_table.yview_moveto(1)

        except queue.Empty:
            pass

        self.status_label.config(text=f"System Status: {global_status}", bg=global_color)

        for sensor, (fig, ax) in self.figures.items():
            ax.clear()
            ax.set_title(sensor)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Value")
            history = self.sensor_history.get(sensor, [])
            if history:
                t0 = history[0][0]
                times = [t - t0 for t, v in history]
                values = [v for t, v in history]
                ax.plot(times, values, color="blue")
            self.canvases[sensor].draw()

        self.after(200, self.update_gui)

def main():
    data_queue = queue.Queue()
    alarm_manager = AlarmManager(SENSOR_LIMITS)

    # Create the GUI first so it starts the simulator subprocess
    app = SensorDashboard(data_queue, alarm_manager, None)

    # Give the simulator a moment to start listening
    time.sleep(0.5)

    # Start the client after the simulator is up using the chosen port
    port = getattr(app, "simulator_port", None)
    if port is None:
        print("[APP] No simulator port available; not starting client.")
    else:
        client = SensorClient("127.0.0.1", port, data_queue)
        client.start()
        app.client = client

    try:
        app.mainloop()
    finally:
        # Ensure we clean up client and simulator on exit
        if 'client' in locals():
            client.stop()
        app.stop_simulator_process()

if __name__ == "__main__":
    main()