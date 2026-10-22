"""Baseline calibration and deliberate complication behavior for simulated vitals."""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch

from assessment import AssessmentService


class BaselineVitalsTests(unittest.TestCase):
    def setUp(self):
        self.time = 100.0
        self.config = deepcopy(AssessmentService(clock=lambda: self.time).config)

    def service_for(self, patient_id=None, config=None):
        patient_id = patient_id or self.config["patient_ids"][0]
        with patch("assessment.random.choice", return_value=patient_id):
            return AssessmentService(config=config or self.config, clock=lambda: self.time)

    def call(self, service, action, **fields):
        state = service.snapshot()
        return service.command({
            "action": action,
            "session_id": state["session_id"],
            "injection_stage_id": state["injection_stage_id"],
            **fields,
        })

    def assert_baseline(self, vitals, ranges=None):
        ranges = ranges or self.config["baseline_vital_ranges"]
        for channel, bounds in ranges.items():
            with self.subTest(channel=channel, value=vitals[channel]):
                self.assertGreaterEqual(vitals[channel], bounds["min"])
                self.assertLessEqual(vitals[channel], bounds["max"])
                precision = 1 if channel == "temp" else 0
                self.assertEqual(vitals[channel], round(vitals[channel], precision))

    def test_default_ranges_match_canine_chart_and_awake_etco2_reference(self):
        self.assertEqual(self.config["baseline_vital_ranges"], {
            "hr": {"min": 80, "max": 120},
            "rr": {"min": 18, "max": 24},
            "temp": {"min": 38.1, "max": 39.1},
            "etco2": {"min": 35, "max": 45},
        })
        for temperature in self.config["baseline_vital_ranges"]["temp"].values():
            fahrenheit = temperature * 9 / 5 + 32
            self.assertGreaterEqual(fahrenheit, 100.5)
            self.assertLessEqual(fahrenheit, 102.5)

    def test_every_patient_stays_normal_before_any_complication(self):
        # Twelve seconds spans a complete fluctuation cycle, including its extremes.
        elapsed_samples = [step / 2 for step in range(25)]
        for patient in self.config["patient_ids"]:
            for mode in ("full", "direct"):
                self.time = 100.0
                service = self.service_for(patient)
                with self.subTest(patient=patient, mode=mode, phase="mode_selection"):
                    self.assert_baseline(service.snapshot()["vitals"])
                self.call(service, "select_mode", mode=mode)
                phases = ("preparation", "injection") if mode == "full" else ("preparation",)
                for phase in phases:
                    if phase == "injection":
                        self.call(service, "begin_injection")
                    for elapsed in elapsed_samples:
                        self.time = 100.0 + elapsed
                        state = service.snapshot()
                        with self.subTest(patient=patient, mode=mode, phase=phase, elapsed=elapsed):
                            self.assertEqual(state["phase"], phase)
                            self.assertIsNone(state["scenario_id"])
                            self.assert_baseline(state["vitals"])

    def test_custom_bounds_clamp_displayed_values_in_both_directions(self):
        for direction, ranges, expected_boundary in (
            ("down", {
                "hr": {"min": 80, "max": 81},
                "rr": {"min": 15, "max": 16},
                "temp": {"min": 37.0, "max": 37.1},
                "etco2": {"min": 35, "max": 36},
            }, "max"),
            ("up", {
                "hr": {"min": 110, "max": 120},
                "rr": {"min": 23, "max": 24},
                "temp": {"min": 38.8, "max": 39.1},
                "etco2": {"min": 40, "max": 45},
            }, "min"),
        ):
            self.time = 100.0
            config = deepcopy(self.config)
            config["baseline_vital_ranges"] = ranges
            service = self.service_for(config=config)
            self.call(service, "select_mode", mode="direct")
            for elapsed in (0, math.pi / 1.2, math.pi / .6, math.pi / .4):
                self.time = 100.0 + elapsed
                vitals = service.snapshot()["vitals"]
                with self.subTest(direction=direction, elapsed=elapsed):
                    self.assert_baseline(vitals, ranges)
                    for channel, bounds in ranges.items():
                        self.assertEqual(vitals[channel], bounds[expected_boundary])

    def test_invalid_baseline_ranges_are_rejected(self):
        cases = [
            ("missing configuration", None),
            ("not a mapping", []),
            ("missing channel", {k: deepcopy(v) for k, v in self.config["baseline_vital_ranges"].items() if k != "rr"}),
            ("extra channel", {**deepcopy(self.config["baseline_vital_ranges"]), "map": {"min": 60, "max": 100}}),
        ]
        for label, replacement in (
            ("not a bound mapping", None),
            ("missing minimum", {"max": 120}),
            ("missing maximum", {"min": 80}),
            ("reversed", {"min": 120, "max": 80}),
            ("zero", {"min": 0, "max": 120}),
            ("negative", {"min": -1, "max": 120}),
            ("boolean minimum", {"min": True, "max": 120}),
            ("boolean maximum", {"min": 80, "max": True}),
            ("string", {"min": "80", "max": 120}),
            ("NaN minimum", {"min": float("nan"), "max": 120}),
            ("NaN maximum", {"min": 80, "max": float("nan")}),
            ("infinite maximum", {"min": 80, "max": float("inf")}),
            ("infinite minimum", {"min": float("-inf"), "max": 120}),
            ("unrenderable integer precision", {"min": 80.5, "max": 120}),
        ):
            ranges = deepcopy(self.config["baseline_vital_ranges"])
            ranges["hr"] = replacement
            cases.append((label, ranges))
        ranges = deepcopy(self.config["baseline_vital_ranges"])
        ranges["temp"]["min"] = 38.15
        cases.append(("unrenderable temperature precision", ranges))

        for label, ranges in cases:
            config = deepcopy(self.config)
            if label == "missing configuration":
                del config["baseline_vital_ranges"]
            else:
                config["baseline_vital_ranges"] = ranges
            with self.subTest(case=label), self.assertRaises(ValueError):
                self.service_for(config=config)

    def test_equal_bounds_allow_a_fixed_baseline(self):
        config = deepcopy(self.config)
        fixed = {"hr": 100, "rr": 20, "temp": 38.5, "etco2": 40}
        config["baseline_vital_ranges"] = {
            channel: {"min": value, "max": value} for channel, value in fixed.items()
        }
        service = self.service_for(config=config)
        self.call(service, "select_mode", mode="direct")
        for elapsed in (0, 3, 6, 9, 12):
            self.time = 100.0 + elapsed
            with self.subTest(elapsed=elapsed):
                vitals = service.snapshot()["vitals"]
                self.assertEqual({channel: vitals[channel] for channel in fixed}, fixed)

    def test_scripted_complications_remain_abnormal_and_reset_restores_baseline(self):
        for scenario in self.config["scenarios"]:
            self.time = 100.0
            service = self.service_for()
            control = self.service_for()
            self.call(service, "select_mode", mode="direct")
            self.call(control, "select_mode", mode="direct")
            self.call(service, "configure", scenario_id=scenario)
            self.call(service, "start_scenario")
            self.call(service, "scenario_visible", scenario_id=scenario)
            targets = self.config["scenarios"][scenario]["target"]
            for elapsed in (0, 3, 6, 9, 12):
                self.time = 100.0 + elapsed
                changed = service.snapshot()["vitals"]
                normal = control.snapshot()["vitals"]
                with self.subTest(scenario=scenario, elapsed=elapsed):
                    for channel in normal.keys() - targets.keys():
                        self.assertEqual(changed[channel], normal[channel])
                    for channel, target in targets.items():
                        self.assertAlmostEqual(changed[channel], target, delta=1)
                        if channel in self.config["baseline_vital_ranges"]:
                            bounds = self.config["baseline_vital_ranges"][channel]
                            self.assertFalse(bounds["min"] <= changed[channel] <= bounds["max"])
            reset = self.call(service, "end")
            with self.subTest(scenario=scenario, phase="reset"):
                self.assertEqual(reset["phase"], "mode_selection")
                self.assertIsNone(reset["scenario_id"])
                self.assert_baseline(reset["vitals"])

    def test_snapshot_exposes_an_independent_copy_of_baseline_ranges(self):
        service = self.service_for()
        catalog = service.snapshot()["catalog"]
        self.assertEqual(catalog["baseline_vital_ranges"], self.config["baseline_vital_ranges"])
        catalog["baseline_vital_ranges"]["hr"]["min"] = 1
        del catalog["baseline_vital_ranges"]["rr"]["max"]
        self.assertEqual(service.config["baseline_vital_ranges"], self.config["baseline_vital_ranges"])
        self.assertEqual(service.snapshot()["catalog"]["baseline_vital_ranges"], self.config["baseline_vital_ranges"])


if __name__ == "__main__":
    unittest.main()
