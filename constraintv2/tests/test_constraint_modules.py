"""Independent constraint calculations with explicit unknown/failure handling."""
import copy
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from constraints import MODULES, constraint1, constraint2, constraint3, constraint4, constraint5
from constraints.shared import number


class UnusedMapping:
    def get(self, *arguments):
        raise AssertionError("Unrelated source data was accessed")


def cpu_observation(percent, seconds=1):
    return {"valid": True, "normalized_pct": percent, "interval_seconds": seconds,
            "cpu_seconds": percent / 100 * seconds * 4, "logical_cpu_count": 4}


class ConstraintModuleTests(unittest.TestCase):
    def test_registry_has_five_stable_independent_definitions(self):
        self.assertEqual([module.NUMBER for module in MODULES], [1, 2, 3, 4, 5])
        self.assertEqual(len({module.ID for module in MODULES}), 5)
        for module in MODULES:
            result = module.build({}, {}, [])
            self.assertEqual((result["id"], result["name"], result["unit"]),
                             (module.ID, module.NAME, module.UNIT))
            self.assertIsNone(result["value"])
        self.assertEqual(constraint5.UNIT, "%")
        self.assertNotIn("model_complexity", [module.ID for module in MODULES])

    def test_own_source_storage_and_mi_use_only_their_relevant_source(self):
        source = {"storage": {"status": "measured", "mb": .001234, "bytes": 1234},
                  "maintainability": {"status": "measured", "score_0_100": 62.5}}
        before = copy.deepcopy(source)
        storage = constraint1.build(UnusedMapping(), source, None)
        maintainability = constraint3.build(UnusedMapping(), source, None)
        self.assertEqual(storage["value"], .001234)
        self.assertEqual(maintainability["value"], 62.5)
        self.assertEqual(source, before)
        storage["evidence"]["bytes"] = 999
        self.assertEqual(source["storage"]["bytes"], 1234)
        source["storage"]["mb"] = 123
        self.assertEqual(constraint3.build({}, source, [])["value"], 62.5)

    def test_invalid_own_source_values_remain_unknown(self):
        for value in (None, True, "2", -1, float("nan"), float("inf")):
            with self.subTest(storage=value):
                result = constraint1.build({}, {"storage": {"status": "measured", "mb": value}}, [])
                self.assertIsNone(result["value"])
                self.assertEqual(result["status"], "unavailable")
        for value in (None, True, "2", -1, 100.01, float("nan"), float("inf")):
            with self.subTest(mi=value):
                result = constraint3.build({}, {"maintainability": {"status": "measured", "score_0_100": value}}, [])
                self.assertIsNone(result["value"])
                self.assertEqual(result["status"], "unavailable")
        self.assertEqual(number(0), 0)
        self.assertEqual(number(100, maximum=100), 100)

    def test_latency_and_memory_pool_observations_without_using_other_metrics(self):
        trials = [
            {"status": "measured", "repeat": 1,
             "latency": {"observations": [{"status": "measured", "elapsed_ms": 10},
                                              {"status": "failed", "error": "Timeout"}]},
             "memory": {"observations": [{"valid": True, "rss_bytes": 100_000_000, "components": {}}]}},
            {"status": "measured", "repeat": 2,
             "latency": {"observations": [{"status": "measured", "elapsed_ms": 30}]},
             "memory": {"observations": [{"valid": True, "rss_bytes": 300_000_000, "components": {}}]}},
        ]
        before = copy.deepcopy(trials)
        latency = constraint2.build(UnusedMapping(), UnusedMapping(), trials)
        memory = constraint4.build(UnusedMapping(), UnusedMapping(), trials)
        self.assertEqual(latency["value"], 20)
        self.assertEqual(latency["status"], "partial")
        self.assertEqual(latency["evidence"]["failed_samples"], 1)
        self.assertEqual(memory["value"], 200)
        self.assertEqual(memory["status"], "measured")
        self.assertEqual(memory["evidence"]["sampled_peak_mb"], 300)
        self.assertEqual(trials, before)

    def test_cpu_old_model_counts_and_missing_values_are_not_zero_usage(self):
        report = {"model_complexity": {"status": "measured", "models": [{"triangle_count": 12345}]}}
        for trials in ([], [{"status": "measured", "repeat": 1}],
                       [{"status": "failed", "repeat": 1, "cpu": {"mean_pct": 0}}]):
            with self.subTest(trials=trials):
                result = constraint5.build(report, {}, trials)
                self.assertIsNone(result["value"])
                self.assertIn(result["status"], {"not_measured", "unmeasured"})

    def test_cpu_pooling_weights_interval_duration_and_preserves_failed_samples(self):
        trials = [
            {"status": "measured", "repeat": 1,
             "cpu": {"observations": [cpu_observation(20, 1)], "mean_pct": 99}},
            {"status": "measured", "repeat": 2,
             "cpu": {"observations": [cpu_observation(80, 3), {"valid": False, "error": "Process vanished"}]}},
        ]
        before = copy.deepcopy(trials)
        result = constraint5.build(UnusedMapping(), UnusedMapping(), trials)
        self.assertAlmostEqual(result["value"], 65)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["evidence"]["sampled_peak_pct"], 80)
        self.assertEqual(result["evidence"]["successful_samples"], 2)
        self.assertEqual(result["evidence"]["attempted_samples"], 3)
        self.assertEqual(result["evidence"]["failed_samples"], 1)
        self.assertIn("weighted", result["evidence"]["aggregation"])
        self.assertIn("logical CPU", result["scope"])
        self.assertEqual(trials, before)

    def test_cpu_single_legacy_summary_is_bounded_and_multiple_summaries_are_unknown(self):
        trial = {"repeat": 1, "status": "measured",
                 "cpu": {"mean_pct": 25, "p95_pct": 40, "sampled_peak_pct": 50}}
        result = constraint5.build({}, {}, [trial])
        self.assertEqual(result["value"], 25)
        self.assertIn("single-trial summary only", result["evidence"]["aggregation"])
        result = constraint5.build({}, {}, [trial, {**trial, "repeat": 2}])
        self.assertIsNone(result["value"])
        self.assertIn("multiple trial summaries", result["evidence"]["reason"])
        for value in (-1, 101, True, float("inf")):
            with self.subTest(value=value):
                result = constraint5.build({}, {}, [{"repeat": 1, "status": "measured", "cpu": {"mean_pct": value}}])
                self.assertIsNone(result["value"])
        self.assertEqual(constraint5.build({}, {}, [{"status": "measured", "cpu": {"mean_pct": 0}}])["value"], 0)

    def test_failed_and_missing_cpu_trials_keep_pooled_data_partial(self):
        trials = [{"repeat": 1, "status": "measured", "cpu": {"observations": [cpu_observation(10)]}},
                  {"repeat": 2, "status": "missing", "reason": "No run"}]
        result = constraint5.build({}, {}, trials)
        self.assertEqual(result["value"], 10)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["evidence"]["failed_or_missing_trials"], 1)


if __name__ == "__main__":
    unittest.main()
