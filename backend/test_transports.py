"""Run a private temporary backend and verify real HTTP + both WebSocket routes."""
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from websockets.sync.client import connect


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.ws = f"ws://127.0.0.1:{cls.port}"
        config = json.loads((Path(__file__).parent / "config/assessment.json").read_text())
        config["angle_calibrations"]["TEST_SURFACE"] = {"syringe_axis_sensor": [1, 0, 0], "surface_normal_sensor": [0, 0, 1], "syringe_reference_rotation_xyzw": [0, 0, 0, 1], "dummy_reference_rotation_xyzw": [0, 0, 0, 1]}
        # Explicitly approved TEST FIXTURE only; production placeholder config stays unapproved.
        for scenario in config["scenarios"].values():
            scenario["injectable_expert_approved"] = True
        config_path = Path(cls.directory.name) / "test-config.json"
        config_path.write_text(json.dumps(config))
        env = {**os.environ, "ASSESSMENT_DB_PATH": str(Path(cls.directory.name) / "test.sqlite3"), "ASSESSMENT_CONFIG_PATH": str(config_path)}
        cls.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--app-dir", str(Path(__file__).parent), "--host", "127.0.0.1", "--port", str(cls.port), "--ws", "websockets-sansio", "--log-level", "warning"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(60):
            try:
                with urlopen(cls.base + "/api/health", timeout=.3) as response:
                    if response.status == 200:
                        return
            except (OSError, URLError):
                if cls.process.poll() is not None:
                    break
                time.sleep(.1)
        cls.process.terminate()
        output = cls.process.communicate(timeout=5)[0].decode(errors="replace")
        cls.directory.cleanup()
        raise RuntimeError("Temporary backend could not start: " + output)

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.communicate()
        cls.directory.cleanup()

    def request(self, path, data=None):
        request = Request(self.base+path, data=None if data is None else json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=4) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def state(self):
        return self.request("/api/assessment/state")[1]

    def command(self, action, **fields):
        status, data = self.request("/api/assessment/command", {"action": action, "session_id": self.state()["session_id"], "injection_stage_id": self.state()["injection_stage_id"], **fields})
        self.assertEqual(status, 200, data)
        return data

    def setUp(self):
        if self.state()["mode"]:
            self.command("end")

    def wait_state(self, ws, predicate):
        for _ in range(20):
            message = json.loads(ws.recv(timeout=3))
            if message.get("type") == "assessment_state" and predicate(message["state"]):
                return message["state"]
        self.fail("Expected assessment update was not streamed")

    def test_both_modes_stream_results_and_save_to_sqlite(self):
        with connect(self.ws+"/api/ws/assessment", open_timeout=3) as ws:
            for mode in ("full", "direct"):
                self.command("select_mode", mode=mode)
                self.command("configure", scenario_id="hypoventilation")
                self.command("review")
                if mode == "full":
                    self.command("begin_injection")
                    self.command("simulate_angle", angle_deg=22)
                    self.command("complete_injection")
                else:
                    self.command("start_scenario")
                pending = self.wait_state(ws, lambda s: s["phase"] == "scenario_pending")
                self.assertIsNone(pending["scenario_started_at"])
                self.command("scenario_visible", scenario_id="hypoventilation")
                self.command("recognize", scenario_id="hypoventilation")
                wrong = self.command("simulate_rfid", uid="RFID_TAG_001")
                self.assertEqual(wrong["phase"], "scenario_active")
                self.assertEqual(wrong["notification"]["kind"], "incorrect")
                correct = self.command("simulate_rfid", uid="RFID_TAG_002")
                self.wait_state(ws, lambda s: s["phase"] == "intervention_injection")
                self.assertFalse(correct["score"]["final"])
                self.command("simulate_angle", angle_deg=22)
                self.command("complete_injection")
                streamed = self.wait_state(ws, lambda s: s["phase"] == "evaluated")
                self.assertEqual(streamed["score"]["value"], 95)
                self.assertEqual(len(correct["attempts"]), 2)
                first = correct["first_response_seconds"]
                self.command("simulate_rfid", scan_kind="duplicate")
                self.assertEqual(self.state()["first_response_seconds"], first)
                ended = self.command("end")
                self.assertNotEqual(ended["patient_id"], correct["patient_id"])
                records = self.request("/api/assessment/results")[1]["results"]
                report = next(r for r in records if r["session_id"] == correct["session_id"])
                self.assertEqual(report["phase"], "ended")
                self.assertEqual(report["score"]["value"], 95)

    def test_esp32_socket_heartbeat_uid_validation_and_duplicate_reads(self):
        state = self.command("select_mode", mode="direct")
        self.command("configure", input_source="esp32", scenario_id="bradycardia")
        session = state["session_id"]
        with connect(self.ws+"/api/ws/hardware", open_timeout=3) as ws:
            self.assertEqual(json.loads(ws.recv(timeout=3))["type"], "ready")
            def send(data):
                ws.send(json.dumps({"device_id": "transport-test", "event_id": str(time.time_ns()), **data}))
                result = json.loads(ws.recv(timeout=3))
                self.assertEqual(result["type"], "accepted", result)
            send({"type": "status", "esp32_connected": True, "mpu_connected": True, "rfid_connected": True})
            self.command("start_scenario")
            self.command("scenario_visible", scenario_id="bradycardia")
            self.command("recognize", scenario_id="bradycardia")
            send({"type": "error", "component": "rfid", "message": "Reader disconnected"})
            send({"type": "rfid", "session_id": session, "uid": "UNREGISTERED_TEST"})
            self.assertEqual(self.state()["attempts"], [])
            send({"type": "status", "esp32_connected": True, "mpu_connected": True, "rfid_connected": True})
            event = {"type": "rfid", "session_id": session, "uid": "RFID_TAG_003", "event_id": "unique-scan-1"}
            send(event)
            send(event)
            intervention = self.state()
            self.assertEqual(intervention["phase"], "intervention_injection")
            half = math.radians(22)/2
            send({"type": "angle", "session_id": session, "injection_stage_id": intervention["injection_stage_id"], "syringe_quaternion": [0, -math.sin(half), 0, math.cos(half)], "dummy_quaternion": [0, 0, 0, 1], "calibrated": True, "calibration_id": "TEST_SURFACE"})
            self.command("complete_injection")
            final = self.state()
            self.assertEqual(final["phase"], "evaluated")
            self.assertEqual(final["score"]["value"], 100)
            self.assertEqual(final["intervention_angle"]["method"], "paired_quaternion_surface_angle")
            self.assertEqual(len(final["attempts"]), 1)
            ws.send("not-json")
            self.assertEqual(json.loads(ws.recv(timeout=3))["type"], "error")

    def test_invalid_api_payloads_are_rejected(self):
        for payload in ({"action": "not_supported"}, {"action": "simulate_angle", "angle_deg": 100}, {"action": "simulate_angle", "angle_deg": float("nan")}, {"action": "select_mode", "mode": "wrong"}):
            status, _ = self.request("/api/assessment/command", payload)
            self.assertEqual(status, 422)
        status, _ = self.request("/api/hardware/events", {"type": "status", "device_id": "test", "event_id": "1", "rfid_connected": "true"})
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
