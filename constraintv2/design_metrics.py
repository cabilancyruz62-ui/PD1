"""Extract each tracker's own-file measurements from one static inventory.

These measurements describe the individual implementations, not separate
installable applications. Shared runtime and rendering code stays supplemental.
"""
from __future__ import annotations

import math


DESIGNS = (
    ("aruco", "Design 1: ArUco", "designs/design-1-aruco/tracker.py"),
    ("orb", "Design 2: ORB + RANSAC", "designs/design-2-orb-ransac/tracker.py"),
    ("optical-flow", "Design 3: Optical flow", "designs/design-3-optical-flow/tracker.py"),
)
MB_BYTES = 1_000_000
STORAGE_SCOPE = "This design's tracker.py source file only; not standalone application or installed storage."
MI_SCOPE = "This design's tracker.py Python file only; not a whole-application Maintainability Index."


def _failure_reason(path, report, fallback):
    for error in report.get("errors", []):
        if error.get("path") == path:
            return str(error.get("reason", error.get("error", fallback)))
    return str(report.get("reason") or fallback)


def collect_design_metrics(static_report):
    """Return three design rows without re-reading files or launching services.

    ``static_report`` is the result of ``collect_static_metrics``. File storage
    comes from its storage inventory and MI from its existing per-file results.
    Missing or invalid observations remain unknown rather than becoming zero.
    """
    storage_report = static_report.get("storage", {})
    mi_report = static_report.get("maintainability", {})
    inventory = {item["path"]: item for item in storage_report.get("files", [])}
    scores = {item["path"]: item for item in mi_report.get("files", [])}
    result = {
        "scope": "Own tracker implementations for Designs 1, 2 and 3; shared application measurements are supplemental.",
        "mb_definition": "1 MB = 1,000,000 bytes",
        "shared_components_excluded": [
            "designs/tracking_common.py",
            "shared frontend, backend and tracking transport",
            "canine models and rendering assets",
            "dependencies, reference/marker artwork, documentation and tests",
        ],
        "designs": [],
    }
    for identifier, label, path in DESIGNS:
        storage = {"status": "unavailable", "bytes": None, "mb": None, "scope": STORAGE_SCOPE}
        item = inventory.get(path)
        if item is None:
            storage["reason"] = _failure_reason(path, storage_report, "Tracker file is absent from the measured storage inventory.")
        elif type(item.get("bytes")) is int and item["bytes"] >= 0:
            storage.update(status="measured", bytes=item["bytes"], mb=item["bytes"] / MB_BYTES)
        else:
            storage["reason"] = "Tracker file storage observation is invalid or unknown."

        maintainability = {
            "status": "unavailable", "score_0_100": None, "scope": MI_SCOPE,
            "method": mi_report.get("method", "Existing Radon per-file Python MI result"),
            "radon_version": mi_report.get("radon_version"),
        }
        score = scores.get(path, {}).get("score_0_100")
        if item is None:
            maintainability["reason"] = "Tracker file is absent from the measured storage inventory; no current-file MI is claimed."
        elif isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and 0 <= score <= 100:
            maintainability.update(status="measured", score_0_100=score)
        else:
            maintainability["reason"] = _failure_reason(path, mi_report, "No valid per-file Python Maintainability Index was measured for this tracker.")
        result["designs"].append({
            "id": identifier, "label": label, "path": path,
            "storage": storage, "maintainability": maintainability,
        })

    statuses = [row[metric]["status"] for row in result["designs"] for metric in ("storage", "maintainability")]
    result["status"] = "measured" if all(value == "measured" for value in statuses) else "partial" if "measured" in statuses else "unavailable"
    return result
