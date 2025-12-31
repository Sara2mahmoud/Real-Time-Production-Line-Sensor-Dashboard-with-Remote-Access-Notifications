import json
import threading
import urllib.request
import urllib.error
from datetime import datetime
from tkinter import messagebox


class NotifierBase:
    def notify(self, alarm: dict):
        raise NotImplementedError


class WebhookNotifier(NotifierBase):
    def __init__(self, url):
        self.url = url

    def notify(self, alarm: dict):
        data = json.dumps(alarm).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read()
        except urllib.error.URLError as e:
            raise


class DesktopNotifier(NotifierBase):
    def __init__(self, title_prefix="Alarm"):
        self.title_prefix = title_prefix

    def notify(self, alarm: dict):
        # Show a simple popup using tkinter.messagebox (runs on caller thread)
        title = f"{self.title_prefix}: {alarm.get('type', '')}"
        msg = f"{alarm.get('sensor')} = {alarm.get('value')}\nTime: {alarm.get('time')}"
        try:
            # Run the messagebox in the main thread via threading if needed
            # Some callers may be in non-GUI threads; use threading to avoid blocking background work.
            def _show():
                try:
                    messagebox.showwarning(title, msg)
                except Exception:
                    print(f"[NOTIFY] {title} - {msg}")

            t = threading.Thread(target=_show)
            t.daemon = True
            t.start()
        except Exception:
            print(f"[NOTIFY] {title} - {msg}")


class NotificationManager:
    def __init__(self, log_callback=None):
        self._notifiers = []
        self._lock = threading.Lock()
        self.log_callback = log_callback

    def add_notifier(self, notifier: NotifierBase):
        with self._lock:
            self._notifiers.append(notifier)

    def remove_notifier(self, notifier: NotifierBase):
        with self._lock:
            self._notifiers.remove(notifier)

    def notify(self, alarm: dict):
        # Called when an alarm occurs; dispatch to notifiers asynchronously
        def _dispatch():
            with self._lock:
                notifiers = list(self._notifiers)

            for n in notifiers:
                try:
                    n.notify(alarm)
                    if self.log_callback:
                        self.log_callback(f"Notification sent via {n.__class__.__name__} for {alarm['sensor']} {alarm['type']}")
                except Exception as e:
                    if self.log_callback:
                        self.log_callback(f"Notification failed ({n.__class__.__name__}): {e}")
        t = threading.Thread(target=_dispatch, daemon=True)
        t.start()

    def send_test(self):
        alarm = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sensor": "TEST_SENSOR",
            "value": 0,
            "type": "TEST"
        }
        self.notify(alarm)
