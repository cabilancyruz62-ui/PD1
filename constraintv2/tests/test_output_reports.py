"""Result layout and aggregation tests; all fixtures are existing observations."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from output_reports import DESIGNS, METRICS, refresh_results, write_results


def latency(values):
    return {"observations": [{"status": "measured", "elapsed_ms": value} for value in values]}


def memory(values):
    return {"observations": [{"valid": True, "rss_bytes": value * 1_000_000,
                              "components": {"browser": {"rss_bytes": value * 1_000_000}}}
                             for value in values]}


def cpu(values=(20, 40), intervals=None):
    intervals = intervals or [1] * len(values)
    logical_cpus = 8
    return {"observations": [
        {"valid": True, "normalized_pct": value, "interval_seconds": interval,
         "cpu_seconds": value / 100 * interval * logical_cpus,
         "logical_cpu_count": logical_cpus,
         "components": {"browser": {"cpu_seconds": value / 100 * interval * logical_cpus},
                        "backend": {"cpu_seconds": 0}}}
        for value, interval in zip(values, intervals)
    ]}


def mode(name, elapsed=(10, 20), ram=(100, 200), utilization=(20, 40)):
    return {"mode": name, "status": "measured", "latency": latency(elapsed),
            "memory": memory(ram), "cpu": cpu(utilization), "assessment": {"patient_id": "charlie"},
            "tracking_diagnostics": {"tracked_results": 2}}


def report():
    return {
        "generated_at_utc": "2026-10-23T18:06:31+00:00",
        "completed_at_utc": "2026-10-23T18:08:10+00:00",
        "derived_from_report": "old-results/summary.json",
        "report_generated_at_utc": "2026-10-24T00:00:00+00:00",
        "static": {},
        "design_metrics": {"designs": [
            {"id": identifier, "storage": {"status": "measured", "mb": (index + 1) / 1000},
             "maintainability": {"status": "measured", "score_0_100": 40 + index}}
            for index, (_, identifier, _, _) in enumerate(DESIGNS)
        ]},
        "model_complexity": {"status": "measured", "models": [
            {"breed_id": breed, "breed_label": label,
             "poses": {"standing": {"triangle_count": count}, "lying": {"triangle_count": count}}}
            for breed, label, count in (("labrador", "Labrador", 36856), ("beagle", "Beagle", 38760),
                                        ("dalmatian", "Dalmatian", 39320))
        ]},
        "runtime": {"status": "measured", "runs": [{"status": "measured", "modes": [
            mode("normal", (999,), (999,)), *[mode(entry[1]) for entry in DESIGNS]
        ]}]},
    }


class OutputReportsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "resultsv2"

    def load(self, relative):
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def canonical_files(self):
        return [self.root / directory / f"constraint{number}.json"
                for directory, _, _, _ in DESIGNS for number in range(1, 6)]

    def snapshots(self, paths):
        return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

    def test_layout_contains_three_designs_and_exactly_five_metrics(self):
        fixture = report()
        before = copy.deepcopy(fixture)
        paths = write_results(fixture, self.root)
        self.assertEqual(set(paths), {"comparison", "measurements", "designs"})
        self.assertEqual(paths["comparison"], self.root.resolve() / "comparison.md")
        self.assertEqual(set(paths["designs"]), {"design1", "design2", "design3"})
        self.assertEqual(set(path.name for path in self.root.iterdir()),
                         {"comparison.md", "comparison.json", "comparison.csv", "measurements.json", "design1", "design2", "design3"})
        comparison = self.load("comparison.json")
        self.assertEqual(len(comparison["rows"]), 5)
        self.assertEqual([row["constraint"] for row in comparison["rows"]], [item[1] for item in METRICS])
        for directory, _, _, _ in DESIGNS:
            item = self.load(directory + "/constraints.json")
            self.assertEqual(item["metric_count"], 5)
            self.assertEqual(len(item["metrics"]), 5)
            self.assertEqual([metric["id"] for metric in item["metrics"]], [metric[0] for metric in METRICS])
            expected = {"constraints.md", "constraints.json"}
            expected.update(f"constraint{number}.{extension}"
                            for number in range(1, 6) for extension in ("md", "json"))
            self.assertEqual(set(path.name for path in (self.root / directory).iterdir()), expected)
            for number, (identifier, _, _) in enumerate(METRICS, 1):
                canonical = self.load(f"{directory}/constraint{number}.json")
                self.assertEqual(canonical["design"], directory)
                self.assertEqual(canonical["constraint_number"], number)
                self.assertEqual(canonical["metric"]["id"], identifier)
                derived = item["metrics"][number - 1]
                self.assertFalse(derived["edited_since_generation"])
                self.assertEqual(canonical["metric"],
                                 {key: value for key, value in derived.items() if key != "edited_since_generation"})
                self.assertIn("generated_metric_sha256", canonical)
            self.assertNotIn("normal", [trial["mode"] for trial in item["trials"]])
        self.assertNotIn("normal", [column["mode"] for column in comparison["columns"]])
        with (self.root / "comparison.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[0], ["Constraint", "Design 1", "Design 2", "Design 3"])
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(len(row) == 4 for row in rows))
        self.assertEqual(self.load("measurements.json"), before)
        self.assertEqual(fixture, before)

    def test_values_keep_own_source_scope_and_use_cpu_for_constraint_five(self):
        fixture = report()
        for index, trial in enumerate(fixture["runtime"]["runs"][0]["modes"][1:], 1):
            trial["cpu"] = cpu((index * 10,))
        write_results(fixture, self.root)
        rows = self.load("comparison.json")["rows"]
        self.assertEqual([rows[0][key] for key, _, _, _ in DESIGNS], [.001, .002, .003])
        self.assertEqual([rows[2][key] for key, _, _, _ in DESIGNS], [40, 41, 42])
        self.assertEqual([rows[4][key] for key, _, _, _ in DESIGNS], [10, 20, 30])
        self.assertEqual(rows[4]["id"], "computational_efficiency")
        self.assertEqual(rows[4]["unit"], "%")
        text = (self.root / "comparison.md").read_text(encoding="utf-8")
        self.assertIn("CPU Utilization", text)
        self.assertNotIn("Model Complexity", text)
        self.assertIn("30.00 %", text)
        fifth = self.load("design1/constraint5.json")["metric"]
        self.assertIn("logical", fifth["scope"].lower())
        self.assertIn("browser", fifth["scope"].lower())
        self.assertIn("backend", fifth["scope"].lower())
        self.assertIn("own tracker.py", self.load("design1/constraint1.json")["metric"]["scope"])
        self.assertIn("tracker.py", text)
        self.assertIn("not the complete application", text)
        self.assertIn("physical ESP32 latency", text)
        detail = (self.root / "design1/constraint1.md").read_text(encoding="utf-8")
        self.assertIn("old-results/summary.json", detail)
        self.assertIn("2026-10-23T18:06:31+00:00", detail)
        self.assertIn("comparison refresh does not collect new measurements", text)

    def test_pooling_uses_observations_not_mean_of_percentiles_or_repeat_means(self):
        fixture = report()
        first = mode("aruco", (0, 100), (100, 200))
        first["latency"]["p95_ms"] = 1  # Deliberately stale summary must not win.
        second = mode("aruco", (1000,), (900,))
        second["latency"]["p95_ms"] = 1
        fixture["runtime"]["runs"] = [{"status": "measured", "modes": [first]},
                                      {"status": "measured", "modes": [second]}]
        write_results(fixture, self.root)
        design = self.load("design1/constraints.json")
        self.assertAlmostEqual(design["metrics"][1]["value"], 1100 / 3)
        self.assertAlmostEqual(design["metrics"][1]["evidence"]["p95_ms"], 910)
        self.assertEqual(design["metrics"][1]["evidence"]["successful_samples"], 3)
        self.assertEqual(design["metrics"][3]["value"], 400)
        self.assertEqual(design["metrics"][3]["evidence"]["sampled_peak_mb"], 900)
        self.assertEqual(len(design["trials"]), 2)
        latency_text = (self.root / "design1/constraint2.md").read_text(encoding="utf-8")
        memory_text = (self.root / "design1/constraint4.md").read_text(encoding="utf-8")
        self.assertRegex(latency_text, r"P50:? 100\.00 ms")
        self.assertRegex(latency_text, r"P95:? 910\.00 ms")
        self.assertIn("3/3 successful", latency_text)
        self.assertIn("0 failed", latency_text)
        self.assertIn("900.00 MB", memory_text)
        self.assertIn("3/3 successful", memory_text)
        self.assertIn("0 failed", memory_text)

    def test_failed_missing_and_unavailable_values_remain_null(self):
        fixture = report()
        fixture["runtime"]["runs"][0]["modes"] = [
            {"mode": "aruco", "status": "failed", "error": "Browser failed",
             "latency": {"mean_ms": 0}, "memory": {"mean_mb": 0}},
            {"mode": "orb", "status": "partial", "latency": {"observations": [{"status": "failed", "error": "Timeout"}]},
             "memory": {"observations": [{"valid": False, "rss_bytes": None, "components": {}}]}},
        ]
        fixture["design_metrics"]["designs"][2]["storage"] = {"status": "unavailable", "mb": None}
        fixture["design_metrics"]["designs"][2]["maintainability"] = {"status": "unavailable", "score_0_100": None}
        fixture["model_complexity"] = {"status": "unavailable", "reason": "Node absent"}
        write_results(fixture, self.root)
        comparison = self.load("comparison.json")
        for index in (1, 3, 4):
            for directory, _, _, _ in DESIGNS:
                self.assertIsNone(comparison["rows"][index][directory])
        third = self.load("design3/constraints.json")
        self.assertEqual(third["trials"][0]["status"], "missing")
        self.assertIsNone(third["metrics"][0]["value"])
        self.assertIsNone(third["metrics"][2]["value"])
        first = self.load("design1/constraints.json")
        self.assertEqual(first["trials"][0]["error"], "Browser failed")
        second = self.load("design2/constraints.json")
        self.assertEqual(second["metrics"][1]["evidence"]["failed_samples"], 1)
        self.assertIn("Not measured", (self.root / "comparison.md").read_text(encoding="utf-8"))

    def test_single_legacy_summary_is_labeled_but_multiple_summaries_are_not_pooled(self):
        fixture = report()
        summary = {"mode": "aruco", "status": "measured", "latency": {"mean_ms": 12, "p95_ms": 18},
                   "memory": {"mean_mb": 100, "sampled_peak_mb": 120}}
        fixture["runtime"]["runs"] = [{"status": "measured", "modes": [summary]}]
        write_results(fixture, self.root)
        first = self.load("design1/constraints.json")
        self.assertEqual(first["metrics"][1]["value"], 12)
        self.assertIn("single-trial summary only", first["metrics"][1]["evidence"]["aggregation"])
        fixture["runtime"]["runs"].append({"status": "measured", "modes": [summary]})
        write_results(fixture, self.root)
        first = self.load("design1/constraints.json")
        self.assertIsNone(first["metrics"][1]["value"])
        self.assertIsNone(first["metrics"][3]["value"])
        self.assertIn("multiple trial summaries", first["metrics"][1]["evidence"]["reason"])

    def test_missing_modes_and_legacy_geometry_do_not_invent_cpu_values(self):
        fixture = report()
        fixture["runtime"]["runs"][0]["modes"] = [mode("aruco")]
        del fixture["runtime"]["runs"][0]["modes"][0]["cpu"]
        fixture["design_metrics"]["designs"] = fixture["design_metrics"]["designs"][:1]
        fixture["model_complexity"]["models"][0]["poses"]["lying"]["triangle_count"] = 123
        write_results(fixture, self.root)
        third = self.load("design3/constraints.json")
        self.assertEqual(len(third["metrics"]), 5)
        for index in (0, 1, 2, 3):
            self.assertIsNone(third["metrics"][index]["value"])
        self.assertIsNone(third["metrics"][4]["value"])
        self.assertIsNone(self.load("design1/constraint5.json")["metric"]["value"])
        self.assertNotIn("triangles", (self.root / "comparison.md").read_text(encoding="utf-8"))

    def test_missing_static_design_rows_fall_back_without_reading_sources(self):
        fixture = report()
        del fixture["design_metrics"]
        fixture["static"] = {
            "storage": {"files": [{"path": "designs/design-1-aruco/tracker.py", "bytes": 1234}]},
            "maintainability": {"files": [{"path": "designs/design-1-aruco/tracker.py", "score_0_100": 55}]},
        }
        write_results(fixture, self.root)
        first = self.load("design1/constraints.json")
        self.assertEqual(first["metrics"][0]["value"], .001234)
        self.assertEqual(first["metrics"][2]["value"], 55)
        self.assertIsNone(self.load("design2/constraints.json")["metrics"][0]["value"])

    def test_cpu_pools_interval_weighted_observations_across_repeats(self):
        fixture = report()
        first = mode("aruco")
        first["cpu"] = cpu((10,), (1,))
        first["cpu"]["mean_normalized_pct"] = 99  # A stale summary must not win.
        second = mode("aruco")
        second["cpu"] = cpu((50,), (3,))
        fixture["runtime"]["runs"] = [
            {"status": "measured", "modes": [first]},
            {"status": "measured", "modes": [second]},
        ]
        write_results(fixture, self.root)
        metric = self.load("design1/constraint5.json")["metric"]
        self.assertAlmostEqual(metric["value"], 40)
        self.assertEqual(metric["status"], "measured")
        self.assertEqual(metric["evidence"]["successful_samples"], 2)
        self.assertEqual(len(metric["evidence"]["observations"]), 2)
        self.assertIn("40.00 %", (self.root / "comparison.md").read_text(encoding="utf-8"))

    def test_failed_cpu_samples_are_retained_without_becoming_zero(self):
        fixture = report()
        fixture["runtime"]["runs"][0]["modes"] = [{
            **mode("aruco"),
            "cpu": {"observations": [{"valid": False, "normalized_pct": None,
                                       "error": "Process disappeared", "interval_seconds": 1}]},
        }]
        write_results(fixture, self.root)
        metric = self.load("design1/constraint5.json")["metric"]
        self.assertIsNone(metric["value"])
        self.assertEqual(metric["evidence"]["failed_samples"], 1)
        self.assertEqual(metric["evidence"]["observations"][0]["error"], "Process disappeared")

    def test_selective_generation_only_changes_the_selected_constraint(self):
        original = report()
        write_results(original, self.root)
        protected = [self.root / "measurements.json"]
        protected.extend(self.root / directory / f"constraint{number}.{extension}"
                         for directory, _, _, _ in DESIGNS
                         for number in range(1, 5) for extension in ("json", "md"))
        before = self.snapshots(protected)
        changed = copy.deepcopy(original)
        changed["design_metrics"]["designs"][0]["storage"]["mb"] = 999
        changed["generated_at_utc"] = "2026-11-01T01:00:00+00:00"
        for trial in changed["runtime"]["runs"][0]["modes"]:
            trial["cpu"] = cpu((70,))
        write_results(changed, self.root, constraints=(5,))
        self.assertEqual(self.snapshots(protected), before)
        for directory, _, _, _ in DESIGNS:
            fifth = self.load(f"{directory}/constraint5.json")
            self.assertEqual(fifth["metric"]["value"], 70)
            self.assertEqual(fifth["provenance"]["generated_at_utc"], changed["generated_at_utc"])
        self.assertEqual(self.load("design1/constraints.json")["metrics"][0]["value"], .001)
        self.assertEqual(self.load("comparison.json")["rows"][0]["design1"], .001)
        self.assertEqual(self.load("comparison.json")["rows"][4]["design1"], 70)
        rows = self.load("comparison.json")["rows"]
        self.assertEqual(rows[0]["provenance"]["design1"]["generated_at_utc"],
                         "2026-10-23T18:06:31+00:00")
        self.assertEqual(rows[4]["provenance"]["design1"]["generated_at_utc"],
                         changed["generated_at_utc"])

    def test_refresh_uses_one_edited_constraint_and_preserves_all_canonical_files(self):
        write_results(report(), self.root)
        path = self.root / "design2/constraint1.json"
        edited = json.loads(path.read_text(encoding="utf-8"))
        edited["metric"]["value"] = .123456
        path.write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
        protected = [*self.canonical_files(), self.root / "measurements.json"]
        before = self.snapshots(protected)
        refresh_results(self.root)
        self.assertEqual(self.snapshots(protected), before)
        metric = self.load("design2/constraints.json")["metrics"][0]
        self.assertEqual(metric["value"], .123456)
        self.assertTrue(metric["edited_since_generation"])
        self.assertEqual(self.load("comparison.json")["rows"][0]["design2"], .123456)
        table = (self.root / "comparison.md").read_text(encoding="utf-8")
        self.assertRegex(table, r"0\.123456 MB\s*\*")
        self.assertIn("edited", table.lower())
        detail = (self.root / "design2/constraint1.md").read_text(encoding="utf-8")
        self.assertIn("2026-10-23T18:06:31+00:00", detail)
        self.assertIn("0.123456 MB", detail)

    def test_invalid_canonical_files_are_rejected_before_any_derived_output_changes(self):
        for invalid in ("malformed", "wrong_design", "wrong_metric"):
            with self.subTest(invalid=invalid):
                write_results(report(), self.root)
                path = self.root / "design3/constraint2.json"
                if invalid == "malformed":
                    path.write_text("{broken", encoding="utf-8")
                else:
                    document = json.loads(path.read_text(encoding="utf-8"))
                    if invalid == "wrong_design":
                        document["design"] = "design1"
                    else:
                        document["metric"]["id"] = "memory_efficiency"
                    path.write_text(json.dumps(document), encoding="utf-8")
                before = self.snapshots(self.root.rglob("*.*"))
                with self.assertRaises(ValueError):
                    refresh_results(self.root)
                self.assertEqual(self.snapshots(before), before)

    def test_refresh_reports_missing_constraint_as_unknown_without_creating_json(self):
        write_results(report(), self.root)
        missing = self.root / "design1/constraint3.json"
        missing.unlink()
        before = self.snapshots([path for path in self.canonical_files() if path.exists()])
        refresh_results(self.root)
        self.assertFalse(missing.exists())
        self.assertEqual(self.snapshots(before), before)
        metric = self.load("design1/constraints.json")["metrics"][2]
        self.assertIsNone(metric["value"])
        self.assertIn(metric["status"], {"unknown", "not_measured", "unavailable", "missing"})
        self.assertIsNone(self.load("comparison.json")["rows"][2]["design1"])
        self.assertIn("Not measured", (self.root / "comparison.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
