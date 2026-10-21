"""Shared image-space tracking output for the three standalone experiments."""

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class TrackingResult:
    status: str
    detail: str
    corners: np.ndarray | None = None
    points: np.ndarray | None = None
    metrics: dict[str, int | float | list[int]] = field(default_factory=dict)

    @property
    def tracked(self) -> bool:
        return self.status == "tracking" and self.corners is not None


def valid_quad(corners: np.ndarray | None, frame_shape: tuple) -> bool:
    """Reject degenerate, nonfinite, tiny, or off-screen target projections."""
    if corners is None:
        return False
    quad = np.asarray(corners, dtype=np.float32)
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        return False
    height, width = frame_shape[:2]
    if (quad < 0).any() or (quad[:, 0] > width - 1).any() or (quad[:, 1] > height - 1).any():
        return False
    contour = quad.reshape(-1, 1, 2)
    edges = np.linalg.norm(quad - np.roll(quad, 1, axis=0), axis=1)
    return bool(
        cv2.isContourConvex(contour)
        and cv2.contourArea(contour) >= 100
        and edges.min() >= 8
    )


def draw_result(frame: np.ndarray, result: TrackingResult, title: str, processing_ms: float) -> np.ndarray:
    """Draw a 2D target proxy only for a currently valid tracking result."""
    output = frame.copy()
    color = (100, 225, 145) if result.tracked else (90, 150, 255)
    if result.tracked and valid_quad(result.corners, frame.shape):
        polygon = np.rint(result.corners).astype(np.int32)
        tint = output.copy()
        cv2.fillConvexPoly(tint, polygon, (55, 155, 90))
        output = cv2.addWeighted(tint, 0.2, output, 0.8, 0)
        cv2.polylines(output, [polygon], True, color, 2)
        center = tuple(np.rint(result.corners.mean(axis=0)).astype(int))
        cv2.drawMarker(output, center, color, cv2.MARKER_CROSS, 24, 2)
        if result.points is not None:
            for point in np.asarray(result.points).reshape(-1, 2)[:200]:
                if np.isfinite(point).all():
                    cv2.circle(output, tuple(np.rint(point).astype(int)), 2, color, -1)
    cv2.rectangle(output, (0, 0), (output.shape[1] - 1, 104), (22, 28, 26), -1)
    lines = [
        f"PupVitals | {title} | {result.status.upper()}",
        result.detail,
        f"Processing: {processing_ms:.1f} ms | s: select region | r: reset | q / Esc: quit",
    ]
    for index, line in enumerate(lines):
        cv2.putText(output, line, (12, 25 + index * 31), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
    return output
