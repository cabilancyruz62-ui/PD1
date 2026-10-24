"""Independent constraint records with derived design and comparison reports."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
from pathlib import Path

from constraints import MODULES
from design_metrics import collect_design_metrics

DESIGNS = (
    ("design1", "aruco", "Design 1", "ArUco"),
    ("design2", "orb", "Design 2", "ORB + RANSAC"),
    ("design3", "optical-flow", "Design 3", "Optical flow"),
)
METRICS = tuple((module.ID, module.NAME, module.UNIT) for module in MODULES)
BY_NUMBER = {module.NUMBER: module for module in MODULES}
TRIAL_KIND = {2: "latency", 4: "memory", 5: "cpu"}


def _encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def _digest(metric):
    return hashlib.sha256(json.dumps(metric, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


def _write(path, content):
    """Avoid rewriting unchanged files, including unrelated constraint reports."""
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _provenance(report):
    keys = ("generated_at_utc", "completed_at_utc", "derived_from_report",
            "report_generated_at_utc", "source_fingerprint", "production_build")
    return {key: copy.deepcopy(report[key]) for key in keys if key in report}


def _trials(report, mode):
    trials = []
    for index, run in enumerate(report.get("runtime", {}).get("runs", []), 1):
        rows = [row for row in run.get("modes", []) if row.get("mode") == mode]
        if not rows:
            rows = [{"mode": mode, "status": "missing", "reason": "No observations for this design in this repeat."}]
        for row in rows:
            trial = {**copy.deepcopy(row), "repeat": index}
            if run.get("error"):
                trial["run_error"] = run["error"]
            trials.append(trial)
    return trials


def _record(report, entry, source, number):
    directory, mode, label, algorithm = entry
    trials = _trials(report, mode)
    metric = BY_NUMBER[number].build(report, source, trials)
    kind = TRIAL_KIND.get(number)
    trial_keys = {"mode", "status", "repeat", "reason", "error", "run_error", "assessment", "tracking_diagnostics", "tracking_warning"}
    if kind:
        trial_keys.add(kind)
    return {
        "schema_version": 3, "design": directory, "mode": mode, "label": label,
        "algorithm": algorithm, "constraint_number": number,
        "metric": metric, "generated_metric_sha256": _digest(metric),
        "provenance": _provenance(report),
        "trials": [{key: value for key, value in trial.items() if key in trial_keys} for trial in trials] if kind else [],
        "acceptance_limits": "not_set",
    }


def _unknown(entry, number, path):
    directory, mode, label, algorithm = entry
    module = BY_NUMBER[number]
    return {"schema_version": 3, "design": directory, "mode": mode, "label": label,
            "algorithm": algorithm, "constraint_number": number, "provenance": {}, "trials": [],
            "metric": {"id": module.ID, "name": module.NAME, "unit": module.UNIT,
                       "value": None, "status": "not_measured", "statistic": "No saved measurement.",
                       "scope": "No saved result file exists for this constraint.",
                       "evidence": {"reason": f"Missing result file: {path}"}}}


def _load(path, entry, number):
    if not path.is_file():
        return _unknown(entry, number, path)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        metric = record["metric"]
        module = BY_NUMBER[number]
        if record["design"] != entry[0] or record["mode"] != entry[1] or record["constraint_number"] != number:
            raise ValueError("design, mode or constraint number does not match its file")
        if metric["id"] != module.ID or metric["unit"] != module.UNIT:
            raise ValueError("metric id or unit does not match its constraint module")
        for key in ("name", "status", "statistic", "scope"):
            if not isinstance(metric[key], str) or not metric[key]:
                raise ValueError(f"metric {key} must be a nonempty string")
        value = metric["value"]
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("metric value must be null or a finite nonnegative number")
            if number in {3, 5} and value > 100:
                raise ValueError("MI and normalized CPU values must be between 0 and 100")
        if metric["status"] == "measured" and value is None:
            raise ValueError("a measured result must have a value")
        if not isinstance(metric.get("evidence"), dict) or not isinstance(record.get("provenance", {}), dict):
            raise ValueError("evidence and provenance must be objects")
        record["edited_since_generation"] = record.get("generated_metric_sha256") != _digest(metric)
        return record
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"Invalid constraint result {path}: {error}") from error


def _cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _format(metric, edited=False):
    value = metric["value"]
    if value is None:
        text = "Not measured"
    else:
        decimals = 6 if metric["id"] == "storage_efficiency" else 2
        suffix = " / 100" if metric["unit"] == "0-100" else " " + metric["unit"]
        text = f"{value:,.{decimals}f}" + suffix
    return text + (" *" if edited else "")


def _secondary(metric):
    evidence = metric["evidence"]
    fields = {"performance": (("p50_ms", "P50", "ms"), ("p95_ms", "P95", "ms")),
              "memory_efficiency": (("sampled_peak_mb", "Sampled peak RAM", "MB"),),
              "computational_efficiency": (("p95_pct", "P95 CPU", "%"), ("sampled_peak_pct", "Sampled peak CPU", "%"))}
    lines = []
    for key, label, unit in fields.get(metric["id"], ()):
        value = evidence.get(key)
        text = "Not measured" if value is None else f"{value:,.2f} {unit}"
        lines.append(f"{label}: {text}.")
    if "attempted_samples" in evidence:
        lines.append(f"Samples: {evidence.get('successful_samples', 0)}/{evidence['attempted_samples']} successful; {evidence.get('failed_samples', 0)} failed.")
    if evidence.get("reason"):
        lines.append(str(evidence["reason"]))
    return lines


def _dates(provenance):
    labels = (("generated_at_utc", "Measurement started"), ("completed_at_utc", "Measurement completed"),
              ("report_generated_at_utc", "Report generated"), ("derived_from_report", "Derived from existing report"))
    return [f"{label}: {provenance[key]}" for key, label in labels if provenance.get(key)]


def _notes(edited):
    lines = [
        "MB = 1,000,000 bytes. Storage and Maintainability Index cover each design's own tracker.py, not the complete application.",
        "Latency and RAM show successful-sample means. CPU shows time-weighted mean utilization normalized across logical CPUs for the owned browser and backend processes.",
        "Legacy observations used headless Edge with SwiftShader software rendering and synthetic camera/simulated inputs. These do not measure physical ESP32 latency or validate unchanged-pad tracking accuracy.",
        "CPU was not recorded in the earlier measurements: missing CPU data stays Not measured. Dog triangle counts remain supplementary metadata.",
        "No acceptance limits have been set. Each numbered constraint JSON keeps its own evidence and measurement dates; comparison refresh does not collect new measurements.",
    ]
    if edited:
        lines.append("* Result record edited since generation; this is a saved-record correction, not a new measurement. Inspect its evidence and provenance.")
    return lines


def refresh_results(output_root):
    """Read independent records and refresh derived views without remeasurement."""
    root = Path(output_root).resolve()
    # Validate every existing record before changing any derived artifact.
    records = {entry[0]: [_load(root / entry[0] / f"constraint{number}.json", entry, number)
                          for number in BY_NUMBER] for entry in DESIGNS}
    edited = any(record.get("edited_since_generation", False) for rows in records.values() for record in rows)
    notes = _notes(edited)
    periods = sorted({(record.get("provenance", {}).get("generated_at_utc", ""), record.get("provenance", {}).get("completed_at_utc", ""))
                      for rows in records.values() for record in rows})
    for started, completed in periods:
        if started or completed:
            notes.append(f"Measurement window: {started or 'not recorded'} to {completed or 'not recorded'}. See each constraint file for its own provenance.")
    comparison = {"schema_version": 3, "title": "PupVitals: five-constraint design comparison",
                  "columns": [{"id": directory, "mode": mode, "label": label, "algorithm": algorithm}
                              for directory, mode, label, algorithm in DESIGNS],
                  "rows": [], "notes": notes, "acceptance_limits": "not_set"}
    header = ["Constraint", *[entry[2] for entry in DESIGNS]]
    csv_rows = [header]
    text = ["# Five-constraint design comparison", "", "| " + " | ".join(header) + " |", "| --- | ---: | ---: | ---: |"]
    for index, module in enumerate(MODULES):
        row = {"id": module.ID, "constraint": module.NAME, "unit": module.UNIT,
               "statuses": {}, "edited_since_generation": {}, "provenance": {}}
        cells = []
        for directory, _, _, _ in DESIGNS:
            record = records[directory][index]
            metric = record["metric"]
            row[directory] = metric["value"]
            row["statuses"][directory] = metric["status"]
            row["edited_since_generation"][directory] = record.get("edited_since_generation", False)
            row["provenance"][directory] = record.get("provenance", {})
            cells.append(_format(metric, record.get("edited_since_generation", False)))
        comparison["rows"].append(row)
        text.append("| " + " | ".join(_cell(item) for item in [module.NAME, *cells]) + " |")
        csv_rows.append([module.NAME, *cells])
    text.extend(["", *["- " + note for note in notes], "",
                 "Detailed results: [Design 1](design1/constraints.md), [Design 2](design2/constraints.md), [Design 3](design3/constraints.md).", ""])
    _write(root / "comparison.md", "\n".join(text))
    _write(root / "comparison.json", _encoded(comparison))
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(csv_rows)
    _write(root / "comparison.csv", "\ufeff" + buffer.getvalue())
    paths = {}
    for directory, mode, label, algorithm in DESIGNS:
        rows = records[directory]
        metrics = [{**copy.deepcopy(record["metric"]), "edited_since_generation": record.get("edited_since_generation", False)} for record in rows]
        provenance = next((record.get("provenance") for record in rows if record.get("provenance")), {})
        aggregate = {"schema_version": 3, "design": directory, "mode": mode, "label": label,
                     "algorithm": algorithm, "metric_count": 5, "metrics": metrics,
                     "provenance": provenance,
                     "constraint_provenance": {f"constraint{record['constraint_number']}": record.get("provenance", {}) for record in rows},
                     "trials": next((record["trials"] for record in rows if record.get("trials")), []),
                     "acceptance_limits": "not_set"}
        _write(root / directory / "constraints.json", _encoded(aggregate))
        index_lines = [f"# {label}: {algorithm}", "", "| Constraint | Value |", "| --- | ---: |"]
        for record in rows:
            number, metric = record["constraint_number"], record["metric"]
            was_edited = record.get("edited_since_generation", False)
            index_lines.append(f"| [{_cell(metric['name'])}](constraint{number}.md) | {_format(metric, was_edited)} |")
            detail = [f"# {label}: {metric['name']}", "", f"Value: **{_format(metric, was_edited)}**", "",
                      f"Status: {metric['status']}.", "", metric["statistic"], "", metric["scope"], "",
                      *["- " + line for line in _secondary(metric)], "",
                      *["- " + line for line in _dates(record.get("provenance", {}))], ""]
            if was_edited:
                detail.extend(["* This record was edited since generation; no new measurement is implied.", ""])
            detail.extend([f"[Saved JSON record](constraint{number}.json) · [Design overview](constraints.md) · [Overall comparison](../comparison.md)", ""])
            _write(root / directory / f"constraint{number}.md", "\n".join(detail))
        index_lines.extend(["", "Each constraint has its own JSON record and readable Markdown report. Edit the corresponding calculation in constraintv2/constraints/constraintN.py and selectively regenerate it, or refresh the comparison after a saved-record correction.", "",
                            *["- " + note for note in notes], "", "[Overall comparison](../comparison.md)", ""])
        path = root / directory / "constraints.md"
        _write(path, "\n".join(index_lines))
        paths[directory] = path
    return {"comparison": root / "comparison.md", "measurements": root / "measurements.json", "designs": paths}


def write_results(report, output_root, *, constraints=None):
    """Replace selected records, preserving every unrelated constraint file."""
    selected = tuple(BY_NUMBER) if constraints is None else tuple(constraints)
    if not selected or len(set(selected)) != len(selected) or any(number not in BY_NUMBER for number in selected):
        raise ValueError("Choose distinct constraint numbers from 1 to 5")
    root = Path(output_root).resolve()
    source = report.get("design_metrics") or collect_design_metrics(report.get("static", {}))
    lookup = {row["id"]: row for row in source.get("designs", [])}
    pending = []
    for entry in DESIGNS:
        for number in selected:
            record = _record(report, entry, lookup.get(entry[1], {}), number)
            pending.append((root / entry[0] / f"constraint{number}.json", _encoded(record)))
    for path, content in pending:
        _write(path, content)
    # Selective updates retain the complete original experiment; new evidence
    # lives in the selected numbered JSON records with its own timestamps.
    if set(selected) == set(BY_NUMBER) or not (root / "measurements.json").is_file():
        _write(root / "measurements.json", _encoded(report))
    return refresh_results(root)
