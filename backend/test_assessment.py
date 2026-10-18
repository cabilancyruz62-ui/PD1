from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from assessment import AssessmentService, AssessmentError
from assessment_store import AssessmentStore


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.time = 100.0
        self.service = AssessmentService(clock=lambda: self.time)

    def call(self, action, **fields):
        return self.service.command({"action": action, "session_id": self.service.snapshot()["session_id"], "injection_stage_id": self.service.snapshot()["injection_stage_id"], **fields})

    def direct(self, scenario="hypotension"):
        self.call("select_mode", mode="direct")
        self.call("configure", scenario_id=scenario)
        self.call("start_scenario")
        return self.call("scenario_visible", scenario_id=scenario)

    def test_full_requires_explicit_completion_and_fresh_calibrated_angle(self):
        self.call("select_mode", mode="full")
        self.call("simulate_angle", angle_deg=22)
        self.assertEqual(self.service.snapshot()["phase"], "preparation")
        self.call("begin_injection")
        with self.assertRaises(AssessmentError):
            self.call("complete_injection")
        state = self.call("simulate_angle", angle_deg=22)
        self.assertEqual(state["phase"], "injection")
        self.assertFalse(state["checklist"]["injection"])
        self.time += 6
        with self.assertRaises(AssessmentError):
            self.call("complete_injection")
        self.call("simulate_angle", angle_deg=22)
        state = self.call("complete_injection")
        self.assertEqual(state["phase"], "scenario_pending")
        self.assertTrue(state["checklist"]["angle"])
        self.assertTrue(state["checklist"]["injection"])

    def test_invalid_angle_is_recorded_and_loses_only_its_configured_points(self):
        self.call("select_mode", mode="full")
        self.call("begin_injection")
        self.call("simulate_angle", angle_deg=45)
        state = self.call("complete_injection")
        self.assertFalse(state["checklist"]["angle"])
        self.assertEqual(state["injection_angle"]["angle_deg"], 45)
        self.call("scenario_visible", scenario_id="hypotension")
        self.call("recognize", scenario_id="hypotension")
        state = self.call("simulate_rfid", scan_kind="correct")
        self.call("simulate_angle", angle_deg=22)
        state = self.call("complete_injection")
        self.assertEqual(state["score"]["value"], 85)

    def test_angle_target_includes_both_boundaries(self):
        for value, valid in [(15, True), (30, True), (14.9, False), (30.1, False)]:
            self.service = AssessmentService(clock=lambda: self.time)
            self.call("select_mode", mode="full")
            self.call("begin_injection")
            self.call("simulate_angle", angle_deg=value)
            self.assertEqual(self.call("complete_injection")["injection_angle"]["within_target"], valid)

    def test_direct_mode_skips_only_initial_injection_in_score(self):
        self.direct("hypoventilation")
        with self.assertRaises(AssessmentError):
            self.call("complete_injection")
        self.call("recognize", scenario_id="hypoventilation")
        self.time += 12
        state = self.call("simulate_rfid", uid="RFID_TAG_002")
        self.assertEqual(state["phase"], "intervention_injection")
        self.assertFalse(state["score"]["final"])
        self.call("simulate_angle", angle_deg=22)
        state = self.call("complete_injection")
        self.assertEqual(state["score"]["value"], 100)
        self.assertEqual(set(state["score"]["weights"]), {"recognition", "drug", "intervention_angle", "intervention_completion"})
        self.assertFalse(state["checklist"]["injection"])
        self.assertEqual(state["first_response_seconds"], 12)

    def test_response_starts_at_visibility_and_retains_first_attempt_time(self):
        self.call("select_mode", mode="direct")
        self.call("start_scenario")
        self.time += 20
        self.call("scenario_visible", scenario_id="hypotension")
        self.time += 12
        first = self.call("simulate_rfid", uid="RFID_TAG_002")
        self.assertEqual(first["first_response_seconds"], 12)
        self.time += 8
        second = self.call("simulate_rfid", uid="RFID_TAG_001")
        self.assertEqual(second["first_response_seconds"], 12)
        self.assertEqual([a["response_seconds"] for a in second["attempts"]], [12, 20])
        self.assertEqual(second["phase"], "intervention_injection")

    def test_only_one_scenario_and_wrong_tag_does_not_change_vital_targets(self):
        state = self.direct("hypotension")
        before = state["vitals"]
        state = self.call("simulate_rfid", uid="RFID_TAG_002")
        self.assertEqual(state["phase"], "scenario_active")
        self.assertEqual(state["vitals"], before)
        self.assertEqual(state["scenario_id"], "hypotension")
        with self.assertRaises(AssessmentError):
            self.call("configure", scenario_id="bradycardia")
        self.time += 120
        self.assertEqual(self.service.snapshot()["scenario_id"], "hypotension")

    def test_scenario_changes_only_requested_channels(self):
        for scenario, channel in [("hypotension", "map"), ("hypoventilation", "rr"), ("bradycardia", "hr")]:
            self.service = AssessmentService(clock=lambda: self.time)
            baseline = self.call("select_mode", mode="direct")["vitals"]
            self.call("configure", scenario_id=scenario)
            self.assertEqual(self.service.snapshot()["vitals"], baseline)
            changed = self.call("start_scenario")["vitals"]
            self.assertLess(changed[channel], baseline[channel])
            if scenario == "hypoventilation":
                self.assertGreater(changed["etco2"], baseline["etco2"])
            else:
                for key in baseline.keys() - {channel}:
                    self.assertEqual(changed[key], baseline[key])
            targets = self.service.config["scenarios"][scenario]["target"]
            for key, target in targets.items():
                self.assertAlmostEqual(changed[key], target, delta=1)
            self.assertEqual(self.call("scenario_visible", scenario_id=scenario)["vitals"], changed)
            self.assertEqual(self.call("simulate_rfid", scan_kind="incorrect")["vitals"], changed)
            verified = self.call("simulate_rfid", scan_kind="correct")
            self.assertEqual(verified["phase"], "intervention_injection")
            self.assertEqual(verified["vitals"], changed)
            self.call("simulate_angle", angle_deg=22)
            self.assertEqual(self.call("complete_injection")["vitals"], changed)
            reset = self.call("end")
            self.assertIsNone(reset["scenario_id"])
            self.assertGreater(reset["vitals"][channel], changed[channel])

    def test_registry_uses_uid_not_an_assumed_drug_number(self):
        config = deepcopy(self.service.config)
        config["rfid_registry"]["AA:BB:12:34"] = config["rfid_registry"].pop("RFID_TAG_001")
        self.service = AssessmentService(config=config, clock=lambda: self.time)
        self.direct()
        unknown = self.call("simulate_rfid", uid="ANY_OTHER_TAG_001")
        self.assertEqual(unknown["attempts"][0]["result"], "unregistered")
        state = self.call("simulate_rfid", uid="aa:bb:12:34")
        self.assertEqual(state["attempts"][-1]["result"], "correct")
        self.assertEqual(state["score"]["incorrect_attempts"], 1)

    def test_duplicate_events_and_bouncing_reads_are_not_double_scored(self):
        self.direct()
        self.call("simulate_rfid", uid="RFID_TAG_002")
        self.call("simulate_rfid", uid="RFID_TAG_002")
        state = self.call("simulate_rfid", scan_kind="duplicate")
        self.assertEqual(len(state["attempts"]), 1)
        self.time += 3
        state = self.call("simulate_rfid", uid="RFID_TAG_002")
        self.assertEqual(len(state["attempts"]), 2)
        self.time += 10
        state = self.call("simulate_rfid", scan_kind="duplicate")
        self.assertEqual(len(state["attempts"]), 2)

    def test_no_scenario_and_disconnected_reader_scans_are_unscored(self):
        self.call("select_mode", mode="direct")
        state = self.call("simulate_rfid", scan_kind="correct")
        self.assertEqual(state["attempts"], [])
        self.assertIsNone(state["first_response_seconds"])
        self.call("start_scenario")
        self.call("scenario_visible", scenario_id="hypotension")
        self.call("simulate_disconnect")
        self.time += 2
        state = self.call("simulate_rfid", scan_kind="correct")
        self.assertEqual(state["attempts"], [])
        self.assertEqual(state["rfid_events"][-1]["result"], "ignored")
        self.call("simulate_reconnect")
        self.time += 2
        self.assertEqual(self.call("simulate_rfid", scan_kind="correct")["phase"], "intervention_injection")

    def test_hardware_requires_heartbeat_calibration_and_correct_session(self):
        state = self.call("select_mode", mode="full")
        session = state["session_id"]
        self.call("configure", input_source="esp32")
        self.call("begin_injection")
        self.service.hardware_event({"type": "status", "esp32_connected": True, "mpu_connected": True, "rfid_connected": True})
        self.service.hardware_event({"type": "angle", "device_id": "unit-test", "event_id": str(self.time) + str(self.service.snapshot()["revision"]), "injection_stage_id": self.service.snapshot()["injection_stage_id"], "session_id": session, "angle_deg": 22, "calibrated": False})
        with self.assertRaises(AssessmentError):
            self.call("complete_injection")
        with self.assertRaises(AssessmentError):
            self.call("simulate_angle", angle_deg=22)
        with self.assertRaises(AssessmentError):
            self.service.hardware_event({"type": "angle", "session_id": "old", "angle_deg": 22})
        self.service.hardware_event({"type": "angle", "device_id": "unit-test", "event_id": "calibrated-sample", "session_id": session, "injection_stage_id": self.service.snapshot()["injection_stage_id"], "angle_deg": 22, "calibrated": True, "calibration_id": "TEST_SKIN_PLANE"})
        self.assertTrue(self.call("complete_injection")["checklist"]["angle"])
        self.time += 6
        self.assertFalse(self.service.snapshot()["hardware"]["rfid_connected"])

    def test_end_keeps_report_and_changes_patient_once(self):
        old = self.direct()
        report = self.call("end")
        self.assertNotEqual(report["patient_id"], old["patient_id"])
        self.assertEqual(report["last_report"]["patient_id"], old["patient_id"])
        self.assertEqual(report["phase"], "mode_selection")
        with self.assertRaises(AssessmentError):
            self.service.command({"action": "end", "session_id": old["session_id"]})

    def test_scoring_is_configurable(self):
        config = deepcopy(self.service.config)
        config["incorrect_attempt_penalty"] = 7
        self.service = AssessmentService(config=config, clock=lambda: self.time)
        self.direct()
        self.call("recognize", scenario_id="hypotension")
        self.call("simulate_rfid", uid="RFID_TAG_002")
        state = self.call("simulate_rfid", uid="RFID_TAG_001")
        self.call("simulate_angle", angle_deg=22)
        state = self.call("complete_injection")
        self.assertEqual(state["score"]["value"], 93)

    def test_sqlite_preserves_reports_and_interrupts_active_session_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AssessmentStore(Path(directory) / "test.sqlite3")
            self.service = AssessmentService(store=store, clock=lambda: self.time)
            session = self.direct()["session_id"]
            self.call("end")
            active = self.call("select_mode", mode="full")["session_id"]
            restarted = AssessmentService(store=store, clock=lambda: self.time)
            records = {record["session_id"]: record for record in store.results()}
            self.assertEqual(records[session]["phase"], "ended")
            self.assertEqual(records[active]["phase"], "interrupted")
            self.assertEqual(restarted.snapshot()["phase"], "mode_selection")
            self.assertIsNotNone(restarted.snapshot()["last_report"])


if __name__ == "__main__":
    unittest.main()
