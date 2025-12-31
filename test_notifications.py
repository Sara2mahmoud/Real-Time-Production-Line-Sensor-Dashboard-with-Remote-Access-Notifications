import time

from notifications import (
    NotificationManager,
    NotifierBase,
    WebhookNotifier,
    DesktopNotifier,
)


def run_notification_test():
    print("\n[TEST] Starting NotificationManager simple test\n")

    logs = []

    def log_callback(msg):
        logs.append(msg)
        print("[LOG]", msg)

    print("[TEST] Creating NotificationManager...")
    nm = NotificationManager(log_callback=log_callback)
    print("[OK] NotificationManager created\n")

    # ---------- TEST 1: Dummy notifier ----------
    print("[TEST] Dummy notifier (print-only)")

    class DummyNotifier(NotifierBase):
        def notify(self, alarm: dict):
            print("[DUMMY NOTIFIER] Received alarm:", alarm)

    dummy = DummyNotifier()
    nm.add_notifier(dummy)

    print("[TEST] Sending test alarm...")
    nm.send_test()

    time.sleep(1)

    print("[TEST] Dummy notifier test finished\n")

    # ---------- TEST 2: Desktop notifier ----------
    print("[TEST] Desktop notifier (may show popup or print fallback)")
    desktop = DesktopNotifier(title_prefix="TEST ALARM")
    nm.add_notifier(desktop)

    print("[TEST] Sending test alarm to desktop notifier...")
    nm.send_test()

    time.sleep(2)
    print("[TEST] Desktop notifier test finished\n")

    # ---------- TEST 3: Webhook notifier (invalid URL, expect failure log) ----------
    print("[TEST] Webhook notifier (expected failure)")

    webhook = WebhookNotifier("http://127.0.0.1:9999/invalid")
    nm.add_notifier(webhook)

    print("[TEST] Sending test alarm to webhook notifier...")
    nm.send_test()

    time.sleep(2)

    print("[TEST] Webhook notifier test finished\n")

    # ---------- SUMMARY ----------
    print("[TEST] Logs captured:")
    for l in logs:
        print(" -", l)

    print("\n[TEST] NotificationManager simple test completed\n")


if __name__ == "__main__":
    run_notification_test()
