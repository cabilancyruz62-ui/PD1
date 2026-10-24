"""Tests for honest runtime aggregation; no real browser or services are started."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


PATH = Path(__file__).resolve().parents[1] / "runtime_metrics.py"
SPEC = importlib.util.spec_from_file_location("v2_runtime_metrics", PATH)
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class FakeProcessError(Exception):
    pass


class FakeProcess:
    def __init__(self, pid, rss, children=(), vanished=False):
        self.pid, self.rss, self.descendants, self.vanished = pid, rss, children, vanished

    def children(self, recursive):
        assert recursive
        return self.descendants

    def memory_info(self):
        if self.vanished:
            raise FakeProcessError("Exited between enumeration and sampling")
        return SimpleNamespace(rss=self.rss)


class RuntimeAggregationTests(unittest.TestCase):
    def test_percentiles_interpolate_and_single_sample_remains_observation(self):
        self.assertEqual(runtime.percentile([100, 20, 40, 60], 50), 50)
        self.assertAlmostEqual(runtime.percentile([100, 20, 40, 60], 95), 94)
        self.assertEqual(runtime.percentile([12], 95), 12)
        for values in ([], [float("nan")], [float("inf")]):
            with self.assertRaises(ValueError):
                runtime.percentile(values, 50)

    def test_failed_latency_trials_are_not_reported_as_zero(self):
        result = runtime.summarize_latency([
            {"status": "measured", "elapsed_ms": 20},
            {"status": "failed", "error": "No matching display"},
            {"status": "measured", "elapsed_ms": 40},
        ])
        self.assertEqual(result["attempted_samples"], 3)
        self.assertEqual(result["successful_samples"], 2)
        self.assertEqual(result["failed_samples"], 1)
        self.assertEqual(result["mean_ms"], 30)
        self.assertEqual(result["p95_ms"], 39)

    def test_unmeasured_latency_keeps_null_summary(self):
        result = runtime.summarize_latency([{"status": "failed", "error": "Timeout"}])
        self.assertIsNone(result["p50_ms"])
        self.assertIsNone(result["p95_ms"])
        for value in (True, None, -1, float("nan"), float("inf"), "20"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime.summarize_latency([{"status": "measured", "elapsed_ms": value}])

    def test_owned_process_tree_sums_browser_children_and_backend_once(self):
        child = FakeProcess(12, 5_000_000)
        browser = FakeProcess(11, 10_000_000, (child, child))
        backend = FakeProcess(21, 20_000_000)
        fake = SimpleNamespace(Process={11: browser, 21: backend}.__getitem__, NoSuchProcess=FakeProcessError, AccessDenied=FakeProcessError)
        result = runtime.process_tree_rss({"browser": 11, "backend": 21}, fake)
        self.assertTrue(result["valid"])
        self.assertEqual(result["rss_bytes"], 35_000_000)
        self.assertEqual(result["components"]["browser"]["process_count"], 2)
        self.assertEqual(result["components"]["browser"]["pids"], [11, 12])

    def test_missing_root_invalidates_total_while_vanished_child_is_recorded(self):
        browser = FakeProcess(11, 10_000_000, (FakeProcess(12, 5_000_000, vanished=True),))
        def find(pid):
            if pid != 11:
                raise FakeProcessError("Missing root")
            return browser
        fake = SimpleNamespace(Process=find, NoSuchProcess=FakeProcessError, AccessDenied=FakeProcessError)
        result = runtime.process_tree_rss({"browser": 11, "backend": 21}, fake)
        self.assertFalse(result["valid"])
        self.assertIsNone(result["rss_bytes"])
        self.assertEqual(result["missing_roots"], ["backend"])
        self.assertEqual(result["vanished_children"], [12])

    def test_memory_uses_decimal_megabytes_and_sampled_peak(self):
        observations = [
            {"valid": True, "rss_bytes": 30_000_000, "components": {"browser": {"rss_bytes": 20_000_000}, "backend": {"rss_bytes": 10_000_000}}},
            {"valid": False, "rss_bytes": None, "components": {}},
            {"valid": True, "rss_bytes": 50_000_000, "components": {"browser": {"rss_bytes": 30_000_000}, "backend": {"rss_bytes": 20_000_000}}},
        ]
        result = runtime.summarize_memory(observations)
        self.assertEqual(result["mean_mb"], 40)
        self.assertEqual(result["sampled_peak_mb"], 50)
        self.assertEqual(result["failed_samples"], 1)
        self.assertEqual(result["components"]["browser"]["mean_mb"], 25)
        self.assertIn("Shared pages", result["shared_page_caveat"])

    def test_root_exiting_during_sampling_does_not_become_zero_memory(self):
        process = FakeProcess(11, 0, vanished=True)
        fake = SimpleNamespace(Process=lambda pid: process, NoSuchProcess=FakeProcessError, AccessDenied=FakeProcessError)
        result = runtime.process_tree_rss({"browser": 11}, fake)
        self.assertFalse(result["valid"])
        self.assertIsNone(result["rss_bytes"])

    def test_empty_memory_is_not_zero_usage(self):
        result = runtime.summarize_memory([])
        self.assertIsNone(result["mean_mb"])
        self.assertIsNone(result["sampled_peak_mb"])

    def test_invalid_runtime_arguments_fail_before_any_service_start(self):
        for fields in ({"seconds": 0}, {"seconds": float("nan")}, {"seconds": True}, {"samples": 0}, {"samples": True}, {"modes": ["orb", "orb"]}, {"modes": ["unknown"]}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                runtime.run_runtime(Path.cwd(), **fields)

    def test_edge_port_poll_retries_lock_empty_and_incomplete_writes(self):
        browser = SimpleNamespace(poll=Mock(return_value=None))
        values = [PermissionError("Edge is still writing"), "", "9001", "65536\n/devtools/browser/example", "9001\n/devtools/browser/example\n"]
        with patch.object(Path, "read_text", side_effect=values) as read, patch.object(runtime.time, "sleep") as sleep:
            self.assertEqual(runtime._wait_debug_port(Path("unused-profile"), browser), 9001)
        self.assertEqual(read.call_count, 5)
        self.assertEqual(sleep.call_count, 4)

    def test_edge_port_poll_stops_when_owned_browser_has_exited(self):
        browser = SimpleNamespace(poll=Mock(return_value=7))
        with patch.object(Path, "read_text") as read, self.assertRaisesRegex(TimeoutError, "exit 7"):
            runtime._wait_debug_port(Path("unused-profile"), browser)
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
