"""CPU aggregation tests with fake process trees; no services are started."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


PATH = Path(__file__).resolve().parents[1] / "runtime_metrics.py"
SPEC = importlib.util.spec_from_file_location("v2_cpu_runtime_metrics", PATH)
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class FakeProcessError(Exception):
    pass


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds=1):
        self.value += seconds


class FakeProcess:
    def __init__(self, pid, *, created=10.0, user=0.0, system=0.0, children=()):
        self.pid, self.created = pid, created
        self.user, self.system, self.descendants = user, system, list(children)
        self.failed = False

    def create_time(self):
        if self.failed:
            raise FakeProcessError("Process unavailable")
        return self.created

    def cpu_times(self):
        if self.failed:
            raise FakeProcessError("CPU reading unavailable")
        # Child aggregate counters must be ignored to avoid double counting.
        return SimpleNamespace(user=self.user, system=self.system, children_user=999, children_system=999)

    def children(self, recursive):
        assert recursive
        if self.failed:
            raise FakeProcessError("Children unavailable")
        return self.descendants


class FakePsutil:
    NoSuchProcess = AccessDenied = FakeProcessError

    def __init__(self, processes, count=4):
        self.processes = {process.pid: process for process in processes}
        self.count = count

    def Process(self, pid):
        try:
            return self.processes[pid]
        except KeyError:
            raise FakeProcessError("Root vanished") from None

    def cpu_count(self, logical):
        assert logical
        return self.count


def observation(percent, interval, *, count=4):
    return {"valid": True, "normalized_pct": percent, "interval_seconds": interval,
            "cpu_seconds": percent / 100 * interval * count, "logical_cpu_count": count, "components": {}}


class CpuSamplingTests(unittest.TestCase):
    def setUp(self):
        self.browser = FakeProcess(11, user=40)
        self.backend = FakeProcess(21, user=10)
        self.clock = FakeClock()
        self.psutil = FakePsutil([self.browser, self.backend])
        self.sampler = runtime.ProcessTreeCpuSampler({"browser": 11, "backend": 21}, self.psutil, self.clock)

    def test_all_logical_cpus_busy_is_100_percent_with_no_duplicate_pids(self):
        child = FakeProcess(12, user=30)
        self.browser.descendants = [child, child]
        self.psutil.count = 2
        self.sampler.logical_cpu_count = 2
        self.sampler.prime()
        self.browser.user += 1
        self.backend.system += .5
        child.system += .5
        self.clock.advance()
        result = self.sampler.sample()
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized_pct"], 100)
        self.assertEqual(result["cpu_seconds"], 2)
        self.assertEqual(result["components"]["browser"]["pids"], [11, 12])
        self.assertEqual(result["components"]["browser"]["normalized_pct"], 75)

    def test_one_busy_logical_cpu_on_four_cpu_machine_is_25_percent(self):
        self.sampler.prime()
        self.browser.user += 1
        self.clock.advance()
        result = self.sampler.sample()
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized_pct"], 25)

    def test_actual_zero_cpu_delta_is_a_valid_zero(self):
        self.sampler.prime()
        self.clock.advance()
        result = self.sampler.sample()
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized_pct"], 0)
        self.assertEqual(result["cpu_seconds"], 0)

    def test_new_child_lifetime_is_not_charged_to_first_observation(self):
        self.sampler.prime()
        child = FakeProcess(12, created=11, user=50)
        self.browser.descendants = [child]
        self.browser.user += .2
        self.clock.advance()
        first = self.sampler.sample()
        self.assertTrue(first["valid"])
        self.assertAlmostEqual(first["normalized_pct"], 5)
        self.assertEqual(first["new_processes"], [{"pid": 12, "create_time": 11}])
        child.system += .4
        self.browser.user += .2
        self.clock.advance()
        second = self.sampler.sample()
        self.assertTrue(second["valid"])
        self.assertAlmostEqual(second["normalized_pct"], 15)

    def test_child_pid_reuse_gets_new_baseline(self):
        child = FakeProcess(12, created=10, user=3)
        self.browser.descendants = [child]
        self.sampler.prime()
        self.browser.descendants = [FakeProcess(12, created=11, user=100)]
        self.browser.user += .4
        self.clock.advance()
        result = self.sampler.sample()
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["normalized_pct"], 10)
        self.assertEqual(result["new_processes"], [{"pid": 12, "create_time": 11}])
        self.assertEqual(result["disappeared_processes"], [{"pid": 12, "create_time": 10}])

    def test_reused_owned_root_is_unknown_instead_of_measuring_other_process(self):
        self.sampler.prime()
        self.psutil.processes[11] = FakeProcess(11, created=99, user=100)
        self.clock.advance()
        result = self.sampler.sample()
        self.assertFalse(result["valid"])
        self.assertIsNone(result["normalized_pct"])
        self.assertIn("reused", result["process_errors"][0]["reason"])

    def test_missing_root_is_unknown_not_zero(self):
        self.sampler.prime()
        del self.psutil.processes[21]
        self.clock.advance()
        result = self.sampler.sample()
        self.assertFalse(result["valid"])
        self.assertIsNone(result["cpu_seconds"])
        self.assertIsNone(result["normalized_pct"])

    def test_unreadable_child_is_unknown_and_recovery_rebaselines(self):
        child = FakeProcess(12, user=1)
        self.browser.descendants = [child]
        self.sampler.prime()
        child.failed = True
        self.clock.advance()
        self.assertFalse(self.sampler.sample()["valid"])
        child.failed = False
        child.user += 1
        self.clock.advance()
        self.assertFalse(self.sampler.sample()["valid"])
        child.user += 1
        self.clock.advance()
        recovered = self.sampler.sample()
        self.assertTrue(recovered["valid"])
        self.assertEqual(recovered["normalized_pct"], 25)

    def test_departed_child_is_recorded_with_unobserved_final_delta_caveat(self):
        child = FakeProcess(12, user=1)
        self.browser.descendants = [child]
        self.sampler.prime()
        self.browser.descendants = []
        self.browser.system += .2
        self.clock.advance()
        result = self.sampler.sample()
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["normalized_pct"], 5)
        self.assertEqual(result["disappeared_processes"], [{"pid": 12, "create_time": 10.0}])
        summary = runtime.summarize_cpu([result])
        self.assertIn("last sighting", summary["process_lifetime_caveat"])

    def test_overlapping_roots_and_children_count_each_identity_once(self):
        self.browser.descendants = [self.backend]
        self.sampler.prime()
        self.backend.user += 1
        self.clock.advance()
        result = self.sampler.sample()
        self.assertTrue(result["valid"])
        self.assertEqual(result["cpu_seconds"], 1)
        self.assertEqual(result["normalized_pct"], 25)

    def test_decreasing_cpu_time_invalidates_interval(self):
        self.sampler.prime()
        self.browser.user -= 1
        self.clock.advance()
        result = self.sampler.sample()
        self.assertFalse(result["valid"])
        self.assertIsNone(result["normalized_pct"])
        self.assertIn("decreased", result["reason"])

    def test_impossible_delta_does_not_report_more_than_100_percent(self):
        self.sampler.prime()
        self.browser.user += 5
        self.clock.advance()
        result = self.sampler.sample()
        self.assertFalse(result["valid"])
        self.assertIsNone(result["normalized_pct"])
        self.assertIn("capacity", result["reason"])

    def test_unprimed_or_zero_interval_and_missing_cpu_count_are_unknown(self):
        self.assertFalse(self.sampler.sample()["valid"])
        self.assertFalse(self.sampler.sample()["valid"])
        self.sampler.logical_cpu_count = None
        self.clock.advance()
        result = self.sampler.sample()
        self.assertFalse(result["valid"])
        self.assertIn("CPU count", result["reason"])


class CpuSummaryTests(unittest.TestCase):
    def test_mean_is_weighted_by_interval_duration_with_failures_preserved(self):
        result = runtime.summarize_cpu([observation(20, 1), {"valid": False, "reason": "No process access"}, observation(80, 3)])
        self.assertEqual(result["unit"], "%")
        self.assertEqual(result["mean_pct"], 65)
        self.assertEqual(result["p95_pct"], 77)
        self.assertEqual(result["sampled_peak_pct"], 80)
        self.assertEqual(result["wall_seconds"], 4)
        self.assertAlmostEqual(result["cpu_seconds"], 10.4)
        self.assertEqual(result["logical_cpu_count"], 4)
        self.assertEqual(result["successful_samples"], 2)
        self.assertEqual(result["attempted_samples"], 3)
        self.assertEqual(result["failed_samples"], 1)

    def test_genuine_zero_is_kept_but_unknown_is_not_zero(self):
        self.assertEqual(runtime.summarize_cpu([observation(0, 1)])["mean_pct"], 0)
        for items in ([], [{"valid": False, "reason": "CPU unavailable"}]):
            result = runtime.summarize_cpu(items)
            for key in ("mean_pct", "p95_pct", "sampled_peak_pct", "cpu_seconds", "wall_seconds", "logical_cpu_count"):
                self.assertIsNone(result[key])

    def test_invalid_or_inconsistent_valid_observations_raise(self):
        for changes in ({"normalized_pct": -1}, {"normalized_pct": 101}, {"normalized_pct": float("nan")},
                        {"interval_seconds": 0}, {"interval_seconds": True}, {"cpu_seconds": float("inf")},
                        {"cpu_seconds": -1}, {"logical_cpu_count": None}, {"logical_cpu_count": True},
                        {"normalized_pct": 10, "cpu_seconds": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                runtime.summarize_cpu([{**observation(20, 1), **changes}])


if __name__ == "__main__":
    unittest.main()
