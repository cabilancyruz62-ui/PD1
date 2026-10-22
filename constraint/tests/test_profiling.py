import json
import math
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import psutil

from constraint.profiling import ResourceMonitor, environment_info


class FakeProcess:
    def __init__(self):
        self.cpu = 0.0
        self.rss = 100_000_000

    def cpu_times(self):
        return SimpleNamespace(user=self.cpu, system=0.0)

    def memory_info(self):
        return SimpleNamespace(rss=self.rss, peak_wset=200_000_000)


class ProfilingTests(unittest.TestCase):
    def test_cpu_normalization_and_decimal_memory(self):
        process = FakeProcess()
        with patch("constraint.profiling.time.perf_counter", side_effect=[10.0, 12.0]):
            with ResourceMonitor(60, process=process, logical_cpu_count=4) as monitor:
                process.cpu = 2.0
                process.rss = 150_000_000
                monitor.observe()
        result = monitor.summary()
        self.assertEqual(result["cpu_one_core_pct"], 100.0)
        self.assertEqual(result["cpu_normalized_pct"], 25.0)
        self.assertEqual(result["baseline_memory_gb"], 0.1)
        self.assertEqual(result["peak_memory_gb"], 0.15)
        self.assertEqual(result["windows_lifetime_peak_working_set_gb"], 0.2)
        self.assertFalse(monitor._thread.is_alive())

    def test_live_allocations_cpu_and_periodic_sampling(self):
        with ResourceMonitor(0.005) as monitor:
            allocation = bytearray(2_000_000)
            deadline = time.perf_counter() + 0.1
            while time.perf_counter() < deadline:
                sum(range(1000))
                time.sleep(0.001)
            monitor.observe()
            self.assertEqual(len(allocation), 2_000_000)
        result = monitor.summary()
        for key in ("peak_memory_gb", "cpu_normalized_pct", "cpu_seconds", "wall_seconds"):
            self.assertTrue(math.isfinite(result[key]), key)
            self.assertGreaterEqual(result[key], 0, key)
        self.assertGreaterEqual(result["peak_memory_gb"], result["baseline_memory_gb"])
        self.assertGreater(result["samples"], 3)
        self.assertFalse(monitor._thread.is_alive())
        json.dumps(result, allow_nan=False)

    def test_unavailable_process_metrics_are_null(self):
        process = FakeProcess()
        process.cpu_times = lambda: (_ for _ in ()).throw(psutil.AccessDenied())
        process.memory_info = process.cpu_times
        with ResourceMonitor(60, process=process) as monitor:
            self.assertIsNone(monitor.observe())
        result = monitor.summary()
        for key in ("peak_memory_gb", "baseline_memory_gb", "cpu_seconds", "cpu_normalized_pct"):
            self.assertIsNone(result[key])
        self.assertEqual(result["samples"], 0)
        self.assertEqual(len(result["measurement_errors"]), 2)

    def test_sampler_stops_when_workload_raises(self):
        with self.assertRaisesRegex(ValueError, "workload"):
            with ResourceMonitor(0.005) as monitor:
                raise ValueError("workload")
        self.assertFalse(monitor._thread.is_alive())
        self.assertGreaterEqual(monitor.summary()["samples"], 2)
        with self.assertRaises(RuntimeError):
            monitor.__enter__()

    def test_validation_and_summary_lifecycle(self):
        for interval in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                ResourceMonitor(interval)
        with self.assertRaises(RuntimeError):
            ResourceMonitor().summary()

    def test_environment_metadata_is_json_serializable(self):
        result = environment_info()
        self.assertGreater(result["total_ram_gb"], 0)
        self.assertIn("opencv_version", result)
        self.assertIsNone(result["gpu"])
        self.assertNotIn("hostname", result)
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
