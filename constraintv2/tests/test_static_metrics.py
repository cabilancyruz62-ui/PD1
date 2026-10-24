"""Storage accounting must exclude caches without excluding source assets."""

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import static_metrics


class StaticMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return target

    def test_source_models_and_assets_are_counted_with_decimal_mb(self):
        self.write("backend/main.py", b"x" * 100)
        self.write("frontend/src/dog.js", b"x" * 200)
        self.write("frontend/public/models/dog.glb", b"x" * 300)
        self.write("AR model/source.blend", b"x" * 400)
        self.write("designs/references/pad/photos/reference.jpg", b"x" * 500)
        self.write("frontend/public/models/dog.bin", b"x" * 600)
        result = static_metrics.measure_storage(self.root)
        self.assertEqual(result["total_bytes"], 2100)
        self.assertEqual(result["total_mb"], 0.0021)
        self.assertEqual(result["categories"]["source_code"]["bytes"], 300)
        self.assertEqual(result["categories"]["models_3d"]["bytes"], 700)
        self.assertEqual(result["categories"]["assets"]["bytes"], 1100)
        self.assertEqual(sum(row["bytes"] for row in result["categories"].values()), 2100)
        self.assertEqual(sum(row["bytes"] for row in result["by_top_level"].values()), 2100)

    def test_dependencies_builds_private_runtime_data_and_reports_are_excluded(self):
        keep = self.write("frontend/src/data/breeds.js", "export const breeds = []")
        excluded = [
            ".git/config", "frontend/node_modules/lib/index.js", "backend/.venv/lib.py",
            "frontend/dist/app.js", "backend/data/student.json", "backend/__pycache__/main.pyc",
            ".env.local", "constraint/runs/latest/summary.json", "constraint/design/results/frame.csv",
            "constraintv2/resultsv2/comparison.md", "constraintv2/resultsv2/measurements.json",
            "constraintv2/resultsv2/design1/constraints.json",
            "constraint/comparison.json", "constraintv2/reports/latest.json",
            "designs/references/pad/photo-check.json", "designs/references/pad/targets/artwork-check.json",
            "Microsoft/Windows/PowerShell/ModuleAnalysisCache", "releases/app.exe",
        ]
        for name in excluded:
            self.write(name, b"x" * 500)
        result = static_metrics.measure_storage(self.root)
        self.assertEqual(result["total_bytes"], keep.stat().st_size)
        self.assertEqual([item["path"] for item in result["files"]], ["frontend/src/data/breeds.js"])
        self.assertTrue(result["exclusions"])
        # Runtime data is a directory exclusion; JS source under src/data stays.
        self.assertIn("backend/data/", [item["path"] for item in result["exclusions"]])

    def test_documentation_tests_and_measurement_code_have_separate_totals(self):
        examples = {
            "README.md": "documentation", "frontend/tests/dog.test.js": "tests",
            "backend/test_tracking.py": "tests", "constraintv2/run.py": "measurement_tools",
            "frontend/package-lock.json": "project_metadata", "backend/requirements.txt": "project_metadata",
            "designs/targets/print.pdf": "assets", "odd.extension": "other",
        }
        for name in examples:
            self.write(name, b"abc")
        result = static_metrics.measure_storage(self.root)
        self.assertEqual({row["path"]: row["category"] for row in result["files"]}, examples)
        self.assertEqual(result["file_count"], len(examples))

    def test_symlinks_do_not_count_targets_twice_or_escape_the_tree(self):
        self.write("source.py", "print('hello')")
        try:
            (self.root / "linked.py").symlink_to(self.root / "source.py")
        except OSError as error:
            self.skipTest(f"Symlink creation is unavailable: {error}")
        result = static_metrics.measure_storage(self.root)
        self.assertEqual(result["file_count"], 1)
        self.assertIn("linked.py", [item["path"] for item in result["exclusions"]])

    def test_unavailable_radon_reports_unknown_not_zero_and_frontend_coverage_gap(self):
        self.write("backend/main.py", "print('hello')")
        self.write("frontend/src/App.jsx", "export default function App() { return null }")
        with patch.object(static_metrics.importlib, "import_module", side_effect=ModuleNotFoundError("radon")):
            result = static_metrics.collect_static_metrics(self.root)
        mi = result["maintainability"]
        self.assertEqual(mi["status"], "unavailable")
        self.assertIsNone(mi["mean_score_0_100"])
        self.assertIsNone(mi["score_0_100"])
        self.assertEqual(mi["coverage"]["python_files_eligible"], 1)
        self.assertEqual(mi["coverage"]["non_python_source_extensions_not_analyzed"], {".jsx": 1})
        self.assertFalse(mi["coverage"]["frontend_javascript_jsx_covered"])
        json.dumps(result, allow_nan=False)

    def test_radon_scores_only_python_source_and_labels_descriptive_aggregate(self):
        self.write("backend/main.py", "score_40")
        self.write("designs/design-1-aruco/tracker.py", "score_80")
        self.write("backend/test_main.py", "do not analyze")
        self.write("constraintv2/run.py", "do not analyze")
        self.write("frontend/src/App.jsx", "do not analyze")
        calls = []

        def calculate(source, multi):
            calls.append((source, multi))
            return {"score_40": 40, "score_80": 80}[source]

        fake_radon = SimpleNamespace(mi_visit=calculate)
        with patch.object(static_metrics.importlib, "import_module", return_value=fake_radon):
            result = static_metrics.measure_python_maintainability(self.root)
        self.assertEqual(result["status"], "measured")
        self.assertEqual(result["mean_score_0_100"], 60)
        self.assertEqual(result["median_score_0_100"], 60)
        self.assertIsNone(result["score_0_100"])
        self.assertEqual(calls, [("score_40", True), ("score_80", True)])
        self.assertEqual(result["coverage"]["python_files_analyzed"], 2)

    def test_application_payload_excludes_repository_support_but_includes_imported_designs(self):
        application = [
            "frontend/src/data/breeds.js", "frontend/public/models/dog.glb", "frontend/package.json",
            "backend/main.py", "backend/config/assessment.json", "AR model/dog.blend",
            "designs/run.py", "designs/tracking_common.py", "designs/design-2-orb-ransac/tracker.py",
        ]
        support = [
            "docs/guide.md", "backend/test_main.py", "constraintv2/run.py", "designs/inspect_reference.py",
            "designs/references/pad/photos/reference.jpg", "frontend/public/models/README.md",
        ]
        for path in application + support:
            self.write(path, b"x" * 10)
        result = static_metrics.measure_storage(self.root)
        self.assertEqual(result["application_raw"]["bytes"], len(application) * 10)
        self.assertEqual(result["repository_support"]["bytes"], len(support) * 10)
        self.assertEqual(result["total_bytes"], result["application_raw"]["bytes"] + result["repository_support"]["bytes"])
        self.assertEqual({row["path"] for row in result["files"] if row["application_payload"]}, set(application))

    def test_radon_error_does_not_silently_produce_a_successful_full_measurement(self):
        self.write("backend/main.py", "valid")
        self.write("backend/broken.py", "broken")

        def calculate(source, multi):
            if source == "broken":
                raise SyntaxError("invalid source")
            return 70

        with patch.object(static_metrics.importlib, "import_module", return_value=SimpleNamespace(mi_visit=calculate)):
            result = static_metrics.measure_python_maintainability(self.root)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["mean_score_0_100"], 70)
        self.assertEqual(result["errors"][0]["path"], "backend/broken.py")
        self.assertEqual(result["coverage"]["python_files_analyzed"], 1)

    def test_empty_project_has_zero_storage_and_no_fabricated_mi(self):
        with patch.object(static_metrics.importlib, "import_module", return_value=SimpleNamespace(mi_visit=lambda *args, **kwargs: 100)):
            result = static_metrics.collect_static_metrics(self.root)
        self.assertEqual(result["storage"]["total_bytes"], 0)
        self.assertEqual(result["maintainability"]["status"], "not_applicable")
        self.assertIsNone(result["maintainability"]["mean_score_0_100"])


if __name__ == "__main__":
    unittest.main()
