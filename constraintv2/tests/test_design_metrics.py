"""Per-design accounting must not attribute the shared application to each tracker."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from design_metrics import DESIGNS, collect_design_metrics
from static_metrics import measure_storage


class DesignMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def static_report(self):
        return {
            "storage": measure_storage(self.root),
            "maintainability": {
                "status": "measured", "method": "Radon per-file MI", "radon_version": "test-version",
                "files": [{"path": path, "score_0_100": 40 + index} for index, (_, _, path) in enumerate(DESIGNS)],
                "errors": [],
            },
        }

    def test_own_source_only_excludes_shared_runtime_assets_and_support(self):
        for index, (_, _, path) in enumerate(DESIGNS, 1):
            self.write(path, b"x" * (index * 100))
        for path in ("designs/tracking_common.py", "backend/main.py", "frontend/src/App.jsx", "frontend/public/models/dog.glb", "designs/references/marker.png", "designs/design-1-aruco/README.md"):
            self.write(path, b"shared" * 1000)
        original = self.static_report()
        before = copy.deepcopy(original)
        report = collect_design_metrics(original)
        self.assertEqual(report["status"], "measured")
        self.assertEqual([row["id"] for row in report["designs"]], ["aruco", "orb", "optical-flow"])
        self.assertEqual([row["storage"]["bytes"] for row in report["designs"]], [100, 200, 300])
        self.assertEqual([row["storage"]["mb"] for row in report["designs"]], [0.0001, 0.0002, 0.0003])
        self.assertEqual([row["maintainability"]["score_0_100"] for row in report["designs"]], [40, 41, 42])
        self.assertEqual(report["designs"][0]["maintainability"]["radon_version"], "test-version")
        self.assertIn("not standalone application", report["designs"][0]["storage"]["scope"])
        self.assertIn("not a whole-application", report["designs"][0]["maintainability"]["scope"])
        self.assertEqual(original, before)

    def test_missing_tracker_is_unknown_even_if_stale_mi_exists(self):
        self.write(DESIGNS[0][2], b"present")
        report = collect_design_metrics(self.static_report())
        self.assertEqual(report["status"], "partial")
        for row in report["designs"][1:]:
            self.assertEqual(row["storage"]["status"], "unavailable")
            self.assertIsNone(row["storage"]["bytes"])
            self.assertIsNone(row["storage"]["mb"])
            self.assertIsNone(row["maintainability"]["score_0_100"])
            self.assertIn("absent", row["maintainability"]["reason"])

    def test_unavailable_analyzer_does_not_fabricate_per_design_scores(self):
        for _, _, path in DESIGNS:
            self.write(path, b"pass\n")
        report = self.static_report()
        report["maintainability"] = {"status": "unavailable", "files": [], "reason": "Radon is not installed"}
        result = collect_design_metrics(report)
        self.assertEqual(result["status"], "partial")
        for row in result["designs"]:
            self.assertEqual(row["storage"]["status"], "measured")
            self.assertIsNone(row["maintainability"]["score_0_100"])
            self.assertEqual(row["maintainability"]["reason"], "Radon is not installed")

    def test_empty_inventory_is_unavailable_instead_of_zero(self):
        result = collect_design_metrics({})
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(len(result["designs"]), 3)
        self.assertTrue(all(row["storage"]["bytes"] is None for row in result["designs"]))
        json.dumps(result, allow_nan=False)

    def test_real_zero_observations_are_distinct_from_missing_data(self):
        self.write(DESIGNS[0][2], b"")
        report = self.static_report()
        report["maintainability"]["files"][0]["score_0_100"] = 0
        result = collect_design_metrics(report)["designs"][0]
        self.assertEqual(result["storage"]["status"], "measured")
        self.assertEqual(result["storage"]["bytes"], 0)
        self.assertEqual(result["storage"]["mb"], 0)
        self.assertEqual(result["maintainability"]["status"], "measured")
        self.assertEqual(result["maintainability"]["score_0_100"], 0)

    def test_invalid_observations_remain_unknown_and_specific_errors_survive(self):
        path = DESIGNS[0][2]
        for score in (True, -1, 101, float("nan"), float("inf"), "45"):
            with self.subTest(score=score):
                report = {
                    "storage": {"files": [{"path": path, "bytes": -1}]},
                    "maintainability": {"files": [{"path": path, "score_0_100": score}], "errors": [{"path": path, "reason": "Source could not be analyzed"}]},
                }
                result = collect_design_metrics(report)
                row = result["designs"][0]
                self.assertIsNone(row["storage"]["bytes"])
                self.assertIsNone(row["maintainability"]["score_0_100"])
                self.assertEqual(row["maintainability"]["reason"], "Source could not be analyzed")
                json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
