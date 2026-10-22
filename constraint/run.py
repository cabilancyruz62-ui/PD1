"""Measure the three existing tracking designs on controlled synthetic scenes."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DESIGNS = {"aruco": "design-1-aruco", "orb": "design-2-orb-ransac",
           "optical-flow": "design-3-optical-flow"}
CONDITIONS = ("stationary", "camera_motion", "dim_light", "occlusion_recovery", "target_absent")
CSV_FIELDS = ("design", "trial", "condition", "frame_index", "expected_visible",
              "status", "tracked", "correct", "false_positive", "corner_error_px",
              "center_residual_x", "center_residual_y", "elapsed_ms", "cycle_ms")


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", choices=("all", *DESIGNS), default="all")
    parser.add_argument("--frames", type=positive_int, default=180, help="Frames per condition per repeat")
    parser.add_argument("--repeats", type=positive_int, default=3)
    parser.add_argument("--fps", type=positive_int, default=30, help="Synthetic source pacing rate")
    parser.add_argument("--warmup", type=positive_int, default=10)
    parser.add_argument("--width", type=positive_int, default=1280)
    parser.add_argument("--height", type=positive_int, default=720)
    parser.add_argument("--conditions", choices=CONDITIONS, nargs="+", default=list(CONDITIONS))
    parser.add_argument("--limits", type=Path, default=ROOT / "limits.json")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--unpaced", action="store_true", help="Run at maximum throughput instead of source FPS")
    parser.add_argument("--opencv-threads", type=positive_int, help="Optional fixed OpenCV thread count")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--condition", choices=CONDITIONS, help=argparse.SUPPRESS)
    parser.add_argument("--trial", type=positive_int, default=1, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.frames < 3:
        parser.error("--frames must be at least 3 to represent occlusion phases")
    if args.width < 480 or args.height < 360:
        parser.error("minimum synthetic resolution is 480x360")
    if len(args.conditions) != len(set(args.conditions)):
        parser.error("--conditions must not contain duplicates")
    if args.worker and (args.design == "all" or not args.condition or not args.worker_output):
        parser.error("worker mode requires one design, condition, and output file")
    return args


def read_limits(path):
    limits = json.loads(path.read_text(encoding="utf-8"))
    required = ("memory_gb", "response_p95_ms", "tracking_success_pct",
                "false_positive_pct", "cpu_pct", "rendering_min_fps", "corner_tolerance_px")
    for key in required:
        value = limits.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"limits.json needs a finite nonnegative number for {key}")
        if key.endswith("pct") and value > 100:
            raise ValueError(f"{key} must be at most 100")
    return limits


def load_tracker_module(design):
    # Import the actual implementation; benchmarking never substitutes a mock tracker.
    sys.path.insert(0, str(PROJECT / "designs"))
    path = PROJECT / "designs" / DESIGNS[design] / "tracker.py"
    spec = importlib.util.spec_from_file_location(f"benchmark_{design.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def worker(args, limits):
    import cv2
    import numpy as np
    from metrics import score_frame, summarize_frames
    from profiling import ResourceMonitor, environment_info
    from scenes import SyntheticScene

    if args.opencv_threads is not None:
        cv2.setNumThreads(args.opencv_threads)
    cv2.setRNGSeed(42)
    scene = SyntheticScene(args.design, args.condition, args.width, args.height, seed=42)
    module = load_tracker_module(args.design)
    started = time.perf_counter()
    if args.design == "aruco":
        tracker = module.ArucoTracker(marker_id=0)
        initial = tracker.update(scene.initial_frame)
    elif args.design == "orb":
        tracker = module.OrbTracker(reference=scene.reference)
        initial = tracker.update(scene.initial_frame)
    else:
        tracker = module.OpticalFlowTracker()
        initial = tracker.initialize(scene.initial_frame, scene.roi)
    initialization_ms = (time.perf_counter() - started) * 1000
    if not initial.tracked:
        raise ValueError(f"{args.design} could not initialize: {initial.detail}")
    for _ in range(args.warmup):
        tracker.update(scene.initial_frame)

    rows = []
    with ResourceMonitor() as monitor:
        run_started = time.perf_counter()
        for index in range(args.frames):
            cycle_started = time.perf_counter()
            frame, expected, visible = scene.frame(index, args.frames)
            started = time.perf_counter_ns()
            result = tracker.update(frame)
            elapsed_ms = (time.perf_counter_ns() - started) / 1e6
            row = {"design": args.design, "trial": args.trial, "condition": args.condition,
                   "frame_index": index, "expected_visible": visible, "status": result.status,
                   "elapsed_ms": elapsed_ms,
                   **score_frame(result, expected, visible, limits["corner_tolerance_px"])}
            row["center_residual_x"] = row["center_residual_y"] = None
            if row["corner_error_px"] is not None:
                residual = np.asarray(result.corners).mean(axis=0) - expected.mean(axis=0)
                row.update(center_residual_x=float(residual[0]), center_residual_y=float(residual[1]))
            row["cycle_ms"] = (time.perf_counter() - cycle_started) * 1000
            rows.append(row)
            monitor.observe()
            if not args.unpaced:
                remaining = run_started + (index + 1) / args.fps - time.perf_counter()
                if remaining > 0:
                    time.sleep(remaining)
    resources = monitor.summary()
    metrics = summarize_frames(rows, limits["corner_tolerance_px"], args.fps)
    metrics["source_budget_miss_frames"] = sum(row["cycle_ms"] > 1000 / args.fps for row in rows)
    metrics["actual_worker_fps"] = args.frames / resources["wall_seconds"]
    return {"design": args.design, "trial": args.trial, "condition": args.condition,
            "initialization_ms": initialization_ms, "environment": environment_info(),
            "opencv_threads": cv2.getNumThreads(), "resources": resources,
            "metrics": metrics, "rows": rows}


def display(value, digits=2):
    return "N/A" if value is None else f"{value:.{digits}f}"


def report_markdown(summary):
    metrics, resources = summary["metrics"], summary["resources"]
    lines = [f"# {summary['folder']} constraint results", "", "**Controlled synthetic benchmark; not a physical-dummy validation.**", "",
             f"Measured: {summary['measured_at_utc']} (UTC).", "",
             f"Resolution: {summary['configuration']['width']} x {summary['configuration']['height']}; "
             f"source: {summary['configuration']['fps']} FPS; paced: {summary['configuration']['paced']}; "
             f"frames per condition/repeat: {summary['configuration']['frames_per_condition']}; repeats: {summary['configuration']['repeats']}.", "",
             "Limits are proposed project budgets, not clinical or industry standards.", "",
             "| Constraint | Observed | Target | Result |", "| --- | --- | --- | --- |"]
    for key, label in (("memory", "Peak observed RAM"), ("response_time", "Processing P95"),
                       ("tracking_performance", "Correct visible frames"), ("rendering_fps", "3D rendering FPS"),
                       ("cpu", "Normalized CPU")):
        item = summary["constraints"][key]
        direction = ">=" if key in ("tracking_performance", "rendering_fps") else "<="
        lines.append(f"| {label} | {display(item['observed'], 4 if key == 'memory' else 2)} {item['unit']} | "
                     f"{direction} {item['target']:g} {item['unit']} | {item['status']} |")
    lines += ["", "| Condition | Processing P95 (ms) | Correct visible frames (%) | False tracking when absent (%) | Corner error P95 (px) |",
              "| --- | --- | --- | --- | --- |"]
    for condition, values in summary["by_condition"].items():
        lines.append(f"| {condition} | {display(values['processing_p95_ms'])} | {display(values['valid_tracking_pct'])} | "
                     f"{display(values['false_positive_pct'])} | {display(values['corner_error_p95_px'])} |")
    lines += ["", f"Frames scored: {metrics['total_frames']}; visible: {metrics['visible_frames']}; absent: {metrics['absent_frames']}.",
              f"Overall false tracking: {display(metrics['false_positive_pct'])}%; "
              f"limit: {summary['limits']['false_positive_pct']:g}% of absent frames.",
              f"Stationary error jitter RMS: {display(summary['by_condition'].get('stationary', {}).get('tracking_error_jitter_rms_px'))} px.",
              f"Mean normalized CPU: {display(resources['cpu_normalized_pct'])}%; "
              f"largest individual trial mean: {display(resources['largest_trial_cpu_normalized_pct'])}%.", "",
              "## Measurement boundaries", ""]
    lines += [f"- {note}" for note in summary["notes"]]
    lines += ["", "## Environment", "", "```json", json.dumps(summary["environment"], indent=2), "```", "",
              "Raw frames: [frames.csv](frames.csv). Individual trial summaries: [trials.json](trials.json).", ""]
    return "\n".join(lines)


def summarize_design(design, trials, args, limits, measured_at):
    from metrics import evaluate_constraints, summarize_frames

    rows = [row for trial in trials for row in trial["rows"]]
    metrics = summarize_frames(rows, limits["corner_tolerance_px"], args.fps)
    peaks = [t["resources"]["peak_memory_gb"] for t in trials if t["resources"]["peak_memory_gb"] is not None]
    measured = [t for t in trials if t["resources"]["cpu_seconds"] is not None and t["resources"]["cpu_normalized_pct"] is not None]
    cpu = None
    if measured:
        wall = sum(t["resources"]["wall_seconds"] for t in measured)
        cpu = sum(t["resources"]["cpu_normalized_pct"] * t["resources"]["wall_seconds"] for t in measured) / wall
    resources = {"peak_memory_gb": max(peaks) if peaks else None,
                 "cpu_normalized_pct": cpu,
                 "largest_trial_cpu_normalized_pct": max((t["resources"]["cpu_normalized_pct"] for t in measured), default=None),
                 "measurement_errors": sorted({error for t in trials for error in t["resources"]["measurement_errors"]})}
    notes = [
        "The existing production tracker modules are imported without algorithm changes; each trial runs in a fresh isolated process.",
        "All designs use the same resolution, conditions, seed, pacing, and repeat count. ArUco requires a marker; ORB/flow use a textured patch, not the marker pattern.",
        "Correctness requires a tracked, valid quadrilateral with mean ordered-corner error within the configured tolerance; tracker status alone is insufficient.",
        "Initialization and warmup are excluded from scored frames, processing latency, and interval CPU. Reference/ROI preparation is supplied automatically; human setup time is not measured.",
        "RAM is peak observed process RSS in decimal GB, sampled every 50 ms and after each frame. Includes Python, OpenCV, target fixtures, tracker, and growing measurement rows; short peaks may be missed.",
        "CPU covers the complete worker window, including synthetic-frame preparation, scoring, sampling, and pacing. It is normalized across logical cores. It does not describe the browser/backend or the whole computer's background load.",
        "Processing time covers tracker.update only; excludes capture, frame generation, scoring, display, network, and camera-to-overlay latency. CPU/memory and processing time therefore have different measurement boundaries.",
        "No camera, video decoder, website, or 3D renderer is running in this test. Rendering FPS is N/A, not zero or a passing result; final-model rendering must be measured after integration.",
        "Camera-motion frames are synthetic similarity warps. Dim-light frames step from bright initialization to alpha=0.42, beta=10; this also tests an illumination change.",
        "Occlusion removes the complete target for the middle third. Optical flow is not automatically reselected; missing a returned visible target counts as failure. No human recovery time is inferred.",
        "A cheap lost-state update can lower processing time/CPU while accuracy fails. Interpret resource and correctness results together; these tests do not prove dummy identity or realistic hand-occlusion robustness.",
    ]
    if args.unpaced:
        notes.append("This run is unpaced maximum-throughput mode; CPU results are not representative of a paced 30-FPS station.")
    source_files = [ROOT / name for name in ("run.py", "scenes.py", "metrics.py", "profiling.py")]
    source_files += [PROJECT / "designs" / DESIGNS[design] / "tracker.py", PROJECT / "designs" / "tracking_common.py"]
    fingerprints = {path.relative_to(PROJECT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in source_files}
    return {"schema_version": 1, "design": design, "folder": DESIGNS[design],
            "source_type": "deterministic_synthetic", "measured_at_utc": measured_at,
            "source_sha256": fingerprints,
            "configuration": {"width": args.width, "height": args.height, "fps": args.fps,
                              "paced": not args.unpaced, "frames_per_condition": args.frames,
                              "repeats": args.repeats, "warmup_frames": args.warmup,
                              "conditions": args.conditions, "seed": 42,
                              "opencv_threads": sorted({t["opencv_threads"] for t in trials})},
            "limits": limits, "environment": trials[0]["environment"], "resources": resources,
            "metrics": metrics,
            "by_condition": {condition: summarize_frames([r for r in rows if r["condition"] == condition],
                                                        limits["corner_tolerance_px"], args.fps)
                             for condition in args.conditions},
            "constraints": evaluate_constraints(metrics, resources["peak_memory_gb"], cpu, limits),
            "notes": notes}


def controller(args, limits):
    designs = list(DESIGNS) if args.design == "all" else [args.design]
    trials = {design: [] for design in designs}
    measured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print("Synthetic-only benchmark. Workers run sequentially; no webcam or GPU renderer is used.", flush=True)
    with tempfile.TemporaryDirectory(prefix="pupvitals-constraints-") as temporary:
        for repeat in range(args.repeats):
            # Rotate design order to reduce a fixed first/last bias across repeats.
            order = designs[repeat % len(designs):] + designs[:repeat % len(designs)]
            for design in order:
                for condition in args.conditions:
                    output = Path(temporary) / f"{design}-{repeat}-{condition}.json"
                    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--design", design,
                               "--condition", condition, "--trial", str(repeat + 1), "--frames", str(args.frames),
                               "--warmup", str(args.warmup), "--fps", str(args.fps), "--width", str(args.width),
                               "--height", str(args.height), "--limits", str(args.limits.resolve()),
                               "--worker-output", str(output)]
                    if args.unpaced:
                        command.append("--unpaced")
                    if args.opencv_threads is not None:
                        command += ["--opencv-threads", str(args.opencv_threads)]
                    print(f"{design}: {condition}, repeat {repeat + 1}/{args.repeats}", flush=True)
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    try:
                        stdout, stderr = process.communicate(timeout=max(60, args.frames / args.fps * 10 + 30))
                    except BaseException:
                        process.kill()
                        process.communicate()
                        raise
                    if process.returncode:
                        raise ValueError(f"{design}/{condition} failed: {stderr.strip() or stdout.strip()}")
                    trials[design].append(json.loads(output.read_text(encoding="utf-8")))

    summaries = []
    for design in designs:
        summary = summarize_design(design, trials[design], args, limits, measured_at)
        destination = args.output_root / DESIGNS[design] / "results"
        write_json(destination / "summary.json", summary)
        write_json(destination / "trials.json", [{key: value for key, value in trial.items() if key != "rows"}
                                                for trial in trials[design]])
        with (destination / "frames.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(row for trial in trials[design] for row in trial["rows"])
        (destination / "summary.md").write_text(report_markdown(summary), encoding="utf-8")
        summaries.append(summary)
    write_json(args.output_root / "comparison.json", summaries)
    lines = ["# Tracking constraint comparison", "", "**Measured on synthetic inputs only. Rendering FPS has not been measured.**", "",
             f"Run started: {measured_at} (UTC).", "",
             "| Design | Peak observed RAM (GB) | Processing P95 (ms) | Correct visible frames (%) | False tracking (%) | Normalized CPU (%) | 3D FPS |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for summary in summaries:
        m, r = summary["metrics"], summary["resources"]
        lines.append(f"| [{summary['folder']}]({summary['folder']}/results/summary.md) | "
                     f"{display(r['peak_memory_gb'], 4)} | {display(m['processing_p95_ms'])} | "
                     f"{display(m['valid_tracking_pct'])} | {display(m['false_positive_pct'])} | "
                     f"{display(r['cpu_normalized_pct'])} | N/A |")
    lines += ["", "See each design report for limits, pass/fail results, conditions, environment, and measurement boundaries.",
              "These measurements are not evidence of physical-dummy recognition or final-model performance.", ""]
    (args.output_root / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {len(summaries)} design report(s) and comparison.md under {args.output_root}", flush=True)


def main(argv=None):
    args = parse_args(argv)
    try:
        limits = read_limits(args.limits)
        if args.worker:
            write_json(args.worker_output, worker(args, limits))
        else:
            controller(args, limits)
        return 0
    except ImportError as error:
        print(f"Missing benchmark dependency: {error}. Install: python -m pip install -r constraint/requirements.txt", file=sys.stderr)
        return 1
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Constraint benchmark: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
