"""Report integrity tests; external tools, browsers and services are never run."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIRECTORY))
import static_metrics

SPEC = importlib.util.spec_from_file_location("v2_application_report_runner", DIRECTORY / "run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ReportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def report(self, runtime=None):
        return {
            "generated_at_utc": "2026-10-24T00:00:00+00:00",
            "static": {
                "storage": {"application_raw": {"mb": 1.234}, "total_mb": 2.345},
                "maintainability": {
                    "mean_score_0_100": None,
                    "median_score_0_100": None,
                    "coverage": {
                        "python_files_analyzed": 0,
                        "python_files_eligible": 2,
                        "non_python_source_files_not_analyzed": 3,
                    },
                },
            },
            "model_complexity": {"status": "unavailable", "reason": "Node unavailable"},
            "runtime": runtime or {"status": "not_requested", "runs": []},
        }

    def collect_with_runtime(self, effects, *, modes=("normal", "aruco", "orb")):
        self.write("constraintv2/definitions.json", "{}")
        source = self.write("backend/main.py", "print('source')")
        static = {"storage": {"files": [{"path": source.relative_to(self.root).as_posix(), "application_payload": True}]}}
        fake_runtime = SimpleNamespace()
        with patch.object(runner, "collect_static_metrics", return_value=static), \
             patch.object(runner, "environment", return_value={}), \
             patch.object(runner, "model_complexity", return_value={"status": "unavailable"}), \
             patch.dict(sys.modules, {"runtime_metrics": fake_runtime}), \
             patch.object(fake_runtime, "run_runtime", side_effect=effects, create=True) as runtime_call, \
             contextlib.redirect_stdout(io.StringIO()):
            report = runner.collect(self.root, runtime=True, seconds=2, samples=3,
                                    repeats=len(effects), modes=modes)
        return report, runtime_call

    def test_missing_runtime_is_explicitly_unmeasured(self):
        text = runner.summary_markdown(self.report())
        self.assertIn("Not measured in this run", text)
        self.assertIn("Physical ESP32 input-to-display latency is unmeasured", text)
        self.assertNotIn("Mean RAM MB", text)
        self.assertIn("Not measured / 100", text)

    def test_both_runners_default_to_the_three_designs_only(self):
        import runtime_metrics
        expected = ("aruco", "orb", "optical-flow")
        self.assertEqual(runner.MODES, expected)
        self.assertEqual(runtime_metrics.MODES, expected)
        self.assertEqual(runner.collect.__kwdefaults__["modes"], expected)
        self.assertEqual(runtime_metrics.run_runtime.__kwdefaults__["modes"], expected)

    def test_design_only_view_excludes_normal_preserves_observations_and_original(self):
        report = self.report({"status": "partial", "runs": [{"status": "partial", "modes": [
            {"mode": "normal", "status": "unmeasured", "error": "Baseline failed"},
            {"mode": "aruco", "status": "measured", "latency": {"mean_ms": 12.5}},
            {"mode": "orb", "status": "measured", "latency": {"mean_ms": 17}},
            {"mode": "optical-flow", "status": "measured", "latency": {"mean_ms": 19}},
        ]}]})
        original = copy.deepcopy(report)
        selected = runner.select_design_report(report)
        self.assertEqual(report, original)
        self.assertEqual(selected["generated_at_utc"], report["generated_at_utc"])
        self.assertEqual([row["mode"] for row in selected["runtime"]["runs"][0]["modes"]], list(runner.MODES))
        self.assertEqual(selected["runtime"]["status"], "measured")
        self.assertEqual(selected["runtime"]["runs"][0]["modes"][0]["latency"]["mean_ms"], 12.5)
        self.assertFalse(selected["comparison_scope"]["normal_mode_included"])

    def test_missing_design_is_not_replaced_by_normal_or_marked_measured(self):
        report = self.report({"status": "measured", "runs": [{"status": "measured", "modes": [
            {"mode": "normal", "status": "measured"},
            {"mode": "aruco", "status": "measured"},
            {"mode": "orb", "status": "measured"},
        ]}]})
        selected = runner.select_design_report(report)
        self.assertEqual(selected["runtime"]["status"], "partial")
        self.assertEqual(selected["runtime"]["runs"][0]["missing_designs"], ["optical-flow"])
        self.assertIn("missing designs: optical-flow", runner.summary_markdown(selected))
        with self.assertRaises(ValueError):
            runner.select_design_report(report, ("normal",))

    def test_failed_mode_has_unknown_measurements_instead_of_zero(self):
        report = self.report({
            "status": "partial", "runs": [{"status": "partial", "modes": [{
                "mode": "orb", "status": "failed", "error": "Target did not initialize",
                "latency": {"attempted_samples": 3, "successful_samples": 0,
                            "mean_ms": None, "p95_ms": None},
                "memory": {"mean_mb": None, "sampled_peak_mb": None},
            }]}],
        })
        text = runner.summary_markdown(report)
        self.assertIn("| 1 | orb | failed | 0/3 | Not measured | Not measured | Not measured | Not measured |", text)
        self.assertIn("Repeat 1, orb: Target did not initialize", text)
        self.assertIn("Physical acquisition/transport and pixel presentation are excluded", text)

    def test_partial_summary_retains_observations_warnings_and_repeat_errors(self):
        report = self.report({
            "status": "partial", "runs": [
                {"status": "partial", "modes": [{
                    "mode": "aruco", "status": "measured",
                    "latency": {"successful_samples": 2, "attempted_samples": 3,
                                "mean_ms": 12.5, "p95_ms": 20},
                    "memory": {"mean_mb": 123.5, "sampled_peak_mb": 150},
                    "tracking_warning": "Marker was temporarily lost",
                }]},
                {"status": "unmeasured", "modes": [], "error": "Browser launch failed"},
            ],
        })
        original = copy.deepcopy(report)
        text = runner.summary_markdown(report)
        self.assertIn("| 1 | aruco | measured | 2/3 | 12.50 | 20.00 | 123.50 | 150.00 |", text)
        self.assertIn("Repeat 1, aruco: Marker was temporarily lost", text)
        self.assertIn("Repeat 2 error: Browser launch failed", text)
        self.assertEqual(report, original)

    def test_fingerprint_uses_only_application_payload_and_is_order_independent(self):
        self.write("backend/main.py", "print('one')")
        self.write("frontend/src/main.jsx", "export const version = 1;")
        self.write("README.md", "support documentation")
        inventory = [
            {"path": "frontend/src/main.jsx", "application_payload": True},
            {"path": "README.md", "application_payload": False},
            {"path": "does-not-exist.private", "application_payload": False},
            {"path": "backend/main.py", "application_payload": True},
        ]
        before = runner.fingerprint(self.root, inventory)
        after = runner.fingerprint(self.root, list(reversed(inventory)))
        self.assertEqual(before, after)
        self.assertEqual(before["errors"], [])
        self.assertEqual([row["path"] for row in before["files"]], ["backend/main.py", "frontend/src/main.jsx"])
        self.write("README.md", "changed support documentation")
        self.assertEqual(runner.fingerprint(self.root, inventory), before)
        self.write("backend/main.py", "print('two')")
        self.assertNotEqual(runner.fingerprint(self.root, inventory)["application_sha256"], before["application_sha256"])

    def test_application_fingerprint_respects_actual_storage_inventory_exclusions(self):
        self.write("backend/main.py", "print('app')")
        self.write("frontend/src/App.jsx", "export default () => null;")
        self.write("README.md", "documentation")
        self.write("constraintv2/run.py", "measurement tool")
        self.write("backend/data/student.json", '{"student": "private"}')
        self.write("frontend/dist/assets/app.js", "generated build")
        self.write("frontend/node_modules/package/index.js", "installed package")
        self.write(".env.local", "EXAMPLE_SECRET=private")
        inventory = static_metrics.measure_storage(self.root)
        result = runner.fingerprint(self.root, inventory["files"])
        self.assertEqual([row["path"] for row in result["files"]], ["backend/main.py", "frontend/src/App.jsx"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(inventory["files"]), 4)
        self.assertNotIn("private", json.dumps(result))

    def test_missing_included_source_invalidates_fingerprint_instead_of_silently_omitting(self):
        self.write("backend/main.py", "print('app')")
        result = runner.fingerprint(self.root, [
            {"path": "backend/main.py", "application_payload": True},
            {"path": "backend/missing.py", "application_payload": True},
        ])
        self.assertIsNone(result["application_sha256"])
        self.assertEqual(result["errors"][0]["path"], "backend/missing.py")
        self.assertEqual(len(result["files"]), 1)

    def test_build_fingerprint_is_separate_and_does_not_attest_source_linkage(self):
        self.write("frontend/src/App.jsx", "export const value = 1;")
        self.write("frontend/dist/assets/app.js", "compiled build one")
        inventory = [{"path": "frontend/src/App.jsx", "application_payload": True}]
        source_before = runner.fingerprint(self.root, inventory)
        build_before = runner.production_build(self.root)
        self.assertEqual(build_before["status"], "recorded")
        self.assertIn("Unverified", build_before["source_build_linkage"])
        self.assertEqual([row["path"] for row in build_before["fingerprint"]["files"]], ["frontend/dist/assets/app.js"])
        self.assertEqual(build_before["fingerprint"]["files"][0]["sha256"], hashlib.sha256(b"compiled build one").hexdigest())
        self.write("frontend/src/App.jsx", "export const value = 2;")
        source_after = runner.fingerprint(self.root, inventory)
        self.assertNotEqual(source_after["application_sha256"], source_before["application_sha256"])
        self.assertEqual(runner.production_build(self.root), build_before)
        self.write("frontend/dist/assets/app.js", "compiled build two")
        self.assertNotEqual(runner.production_build(self.root)["fingerprint"]["application_sha256"], build_before["fingerprint"]["application_sha256"])
        self.assertEqual(runner.fingerprint(self.root, inventory), source_after)

    def test_missing_production_build_is_unavailable(self):
        result = runner.production_build(self.root)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["fingerprint"]["files"], [])

    def test_partial_runtime_failures_are_preserved_and_mode_order_rotates(self):
        partial = {"status": "partial", "modes": [
            {"mode": "normal", "status": "measured", "latency": {"mean_ms": 15}},
            {"mode": "aruco", "status": "failed", "error": "Camera unavailable"},
        ]}
        completed = {"status": "measured", "modes": [{"mode": "orb", "status": "measured"}]}
        report, runtime_call = self.collect_with_runtime([
            partial, RuntimeError("Browser process exited"), completed,
        ])
        self.assertEqual(report["runtime"]["status"], "partial")
        self.assertEqual(report["runtime"]["runs"][0], partial)
        self.assertEqual(report["runtime"]["runs"][1], {"status": "unmeasured", "modes": [], "error": "Browser process exited"})
        self.assertEqual(report["runtime"]["runs"][2], completed)
        self.assertEqual([call.kwargs["modes"] for call in runtime_call.call_args_list], [
            ("normal", "aruco", "orb"), ("aruco", "orb", "normal"), ("orb", "normal", "aruco"),
        ])
        self.assertEqual(report["physical_sensor_latency"]["status"], "not_measured")
        json.dumps(report, allow_nan=False)

    def test_all_runtime_failures_remain_unmeasured_and_all_errors_survive(self):
        report, _ = self.collect_with_runtime([OSError("Cannot launch browser"), ValueError("No matching feedback")])
        self.assertEqual(report["runtime"]["status"], "unmeasured")
        self.assertEqual([run["error"] for run in report["runtime"]["runs"]], ["Cannot launch browser", "No matching feedback"])
        self.assertTrue(all(run["modes"] == [] for run in report["runtime"]["runs"]))


if __name__ == "__main__":
    unittest.main()
