from alarms.alarm_manager import AlarmManager


def run_alarm_manager_test():
    print("\n[TEST] Starting AlarmManager simple test...\n")

    limits = {
        "TEMP_1": {"low": 20, "high": 80}
    }

    print("[TEST] Creating AlarmManager...")
    am = AlarmManager(limits)
    print("[OK] AlarmManager created\n")

    # ---------- FAULT TEST ----------
    print("[TEST] FAULT sensor test")
    pkt = {"sensor": "TEMP_1", "value": 50, "status": "FAULT"}
    alarm = am.check(pkt)

    if alarm:
        print("[OK] Alarm triggered")
        print("[ALARM]", alarm)
    else:
        print("[ERROR] No alarm triggered for FAULT")

    print()

    # ---------- LOW LIMIT TEST ----------
    print("[TEST] LOW limit test")
    pkt = {"sensor": "TEMP_1", "value": 10, "status": "OK"}
    alarm = am.check(pkt)

    if alarm and alarm["type"] == "LOW_LIMIT":
        print("[OK] LOW_LIMIT alarm triggered correctly")
        print("[ALARM]", alarm)
    else:
        print("[ERROR] LOW_LIMIT alarm not triggered correctly")

    print()

    # ---------- HIGH LIMIT TEST ----------
    print("[TEST] HIGH limit test")
    pkt = {"sensor": "TEMP_1", "value": 100, "status": "OK"}
    alarm = am.check(pkt)

    if alarm and alarm["type"] == "HIGH_LIMIT":
        print("[OK] HIGH_LIMIT alarm triggered correctly")
        print("[ALARM]", alarm)
    else:
        print("[ERROR] HIGH_LIMIT alarm not triggered correctly")

    print()

    # ---------- NORMAL VALUE TEST ----------
    print("[TEST] Normal value (no alarm)")
    pkt = {"sensor": "TEMP_1", "value": 50, "status": "OK"}
    alarm = am.check(pkt)

    if alarm is None:
        print("[OK] No alarm as expected")
    else:
        print("[ERROR] Alarm triggered when it should not")
        print("[ALARM]", alarm)

    print()

    # ---------- ACTIVE ALARMS COUNT ----------
    print("[TEST] Active alarms count")
    print(f"[INFO] Active alarms stored: {len(am.active_alarms)}")
    for a in am.active_alarms:
        print(" -", a)

    print("\n[TEST] AlarmManager simple test finished\n")


if __name__ == "__main__":
    run_alarm_manager_test()
