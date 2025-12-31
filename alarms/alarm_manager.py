from datetime import datetime


class AlarmManager:
    def __init__(self, sensor_limits, notifier=None):
        """
        sensor_limits example:
        {
            "TEMP_1": {"low": 20, "high": 80},
            "PRESS_1": {"low": 1.0, "high": 5.0}
        }
        notifier: optional NotificationManager or any object with .notify(dict)
        """
        self.sensor_limits = sensor_limits
        self.active_alarms = []
        self.notifier = notifier

    def check(self, packet):
        """
        Evaluates a sensor packet and returns alarm info if triggered.
        """
        sensor = packet["sensor"]
        value = packet["value"]
        status = packet["status"]

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if status == "FAULT":
            return self._create_alarm(timestamp, sensor, value, "SENSOR_FAULT")

        limits = self.sensor_limits.get(sensor)
        if not limits:
            return None

        if value < limits["low"]:
            return self._create_alarm(timestamp, sensor, value, "LOW_LIMIT")

        if value > limits["high"]:
            return self._create_alarm(timestamp, sensor, value, "HIGH_LIMIT")

        return None

    def _create_alarm(self, timestamp, sensor, value, alarm_type):
        alarm = {
            "time": timestamp,
            "sensor": sensor,
            "value": value,
            "type": alarm_type
        }
        self.active_alarms.append(alarm)
        # Send notification if notifier provided
        try:
            if self.notifier:
                self.notifier.notify(alarm)
        except Exception:
            # Non-fatal: notifications should not break alarm flow
            pass
        return alarm
