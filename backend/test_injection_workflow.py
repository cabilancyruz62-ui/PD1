from copy import deepcopy
import unittest
from assessment import AssessmentService, AssessmentError


class InjectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.service = AssessmentService(clock=lambda: self.now)

    def command(self, action, **fields):
        current = self.service.snapshot()
        return self.service.command({"action": action, "session_id": current["session_id"], "injection_stage_id": current["injection_stage_id"], **fields})

    def activate(self, mode="direct", source="simulation"):
        self.command("select_mode", mode=mode)
        self.command("configure", input_source=source)
        if mode == "full":
            self.command("begin_injection")
            self.command("simulate_angle", angle_deg=22)
            self.command("complete_injection")
        else:
            self.command("start_scenario")
        self.command("scenario_visible", scenario_id="hypotension")
        self.command("recognize", scenario_id="hypotension")

    def test_both_modes_require_new_angle_and_confirmation_after_drug_verification(self):
        for mode in ("full", "direct"):
            with self.subTest(mode=mode):
                self.service = AssessmentService(clock=lambda: self.now)
                self.activate(mode)
                before = deepcopy(self.service.snapshot())
                self.now += 12
                verified = self.command("simulate_rfid", scan_kind="correct")
                self.assertEqual(verified["notification"]["kind"], "drug_verified")
                self.assertEqual(verified["phase"], "intervention_injection")
                self.assertFalse(verified["score"]["final"])
                self.assertIsNone(verified["angle"])
                with self.assertRaises(AssessmentError):
                    self.command("complete_injection")
                with self.assertRaises(AssessmentError):
                    self.command("complete_injection", injection_stage_id=before["injection_stage_id"])
                self.command("simulate_angle", angle_deg=22)
                self.assertEqual(self.service.snapshot()["phase"], "intervention_injection")
                self.now += 3
                done = self.command("complete_injection")
                self.assertEqual(done["phase"], "evaluated")
                self.assertTrue(done["score"]["final"])
                self.assertEqual(done["score"]["value"], 100)
                self.assertEqual(done["first_response_seconds"], 12)
                self.assertEqual(done["intervention_duration_seconds"], 3)
                self.assertEqual(done["intervention_completion_seconds"], 15)
                self.assertTrue(done["intervention_injection_completed"])
                self.assertEqual(done["angle_records"]["intervention"]["total_samples"], 5)
                self.assertEqual(done["angle_records"]["initial"]["total_samples"], 5 if mode == "full" else 0)
                if mode == "full":
                    self.assertNotEqual(done["initial_angle"]["injection_stage_id"], done["intervention_angle"]["injection_stage_id"])
                    self.assertEqual(done["initial_angle"], before["initial_angle"])
                else:
                    self.assertIsNone(done["initial_angle"])
                    self.assertNotIn("initial_angle", done["score"]["weights"])

    def test_wrong_or_unknown_tag_cannot_unlock_intervention(self):
        self.activate()
        for kind in ("incorrect", "unregistered"):
            state = self.command("simulate_rfid", scan_kind=kind)
            self.assertEqual(state["phase"], "scenario_active")
            self.assertIsNone(state["injection_stage_id"])
            with self.assertRaises(AssessmentError):
                self.command("complete_injection")
        self.assertEqual(len(self.service.snapshot()["attempts"]), 2)

    def test_invalid_intervention_angle_is_recorded_separately(self):
        self.activate("full")
        self.command("simulate_rfid", scan_kind="correct")
        self.command("simulate_angle", angle_deg=45)
        state = self.command("complete_injection")
        self.assertTrue(state["initial_angle"]["within_target"])
        self.assertFalse(state["intervention_angle"]["within_target"])
        self.assertEqual(state["score"]["value"], 80)

    def test_stale_or_disconnected_intervention_cannot_complete(self):
        self.activate()
        self.command("simulate_rfid", scan_kind="correct")
        self.command("simulate_angle", angle_deg=22)
        self.now += 5
        with self.assertRaises(AssessmentError):
            self.command("complete_injection")
        self.command("simulate_disconnect")
        self.command("simulate_angle", angle_deg=22)
        with self.assertRaises(AssessmentError):
            self.command("complete_injection")

    def test_real_unapproved_route_never_forces_injection(self):
        self.activate(source="esp32")
        current = self.service.snapshot()
        self.service.hardware_event({"type": "status", "esp32_connected": True, "mpu_connected": True, "rfid_connected": True})
        self.service.hardware_event({"type": "rfid", "device_id": "test", "event_id": "1", "session_id": current["session_id"], "uid": "RFID_TAG_001"})
        state = self.service.snapshot()
        self.assertEqual(state["phase"], "intervention_review")
        self.assertFalse(state["intervention_policy"]["requires_injection"])
        self.assertIsNone(state["injection_stage_id"])
        self.assertNotIn("intervention_angle", state["score"]["weights"])
        with self.assertRaises(AssessmentError):
            self.command("complete_injection")

    def test_non_injectable_route_has_no_angle_requirement(self):
        config = deepcopy(self.service.config)
        config["scenarios"]["hypotension"]["intervention_route"] = "non_injectable"
        self.service = AssessmentService(config=config, clock=lambda: self.now)
        self.activate()
        state = self.command("simulate_rfid", scan_kind="correct")
        self.assertEqual(state["phase"], "intervention_non_injectable")
        self.assertNotIn("intervention_angle", state["score"]["weights"])
        done = self.command("complete_non_injectable_intervention")
        self.assertEqual(done["score"]["value"], 100)
        self.assertFalse(done["intervention_injection_completed"])

    def test_approved_hardware_uses_fresh_stage_id_and_deduplicates_angle_events(self):
        config = deepcopy(self.service.config)
        config["scenarios"]["hypotension"]["injectable_expert_approved"] = True
        self.service = AssessmentService(config=config, clock=lambda: self.now)
        self.activate(source="esp32")
        self.service.hardware_event({"type": "status", "esp32_connected": True, "mpu_connected": True, "rfid_connected": True})
        self.service.hardware_event({"type": "rfid", "device_id": "test", "event_id": "scan", "session_id": self.service.snapshot()["session_id"], "uid": "RFID_TAG_001"})
        state = self.service.snapshot()
        data = {"type": "angle", "device_id": "test", "event_id": "angle", "session_id": state["session_id"], "injection_stage_id": state["injection_stage_id"], "angle_deg": 22, "calibrated": True, "calibration_id": "TEST_SURFACE"}
        with self.assertRaises(AssessmentError):
            self.service.hardware_event({**data, "injection_stage_id": "expired-initial-stage"})
        self.service.hardware_event(data)
        self.service.hardware_event(data)
        self.assertEqual(self.service.snapshot()["angle_records"]["intervention"]["total_samples"], 1)
        self.now += 6
        self.service.hardware_event({"type": "status", "esp32_connected": True, "mpu_connected": True, "rfid_connected": True})
        self.service.hardware_event(data)
        self.assertFalse(self.service.snapshot()["angle"]["fresh"])
        with self.assertRaises(AssessmentError):
            self.command("complete_injection")


if __name__ == "__main__":
    unittest.main()
