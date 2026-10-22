"""Exercise isolated benchmark workers, reports, and real tracker integration."""

import csv
from contextlib import redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("constraint_runner", ROOT / "run.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BenchmarkRunnerTests(unittest.TestCase):
    def test_all_real_trackers_write_scored_reports_and_gpu_stays_unmeasured(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "run.py"), "--frames", "6", "--repeats", "1",
                 "--warmup", "2", "--conditions", "stationary", "target_absent", "occlusion_recovery",
                 "--unpaced", "--opencv-threads", "1", "--output-root", directory],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            comparison = json.loads((Path(directory) / "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual(len(comparison), 3)
            for summary in comparison:
                self.assertEqual(summary["metrics"]["total_frames"], 18)
                self.assertEqual(summary["metrics"]["visible_frames"], 10)
                self.assertEqual(summary["metrics"]["false_positive_frames"], 0)
                expected = 80 if summary["design"] == "optical-flow" else 100
                self.assertEqual(summary["metrics"]["valid_tracking_pct"], expected)
                self.assertEqual(summary["by_condition"]["stationary"]["valid_tracking_pct"], 100)
                self.assertGreater(summary["resources"]["peak_memory_gb"], 0)
                self.assertEqual(summary["constraints"]["rendering_fps"]["status"], "not_applicable")
                self.assertIsNone(summary["constraints"]["rendering_fps"]["observed"])
                self.assertTrue(summary["source_sha256"])
                folder = Path(directory) / summary["folder"] / "results"
                self.assertIn("synthetic", (folder / "summary.md").read_text(encoding="utf-8"))
                with (folder / "frames.csv").open(newline="", encoding="utf-8") as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))), 18)
                self.assertEqual(len(json.loads((folder / "trials.json").read_text(encoding="utf-8"))), 3)

    def test_invalid_limits_are_rejected(self):
        limits = json.loads((ROOT / "limits.json").read_text(encoding="utf-8"))
        for key, value in (("memory_gb", -1), ("cpu_pct", 101), ("response_p95_ms", True), ("corner_tolerance_px", float("nan"))):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "limits.json"
                path.write_text(json.dumps({**limits, key: value}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    module.read_limits(path)

    def test_invalid_capture_or_worker_settings_fail_before_work(self):
        for arguments in (["--frames", "2"], ["--fps", "0"], ["--width", "100"],
                          ["--worker"], ["--conditions", "stationary", "stationary"]):
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                module.parse_args(arguments)


if __name__ == "__main__":
    unittest.main()
