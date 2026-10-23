"""Input-source selection before and after assessment mode selection."""
from pathlib import Path
import tempfile
import unittest

from assessment import AssessmentError, AssessmentService
from assessment_store import AssessmentStore


class InputSourceTests(unittest.TestCase):
    def setUp(self):
        self.service = AssessmentService(clock=lambda: 100.0)

    def command(self, action, **fields):
        return self.service.command({"action": action, "session_id": self.service.snapshot()["session_id"], **fields})

    def test_selecting_source_before_mode_does_not_start_an_assessment(self):
        before = self.service.snapshot()
        for source in ("esp32", "simulation"):
            state = self.command("set_input_source", input_source=source)
            self.assertEqual(state["input_source"], source)
            self.assertEqual(state["phase"], "mode_selection")
            self.assertIsNone(state["session_id"])
            self.assertIsNone(state["mode"])
            self.assertEqual(state["patient_id"], before["patient_id"])
            self.assertEqual(state["student"], before["student"])
            self.assertEqual(state["checklist"], before["checklist"])
            self.assertEqual(state["elapsed"], 0)
            self.assertIsNone(self.service._started)

    def test_source_selection_does_not_fabricate_real_sensor_connections(self):
        state = self.command("set_input_source", input_source="esp32")
        self.assertFalse(state["hardware"]["esp32_connected"])
        self.assertFalse(state["hardware"]["mpu_connected"])
        self.assertFalse(state["hardware"]["rfid_connected"])
        self.service.hardware_event({"type": "status", "esp32_connected": True, "mpu_connected": True, "rfid_connected": True})
        state = self.service.snapshot()
        self.assertTrue(state["hardware"]["mpu_connected"])
        self.assertTrue(state["hardware"]["rfid_connected"])

    def test_both_modes_preserve_a_source_selected_before_mode(self):
        for source in ("simulation", "esp32"):
            for mode in ("full", "direct"):
                with self.subTest(source=source, mode=mode):
                    self.service = AssessmentService(clock=lambda: 100.0)
                    self.command("set_input_source", input_source=source)
                    state = self.command("select_mode", mode=mode)
                    self.assertEqual(state["input_source"], source)
                    self.assertEqual(state["phase"], "preparation")
                    self.assertEqual(state["mode"], mode)
                    self.assertIsNotNone(state["session_id"])

    def test_source_can_be_changed_after_mode_and_scenario_selection(self):
        for mode in ("full", "direct"):
            self.service = AssessmentService(clock=lambda: 100.0)
            initial = self.command("select_mode", mode=mode)
            self.command("configure", scenario_id="hypoventilation")
            for source in ("esp32", "simulation"):
                state = self.command("set_input_source", input_source=source)
                self.assertEqual(state["input_source"], source)
                self.assertEqual(state["session_id"], initial["session_id"])
                self.assertEqual(state["phase"], "preparation")
                self.assertEqual(state["planned_scenario"], "hypoventilation")
            # Existing clients can still use configure during preparation.
            self.assertEqual(self.command("configure", input_source="esp32")["input_source"], "esp32")

    def test_session_checks_cover_stale_menu_and_preparation_requests(self):
        with self.assertRaises(AssessmentError):
            self.command("set_input_source", input_source="esp32", session_id="expired-session")
        self.command("select_mode", mode="full")
        for session_id in (None, "expired-session"):
            with self.assertRaises(AssessmentError):
                self.command("set_input_source", input_source="esp32", session_id=session_id)
        self.assertEqual(self.service.snapshot()["input_source"], "simulation")

    def test_missing_and_invalid_sources_do_not_change_the_selection(self):
        for source in (None, "serial", "", True):
            with self.assertRaises(AssessmentError):
                self.command("set_input_source", input_source=source)
            self.assertEqual(self.service.snapshot()["input_source"], "simulation")

    def test_source_is_locked_after_either_exercise_starts(self):
        for mode, action in (("full", "begin_injection"), ("direct", "start_scenario")):
            self.service = AssessmentService(clock=lambda: 100.0)
            self.command("select_mode", mode=mode)
            before = self.command(action)
            with self.assertRaises(AssessmentError):
                self.command("set_input_source", input_source="esp32")
            after = self.service.snapshot()
            self.assertEqual(after["input_source"], before["input_source"])
            self.assertEqual(after["phase"], before["phase"])
            self.assertEqual(after["revision"], before["revision"])

    def test_source_stays_locked_during_intervention_and_results(self):
        self.command("select_mode", mode="direct")
        self.command("start_scenario")
        self.command("scenario_visible", scenario_id="hypotension")
        self.command("recognize", scenario_id="hypotension")
        self.command("simulate_rfid", scan_kind="correct")
        with self.assertRaises(AssessmentError):
            self.command("set_input_source", input_source="esp32")
        self.command("simulate_angle", angle_deg=22)
        self.command("complete_injection", injection_stage_id=self.service.snapshot()["injection_stage_id"])
        with self.assertRaises(AssessmentError):
            self.command("set_input_source", input_source="esp32")

    def test_next_student_keeps_source_and_old_report_is_unchanged(self):
        self.command("set_input_source", input_source="esp32")
        active = self.command("select_mode", mode="full")
        next_state = self.command("end")
        self.assertEqual(next_state["input_source"], "esp32")
        self.assertIsNone(next_state["session_id"])
        self.assertNotEqual(next_state["patient_id"], active["patient_id"])
        self.assertEqual(next_state["last_report"]["input_source"], "esp32")
        self.command("set_input_source", input_source="simulation")
        self.assertEqual(self.service.snapshot()["last_report"]["input_source"], "esp32")
        with self.assertRaises(AssessmentError):
            self.command("set_input_source", input_source="esp32", session_id=active["session_id"])

    def test_pre_mode_selection_does_not_create_an_empty_assessment_record(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AssessmentStore(Path(directory) / "test.sqlite3")
            self.service = AssessmentService(store=store)
            self.command("set_input_source", input_source="esp32")
            self.assertEqual(store.results(), [])
            self.command("select_mode", mode="full")
            self.assertEqual(store.results()[0]["input_source"], "esp32")


if __name__ == "__main__":
    unittest.main()
