"""Detect one configured ArUco marker as a 2D proxy for the dummy."""

from numbers import Integral

import cv2
import numpy as np

from tracking_common import TrackingResult


def _integer(value: int, name: str, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer.")
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"{minimum} to {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValueError(f"{name} must be {bounds}.")
    return int(value)


def _dictionary():
    return cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def generate_marker(marker_id: int = 0, size: int = 400, border: int = 40) -> np.ndarray:
    """Return a grayscale marker with a white margin of ``border`` pixels.

    ``size`` describes the square marker itself, including its black border.
    The complete image measures ``size + 2 * border`` pixels on each side.
    """
    marker_id = _integer(marker_id, "marker_id", 0, 49)
    size = _integer(size, "size", 6)
    border = _integer(border, "border", 1)
    marker = cv2.aruco.generateImageMarker(_dictionary(), marker_id, size)
    return cv2.copyMakeBorder(
        marker, border, border, border, border, cv2.BORDER_CONSTANT, value=255
    )


class ArucoTracker:
    def __init__(self, marker_id: int = 0):
        self.marker_id = _integer(marker_id, "marker_id", 0, 49)
        self.detector = cv2.aruco.ArucoDetector(_dictionary(), cv2.aruco.DetectorParameters())
        self.reset()

    def reset(self) -> None:
        self._seen = False

    def update(self, frame: np.ndarray) -> TrackingResult:
        """Detect the configured ID in a BGR frame; never reuse old corners."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        detected_ids = [] if ids is None else ids.flatten().tolist()
        metrics = {"marker_id": self.marker_id, "detected_ids": detected_ids}
        if self.marker_id in detected_ids:
            selected = np.asarray(corners[detected_ids.index(self.marker_id)], dtype=np.float32)
            selected = selected.reshape(4, 2).copy()
            self._seen = True
            return TrackingResult(
                status="tracking",
                detail=f"Marker {self.marker_id} detected; 2D anchor only.",
                corners=selected,
                points=selected.copy(),
                metrics=metrics,
            )
        return TrackingResult(
            status="lost" if self._seen else "searching",
            detail=f"Show marker {self.marker_id} attached to the dummy.",
            corners=None,
            points=None,
            metrics=metrics,
        )
