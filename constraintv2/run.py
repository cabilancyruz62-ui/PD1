"""Measure v2 constraints separately from the original tracker benchmarks."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from static_metrics import collect_static_metrics
from design_metrics import collect_design_metrics
from output_reports import refresh_results, write_results


ROOT = Path(__file__).resolve().parents[1]
MODES = ("aruco", "orb", "optical-flow")


def command_output(arguments, root):
    try:
        result = subprocess.run(arguments, cwd=root, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
        if result.returncode:
            return {"status": "unavailable", "reason": result.stderr.strip() or f"Exit {result.returncode}"}
        return {"status": "measured", "output": result.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "unavailable", "reason": str(error)}


def fingerprint(root, files):
    """Hash measured app inputs; never open excluded runtime/configuration files."""
    digest = hashlib.sha256()
    rows, errors = [], []
    for item in sorted(files, key=lambda row: row["path"]):
        if not item["application_payload"]:
            continue
        try:
            value = hashlib.sha256((root / item["path"]).read_bytes()).hexdigest()
            digest.update((item["path"] + "\0" + value + "\n").encode("utf-8"))
            rows.append({"path": item["path"], "sha256": value})
        except OSError as error:
            errors.append({"path": item["path"], "reason": str(error)})
    return {"algorithm": "SHA-256 of sorted path + NUL + file SHA-256 + newline",
            "application_sha256": digest.hexdigest() if not errors else None,
            "files": rows, "errors": errors}


def model_complexity(root):
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return {"status": "unavailable", "reason": "Node.js is not installed or is absent from PATH."}
    result = command_output([node, str(root / "constraintv2/model_complexity.mjs")], root)
    if result["status"] != "measured":
        return result
    try:
        return {"status": "measured", **json.loads(result["output"])}
    except (ValueError, TypeError) as error:
        return {"status": "unavailable", "reason": "Invalid model measurement JSON: " + str(error)}


def production_build(root):
    directory = root / "frontend/dist"
    files = [{"path": path.relative_to(root).as_posix(), "application_payload": True}
             for path in sorted(directory.rglob("*")) if path.is_file() and not path.is_symlink()]
    return {
        "status": "recorded" if files else "unavailable",
        "scope": "Existing production frontend/dist files, separate from raw-source storage",
        "source_build_linkage": "Unverified: build files are fingerprinted, but a compiler-attested source-to-build mapping is not available. Rebuild immediately before runtime measurements.",
        "fingerprint": fingerprint(root, files),
    }


def environment(root):
    packages = {}
    for name in ("radon", "psutil", "opencv-contrib-python", "numpy", "fastapi", "websockets"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "platform": platform.platform(), "machine": platform.machine(),
        "python": sys.version, "python_executable": sys.executable,
        "node": command_output(["node", "--version"], root), "packages": packages,
        "git_head": command_output(["git", "rev-parse", "HEAD"], root),
        "git_working_tree": command_output(["git", "status", "--short"], root),
        "source_note": "Measurements describe the local working tree, including uncommitted changes; HEAD alone does not identify this build.",
    }


def format_value(value, decimals=2):
    return "Not measured" if value is None else f"{value:,.{decimals}f}"


def select_design_report(report, modes=MODES):
    """Derive a design-only comparison without rerunning or inventing samples."""
    selected = tuple(modes)
    if not selected or len(set(selected)) != len(selected) or any(mode not in MODES for mode in selected):
        raise ValueError("Select distinct designs: aruco, orb, optical-flow")
    result = copy.deepcopy(report)
    result["comparison_scope"] = {
        "designs": list(selected), "normal_mode_included": False,
        "shared_controls": ["application infrastructure and assets", "canine model geometry"],
    }
    result["purpose"] = "Compare Designs 1, 2 and 3; shared application/model measurements are supplementary context"
    result["design_metrics"] = collect_design_metrics(result["static"])
    result["design_metrics"]["designs"] = [item for item in result["design_metrics"]["designs"] if item["id"] in selected]
    runtime = result["runtime"]
    if runtime["status"] != "not_requested":
        for trial in runtime["runs"]:
            observations = {item["mode"]: item for item in trial.get("modes", [])}
            trial["modes"] = [observations[mode] for mode in selected if mode in observations]
            missing = [mode for mode in selected if mode not in observations]
            if missing:
                trial["missing_designs"] = missing
            statuses = [item["status"] for item in trial["modes"]]
            trial["status"] = "measured" if not missing and all(value == "measured" for value in statuses) else "partial" if any(value in {"measured", "partial"} for value in statuses) else "unmeasured"
        statuses = [trial["status"] for trial in runtime["runs"]]
        runtime["status"] = "measured" if statuses and all(value == "measured" for value in statuses) else "partial" if any(value in {"measured", "partial"} for value in statuses) else "unmeasured"
    return result


def summary_markdown(report):
    storage = report["static"]["storage"]
    mi = report["static"]["maintainability"]
    coverage = mi["coverage"]
    lines = [
        "# PupVitals constraint v2: three-design comparison", "",
        f"Collected: {report['generated_at_utc']}", "",
        "These are measurements, with no pass/fail limits assigned. MB means 1,000,000 bytes.", "",
        "Official comparison: Design 1 (ArUco), Design 2 (ORB + RANSAC), Design 3 (optical flow). Normal mode is outside this comparison.", "",
        "## Design-specific source measurements", "",
        "Each row covers that design's tracker module only. Shared frontend/backend, common tracking code and assets are excluded from these module totals; these are not standalone application footprints.", "",
        "| Design | Tracker source MB | Tracker Python MI / 100 |", "| --- | ---: | ---: |",
    ]
    designs = report.get("design_metrics") or collect_design_metrics(report["static"])
    for item in designs["designs"]:
        lines.append(f"| {item['label']} | {format_value(item['storage']['mb'], 6)} | {format_value(item['maintainability']['score_0_100'])} |")
    if report.get("derived_from_report"):
        lines.insert(4, "Comparison derived from existing observations; no new experiment was run. Source: " + report["derived_from_report"])
        lines.insert(5, "")
    lines.extend([
        "", "## Shared application context", "",
        "The three designs use the same application infrastructure and models. The following totals include all three trackers and are supplementary context, not separate per-design scores.", "",
        "| Metric | Result | Scope |", "| --- | --- | --- |",
        f"| Raw application storage | {storage['application_raw']['mb']:.6f} MB | Source, configuration, models and runtime assets; excludes installed dependencies/builds |",
        f"| Raw repository storage | {storage['total_mb']:.6f} MB | Also includes documentation, tests, reference photos and measurement tools |",
        f"| Python Maintainability Index mean | {format_value(mi['mean_score_0_100'])} / 100 | {coverage['python_files_analyzed']} of {coverage['python_files_eligible']} eligible Python files |",
        f"| Python Maintainability Index median | {format_value(mi['median_score_0_100'])} / 100 | Per-file summary; frontend JS/JSX is unmeasured |", "",
        f"Non-Python source files outside MI coverage: {coverage['non_python_source_files_not_analyzed']}. No whole-application MI is claimed.", "",
        "## Canine model complexity", "",
    ])
    model = report["model_complexity"]
    if model["status"] == "measured":
        lines.extend(["| Breed | Standing triangles | Lying triangles | Model |", "| --- | ---: | ---: | --- |"])
        for item in model["models"]:
            lines.append(f"| {item['breed_label']} | {item['poses']['standing']['triangle_count']:,} | {item['poses']['lying']['triangle_count']:,} | Current procedural dog |")
        lines.extend(["", "All three designs use the same canine geometry for a selected breed. Counts apply to one visible model and are a shared control, not a difference between trackers. They are triangle counts, not original Blender polygon counts or rendering FPS. Final Blender/GLB assets require another measurement."])
    else:
        lines.append("Not measured: " + model.get("reason", "Model measurement unavailable."))
    lines.extend(["", "## Simulation latency and RAM", ""])
    runtime = report["runtime"]
    if runtime["status"] == "not_requested":
        lines.extend(["Not measured in this run. Use `--runtime` to start isolated production-browser trials.",
                      "Physical ESP32 input-to-display latency is unmeasured."])
    else:
        lines.extend(["Preliminary headless Edge with SwiftShader software rendering and synthetic camera targets. Latency starts at a simulated-angle control click and ends at matching DOM feedback plus two animation-frame callbacks, a display-update proxy. Physical acquisition/transport and pixel presentation are excluded.", "",
                      "| Repeat | Mode | Status | Latency samples OK/attempted | Mean ms | P95 ms | Mean RAM MB | Sampled peak RAM MB |",
                      "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |"])
        for index, run in enumerate(runtime["runs"], 1):
            for item in run.get("modes", []):
                latency, memory = item.get("latency", {}), item.get("memory", {})
                lines.append(f"| {index} | {item['mode']} | {item['status']} | {latency.get('successful_samples', 0)}/{latency.get('attempted_samples', 0)} | {format_value(latency.get('mean_ms'))} | {format_value(latency.get('p95_ms'))} | {format_value(memory.get('mean_mb'))} | {format_value(memory.get('sampled_peak_mb'))} |")
        for index, run in enumerate(runtime["runs"], 1):
            if run.get("error"):
                lines.extend(["", f"Repeat {index} error: {run['error']}"])
            if run.get("missing_designs"):
                lines.extend(["", f"Repeat {index} missing designs: {', '.join(run['missing_designs'])}"])
            for item in run.get("modes", []):
                if item.get("error"):
                    lines.extend(["", f"Repeat {index}, {item['mode']}: {item['error']}"])
                if item.get("tracking_warning"):
                    lines.extend(["", f"Repeat {index}, {item['mode']}: {item['tracking_warning']}"])
        lines.extend(["", "RAM sums the isolated browser and Python backend process working sets. Shared pages can be counted more than once; sampling can miss short peaks. Preview server/controller and unrelated applications are excluded.",
                      "Tracking uses synthetic ArUco or non-coded texture artwork; it does not validate the unchanged physical injection pad. See JSON for setup failures, tracking diagnostics, raw samples and component RAM."])
    lines.extend(["", "Physical sensor latency, final GPU operation, final Blender assets and a packaged Electron application still require measurements in their intended operating conditions.", "",
                  "Full per-file inventory, exclusions, environment, source fingerprints, errors and raw observations are in the companion JSON.", ""])
    return "\n".join(lines)


def collect(root, *, runtime=False, seconds=5, samples=5, repeats=1, modes=MODES):
    static = collect_static_metrics(root)
    report = {
        "schema_version": 2, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Compare Designs 1, 2 and 3; shared application/model measurements are supplementary context",
        "comparison_scope": {"designs": list(modes), "normal_mode_included": False},
        "definitions": json.loads((root / "constraintv2/definitions.json").read_text(encoding="utf-8")),
        "environment": environment(root), "static": static,
        "design_metrics": collect_design_metrics(static),
        "source_fingerprint": fingerprint(root, static["storage"]["files"]),
        "production_build": production_build(root),
        "model_complexity": model_complexity(root),
        "runtime": {"status": "not_requested", "runs": []},
        "physical_sensor_latency": {"status": "not_measured", "reason": "No physical ESP32 sampling/transport-to-display trial was performed."},
    }
    if runtime:
        from runtime_metrics import run_runtime
        runs = report["runtime"]["runs"]
        for index in range(repeats):
            offset = index % len(modes)
            order = modes[offset:] + modes[:offset]
            print(f"Runtime repeat {index + 1}/{repeats}: {', '.join(order)}", flush=True)
            try:
                runs.append(run_runtime(root, seconds=seconds, samples=samples, modes=order))
            except (OSError, RuntimeError, ImportError, ValueError) as error:
                runs.append({"status": "unmeasured", "modes": [], "error": str(error)})
        measured = sum(item["status"] == "measured" for item in runs)
        report["runtime"]["status"] = "measured" if measured == repeats else "partial" if measured or any(item["status"] == "partial" for item in runs) else "unmeasured"
        report["runtime"]["repeat_order"] = "Rotate the first mode on each repeat; each repeat otherwise sequential. No statistical randomization is claimed."
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--runtime", action="store_true", help="Measure Designs 1-3 with private backend, production preview and headless Edge; synthetic inputs only")
    action.add_argument("--from-report", type=Path, help="Make a three-design view of existing observations without remeasuring; preserve original timestamps")
    action.add_argument("--refresh-comparison", action="store_true", help="Refresh comparisons and Markdown from saved numbered JSON files; no measurements are replaced")
    parser.add_argument("--seconds", type=float, default=5, help="Minimum steady measurement duration per mode (default: 5)")
    parser.add_argument("--samples", type=int, default=5, help="Simulated-angle latency trials per mode (default: 5)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--constraints", nargs="+", type=int, choices=range(1, 6), default=list(range(1, 6)), help="Replace only these numbered constraint results (default: all five)")
    parser.add_argument("--output-root", type=Path, default=ROOT / "constraintv2/resultsv2")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 3600 or not 1 <= args.samples <= 1000 or not 1 <= args.repeats <= 100:
        parser.error("seconds must be >0 and <=3600; samples 1..1000; repeats 1..100")
    if len(set(args.modes)) != len(args.modes):
        parser.error("Choose distinct modes")
    if len(set(args.constraints)) != len(args.constraints):
        parser.error("Choose distinct constraint numbers")
    if args.refresh_comparison:
        outputs = refresh_results(args.output_root.resolve())
        print(f"Overall comparison refreshed: {outputs['comparison']}")
        print("Saved constraint JSON records and measurements were preserved.")
        return
    if args.from_report:
        source = args.from_report.resolve(strict=True)
        report = select_design_report(json.loads(source.read_text(encoding="utf-8")), tuple(args.modes))
        report["derived_from_report"] = str(source)
        report["report_generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    else:
        report = collect(ROOT, runtime=args.runtime, seconds=args.seconds, samples=args.samples,
                         repeats=args.repeats, modes=tuple(args.modes))
    outputs = write_results(report, args.output_root.resolve(), constraints=args.constraints)
    print(f"Overall comparison: {outputs['comparison']}")
    for design, path in outputs["designs"].items():
        print(f"{design}: {path}")
    print(f"Full measurements: {outputs['measurements']}")
    print(f"Runtime: {report['runtime']['status']}; physical sensor latency: not measured; acceptance limits: not set")


if __name__ == "__main__":
    main()
