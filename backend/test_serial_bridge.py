import json
import unittest
from serial_bridge import Bridge, BackendRejected


class FakeClient:
    def __init__(self):
        self.state = {"session_id": "S1", "injection_stage_id": "STAGE1"}
        self.sent = []
        self.reject = None

    def get_state(self):
        return dict(self.state)

    def post_event(self, event):
        if self.reject:
            raise BackendRejected(*self.reject)
        self.sent.append(event)
        return {}


def line(**overrides):
    data = {"angle": 22.0, "elev": -22.0, "drug": None, "scan": 0, "o2": 50, "volume": None, "q": [1, 0, 0, 0], "angle_valid": True, "dummy_ok": True, "syringe_ok": True, "rfid_ok": True, "uid": None, "scan_seq": 0, "cal_ok": True, "cal_id": "fw-2"}
    data.update(overrides)
    return json.dumps(data)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.client = FakeClient()
        self.logs = []
        self.bridge = Bridge(self.client, angle_hz=5, clock=lambda: self.now, log=self.logs.append)

    def types(self):
        return [event["type"] for event in self.client.sent]

    def test_status_heartbeat_once_per_second_with_connection_flags(self):
        self.bridge.handle_line(line())
        self.now += 0.5
        self.bridge.handle_line(line())
        self.assertEqual(self.types().count("status"), 1)
        status = next(event for event in self.client.sent if event["type"] == "status")
        self.assertEqual((status["esp32_connected"], status["mpu_connected"], status["rfid_connected"]), (True, True, True))
        self.now += 1
        self.bridge.handle_line(line())
        self.assertEqual(self.types().count("status"), 2)

    def test_missing_dummy_marks_mpu_disconnected_unless_allowed(self):
        self.bridge.handle_line(line(dummy_ok=False))
        self.assertFalse(self.client.sent[0]["mpu_connected"])
        self.assertIn("error", self.types())
        relaxed = Bridge(self.client, require_dummy=False, clock=lambda: self.now, log=self.logs.append)
        self.client.sent.clear()
        relaxed.handle_line(line(dummy_ok=False))
        self.assertTrue(self.client.sent[0]["mpu_connected"])

    def test_angle_requires_active_stage_and_never_sends_quaternions(self):
        self.client.state["injection_stage_id"] = None
        self.bridge.handle_line(line())
        self.assertNotIn("angle", self.types())
        self.client.state["injection_stage_id"] = "STAGE1"
        self.now += 1
        self.bridge.handle_line(line())
        angle = next(event for event in self.client.sent if event["type"] == "angle")
        self.assertEqual((angle["session_id"], angle["injection_stage_id"], angle["angle_deg"], angle["calibrated"], angle["calibration_id"]), ("S1", "STAGE1", 22.0, True, "fw-2"))
        self.assertNotIn("syringe_quaternion", angle)
        self.assertNotIn("dummy_quaternion", angle)

    def test_uncalibrated_angle_is_flagged_and_has_no_calibration_id(self):
        self.bridge.handle_line(line(cal_ok=False))
        angle = next(event for event in self.client.sent if event["type"] == "angle")
        self.assertFalse(angle["calibrated"])
        self.assertNotIn("calibration_id", angle)

    def test_null_angle_is_not_sent_and_rate_is_limited(self):
        self.bridge.handle_line(line(angle=None))
        self.assertNotIn("angle", self.types())
        self.bridge.handle_line(line())
        self.now += 0.05
        self.bridge.handle_line(line())
        self.assertEqual(self.types().count("angle"), 1)
        self.now += 0.25
        self.bridge.handle_line(line())
        self.assertEqual(self.types().count("angle"), 2)

    def test_scan_sent_once_and_old_scans_are_not_replayed_at_startup(self):
        self.bridge.handle_line(line(uid="OLD", scan_seq=7))
        self.assertNotIn("rfid", self.types())
        self.bridge.handle_line(line(uid="04A1B2C3", scan_seq=8))
        self.bridge.handle_line(line(uid="04A1B2C3", scan_seq=8))
        scans = [event for event in self.client.sent if event["type"] == "rfid"]
        self.assertEqual(len(scans), 1)
        self.assertEqual((scans[0]["uid"], scans[0]["session_id"]), ("04A1B2C3", "S1"))

    def test_firmware_reboot_does_not_reuse_event_ids_or_replay(self):
        self.bridge.handle_line(line(uid="A", scan_seq=3))
        self.bridge.handle_line(line(uid="A", scan_seq=4))
        self.bridge.handle_line(line(uid=None, scan_seq=0))   # reboot
        self.bridge.handle_line(line(uid="A", scan_seq=1))
        ids = [event["event_id"] for event in self.client.sent if event["type"] == "rfid"]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 2)

    def test_rejection_forces_resync_and_partial_lines_are_ignored(self):
        self.client.reject = (409, "different injection stage")
        self.bridge.handle_line(line())
        self.assertEqual(self.bridge.last_state_fetch, -1e9)   # next sample refetches session/stage IDs
        self.bridge.handle_line('{"angle": 12.')
        self.bridge.handle_line("# Bridge v3 boot")
        self.assertTrue(any("boot" in item for item in self.logs))


if __name__ == "__main__":
    unittest.main()
