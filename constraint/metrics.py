"""Ground-truth scoring and summaries for the standalone tracking benchmarks.

Times describe tracker computation, not camera-to-display latency. All returned
values can be serialized with ``json.dumps(..., allow_nan=False)``.
"""

import math

import numpy as np


def _number(value):
    if isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _quad(value):
    try:
        quad = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        return None
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        return None
    edges = np.roll(quad, -1, axis=0) - quad
    following = np.roll(edges, -1, axis=0)
    cross = edges[:, 0] * following[:, 1] - edges[:, 1] * following[:, 0]
    if not (np.all(cross > 1e-9) or np.all(cross < -1e-9)):
        return None
    return quad


def score_frame(result, expected_corners, expected_visible, tolerance_px=5.0):
    """Compare ordered TL/TR/BR/BL corners using mean Euclidean error.

    A tracker claiming a target in an absent frame is a false positive even if
    its output polygon is malformed. Tracking status alone never means correct.
    """
    tolerance = _number(tolerance_px)
    if tolerance is None or tolerance < 0:
        raise ValueError("tolerance_px must be finite and nonnegative")
    visible = bool(expected_visible)
    tracked = bool(getattr(result, "tracked", False))
    actual = _quad(getattr(result, "corners", None)) if tracked else None
    expected = _quad(expected_corners) if visible else None
    error = None
    if actual is not None and expected is not None:
        error = _number(np.linalg.norm(actual - expected, axis=1).mean())
    return {
        "tracked": tracked,
        "correct": bool(visible and tracked and error is not None and error <= tolerance),
        "false_positive": bool(not visible and tracked),
        "corner_error_px": error,
    }


def summarize_frames(rows, tolerance_px=5.0, source_fps=30.0):
    """Summarize scored rows; missing correctness is counted as unsuccessful."""
    tolerance = _number(tolerance_px)
    fps = _number(source_fps)
    if tolerance is None or tolerance < 0 or fps is None or fps <= 0:
        raise ValueError("Provide nonnegative finite tolerance and positive finite source_fps")
    visible = [row for row in rows if row.get("expected_visible", False)]
    absent = [row for row in rows if not row.get("expected_visible", False)]
    correct = sum(bool(row.get("correct", False)) for row in visible)
    false_positives = sum(bool(row.get("tracked", False)) for row in absent)
    errors = [value for row in visible if row.get("tracked", False)
              if (value := _number(row.get("corner_error_px"))) is not None and value >= 0]
    timings = [value for row in rows
               if (value := _number(row.get("elapsed_ms"))) is not None and value >= 0]
    residuals = []
    for row in visible:
        x = _number(row.get("center_residual_x"))
        y = _number(row.get("center_residual_y"))
        if row.get("tracked", False) and x is not None and y is not None:
            residuals.append((x, y))
    jitter = None
    if len(residuals) >= 2:
        residuals = np.asarray(residuals, dtype=np.float64)
        centered = residuals - residuals.mean(axis=0)
        jitter = float(np.sqrt(np.mean(np.sum(centered ** 2, axis=1))))
    mean_ms = float(np.mean(timings)) if timings else None
    return {
        "total_frames": len(rows),
        "visible_frames": len(visible),
        "absent_frames": len(absent),
        "tracked_frames": sum(bool(row.get("tracked", False)) for row in rows),
        "correct_frames": correct,
        "false_positive_frames": false_positives,
        "valid_tracking_pct": correct / len(visible) * 100 if visible else None,
        "false_positive_pct": false_positives / len(absent) * 100 if absent else None,
        "corner_error_median_px": float(np.median(errors)) if errors else None,
        "corner_error_p95_px": float(np.percentile(errors, 95)) if errors else None,
        "tracking_error_jitter_rms_px": jitter,
        "processing_median_ms": float(np.median(timings)) if timings else None,
        "processing_p95_ms": float(np.percentile(timings, 95)) if timings else None,
        "processing_max_ms": max(timings) if timings else None,
        "tracking_throughput_fps": 1000 / mean_ms if mean_ms and mean_ms > 0 else None,
        "source_fps": fps,
        "tolerance_px": tolerance,
    }


def evaluate_constraints(metrics, peak_memory_gb, cpu_normalized_pct, limits=None):
    """Evaluate proposed project limits; 3D rendering is not measured here."""
    limits = {"memory_gb": 1.0, "response_p95_ms": 33.0,
              "tracking_success_pct": 95.0, "false_positive_pct": 1.0,
              "cpu_pct": 60.0, **(limits or {})}

    def upper(observed, target, unit, reason):
        value = _number(observed)
        return {"status": "insufficient_data" if value is None else
                ("pass" if value <= target else "fail"),
                "observed": value, "target": target, "unit": unit, "reason": reason}

    success = _number(metrics.get("valid_tracking_pct"))
    false_positive = _number(metrics.get("false_positive_pct"))
    status = "pass" if success is not None and false_positive is not None else "insufficient_data"
    if (success is not None and success < limits["tracking_success_pct"]
            or false_positive is not None and false_positive > limits["false_positive_pct"]):
        status = "fail"
    tracking = {
        "status": status, "observed": success,
        "target": limits["tracking_success_pct"], "unit": "%",
        "false_positive_pct": false_positive,
        "false_positive_limit_pct": limits["false_positive_pct"],
        "reason": "Correct visible-target frames within the corner-error tolerance; "
                  "false-positive rate must also meet its limit."
                  + (" No absent-target frames were evaluated." if false_positive is None else ""),
    }
    return {
        "memory": upper(peak_memory_gb, limits["memory_gb"], "GB",
                        "Peak sampled resident memory of the benchmark process (decimal GB)."),
        "response_time": upper(metrics.get("processing_p95_ms"), limits["response_p95_ms"],
                               "ms", "95th-percentile tracker processing time; excludes capture and display."),
        "tracking_performance": tracking,
        "rendering_fps": {"status": "not_applicable", "observed": None, "target": limits.get("rendering_min_fps", 30.0),
                          "unit": "FPS", "reason": "No shared 3D renderer is integrated into these prototypes."},
        "cpu": upper(cpu_normalized_pct, limits["cpu_pct"], "%",
                     "Process CPU utilization normalized across all logical CPU cores."),
    }
