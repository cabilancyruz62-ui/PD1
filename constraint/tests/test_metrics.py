"""Check that benchmark scores distinguish correct tracking from false claims."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metrics import evaluate_constraints, score_frame, summarize_frames


QUAD = np.array([[10, 10], [110, 10], [110, 110], [10, 110]], dtype=float)


def result(corners=QUAD, tracked=True):
    return SimpleNamespace(corners=corners, tracked=tracked)


def row(visible=True, corners=QUAD, elapsed=10, tracked=True, **extra):
    return {"expected_visible": visible, "elapsed_ms": elapsed,
            **score_frame(result(corners, tracked), QUAD if visible else None, visible), **extra}


class FrameScoringTests(unittest.TestCase):
    def test_corner_error_is_mean_euclidean_pixels_with_inclusive_threshold(self):
        score = score_frame(result(QUAD + [3, 4]), QUAD, True, tolerance_px=5)
        self.assertEqual(score["corner_error_px"], 5.0)
        self.assertTrue(score["correct"])
        self.assertFalse(score_frame(result(QUAD + [3, 4.1]), QUAD, True)["correct"])

    def test_tracker_status_does_not_substitute_for_ground_truth(self):
        self.assertFalse(score_frame(result(QUAD + 50), QUAD, True)["correct"])
        self.assertFalse(score_frame(result(tracked=False), QUAD, True)["correct"])
        self.assertFalse(score_frame(result(), None, True)["correct"])

    def test_corner_correspondence_is_not_reordered_to_hide_wrong_pose(self):
        self.assertFalse(score_frame(result(np.roll(QUAD, 1, axis=0)), QUAD, True)["correct"])

    def test_invalid_quads_never_pass(self):
        invalid = [None, [], [[1, 2]], "invalid", np.full((4, 2), np.nan),
                   np.full((4, 2), np.inf), np.zeros((4, 2)),
                   QUAD[[0, 2, 1, 3]], np.array([[0, 0], [1, 0], [2, 0], [3, 0]])]
        for corners in invalid:
            with self.subTest(corners=corners):
                score = score_frame(result(corners), QUAD, True)
                self.assertFalse(score["correct"])
                self.assertIsNone(score["corner_error_px"])

    def test_absent_claim_is_false_positive_even_with_malformed_polygon(self):
        score = score_frame(result(np.full((4, 2), np.nan)), None, False)
        self.assertTrue(score["false_positive"])
        self.assertFalse(score["correct"])
        self.assertIsNone(score["corner_error_px"])
        self.assertFalse(score_frame(result(tracked=False), None, False)["false_positive"])

    def test_invalid_tolerance_is_rejected(self):
        for tolerance in (-1, float("nan"), float("inf"), True):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                score_frame(result(), QUAD, True, tolerance)


class SummaryTests(unittest.TestCase):
    def test_summary_uses_visible_accuracy_and_absence_denominators(self):
        rows = [row(elapsed=10), row(corners=QUAD + 20, elapsed=20),
                row(visible=False, tracked=True, elapsed=30),
                row(visible=False, tracked=False, elapsed=40)]
        metrics = summarize_frames(rows)
        self.assertEqual(metrics["correct_frames"], 1)
        self.assertEqual(metrics["visible_frames"], 2)
        self.assertEqual(metrics["absent_frames"], 2)
        self.assertEqual(metrics["valid_tracking_pct"], 50)
        self.assertEqual(metrics["false_positive_pct"], 50)
        self.assertEqual(metrics["processing_median_ms"], 25)
        self.assertAlmostEqual(metrics["processing_p95_ms"], 38.5)
        self.assertEqual(metrics["processing_max_ms"], 40)
        self.assertEqual(metrics["tracking_throughput_fps"], 40)
        self.assertAlmostEqual(metrics["corner_error_median_px"], np.sqrt(800) / 2)

    def test_empty_summary_is_json_safe_and_has_unknown_not_zero_accuracy(self):
        metrics = summarize_frames([])
        for key in ("valid_tracking_pct", "false_positive_pct", "processing_p95_ms",
                    "tracking_throughput_fps", "tracking_error_jitter_rms_px"):
            self.assertIsNone(metrics[key])
        json.dumps(metrics, allow_nan=False)

    def test_missing_correct_field_does_not_count_claimed_tracking_as_correct(self):
        metrics = summarize_frames([{"expected_visible": True, "tracked": True}])
        self.assertEqual(metrics["valid_tracking_pct"], 0)
        self.assertIsNone(metrics["false_positive_pct"])

    def test_invalid_values_are_excluded_from_numeric_aggregates(self):
        rows = [row(elapsed=0), row(elapsed=float("nan"), corner_error_px=float("inf")),
                row(elapsed=-1, corner_error_px=-1), row(elapsed=None, corner_error_px=None)]
        metrics = summarize_frames(rows)
        self.assertEqual(metrics["processing_p95_ms"], 0)
        self.assertEqual(metrics["corner_error_p95_px"], 0)
        self.assertIsNone(metrics["tracking_throughput_fps"])
        json.dumps(metrics, allow_nan=False)

    def test_jitter_removes_constant_bias_and_uses_two_dimensional_rms(self):
        rows = [row(center_residual_x=9, center_residual_y=18),
                row(center_residual_x=11, center_residual_y=22)]
        self.assertAlmostEqual(summarize_frames(rows)["tracking_error_jitter_rms_px"], np.sqrt(5))
        self.assertIsNone(summarize_frames(rows[:1])["tracking_error_jitter_rms_px"])
        rows[1]["tracked"] = False
        self.assertIsNone(summarize_frames(rows)["tracking_error_jitter_rms_px"])

    def test_invalid_capture_settings_are_rejected(self):
        for fps in (0, -1, float("nan")):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                summarize_frames([], source_fps=fps)


class ConstraintEvaluationTests(unittest.TestCase):
    def test_limits_are_inclusive_and_rendering_is_unmeasured(self):
        metrics = {"valid_tracking_pct": 95, "false_positive_pct": 1, "processing_p95_ms": 33}
        checks = evaluate_constraints(metrics, 1, 60, {})
        for key in ("memory", "response_time", "tracking_performance", "cpu"):
            self.assertEqual(checks[key]["status"], "pass")
        self.assertEqual(checks["rendering_fps"]["status"], "not_applicable")
        self.assertIsNone(checks["rendering_fps"]["observed"])
        self.assertEqual(checks["memory"]["unit"], "GB")
        json.dumps(checks, allow_nan=False)

    def test_limits_fail_for_over_budget_or_false_tracking(self):
        metrics = {"valid_tracking_pct": 100, "false_positive_pct": 2, "processing_p95_ms": 34}
        checks = evaluate_constraints(metrics, 1.1, 61)
        for key in ("memory", "response_time", "tracking_performance", "cpu"):
            self.assertEqual(checks[key]["status"], "fail")

    def test_absent_only_can_fail_false_positives_but_cannot_pass_accuracy(self):
        metrics = summarize_frames([row(visible=False, tracked=False)])
        self.assertEqual(evaluate_constraints(metrics, None, None)["tracking_performance"]["status"],
                         "insufficient_data")
        metrics = summarize_frames([row(visible=False, tracked=True)])
        self.assertEqual(evaluate_constraints(metrics, None, None)["tracking_performance"]["status"], "fail")

    def test_unavailable_resource_data_are_not_reported_as_passes(self):
        checks = evaluate_constraints({}, float("nan"), None)
        for key in ("memory", "response_time", "tracking_performance", "cpu"):
            self.assertEqual(checks[key]["status"], "insufficient_data")
        json.dumps(checks, allow_nan=False)

    def test_visible_only_cannot_pass_without_absence_checks(self):
        checks = evaluate_constraints({"valid_tracking_pct": 100}, 0.1, 5)
        self.assertEqual(checks["tracking_performance"]["status"], "insufficient_data")
        checks = evaluate_constraints({"valid_tracking_pct": 50}, 0.1, 5)
        self.assertEqual(checks["tracking_performance"]["status"], "fail")

    def test_limits_can_be_configured(self):
        checks = evaluate_constraints({"valid_tracking_pct": 90, "false_positive_pct": 0, "processing_p95_ms": 40}, 2, 75,
                                      {"memory_gb": 2, "response_p95_ms": 40,
                                       "tracking_success_pct": 90, "cpu_pct": 75})
        for key in ("memory", "response_time", "tracking_performance", "cpu"):
            self.assertEqual(checks[key]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
