"""Per-browser OpenCV tracking. Frames are processed in memory, never saved."""
from functools import lru_cache
import importlib.util
import math
from pathlib import Path
import sys
import time

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal


class TrackingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["configure"]
    design: Literal["aruco", "orb", "optical-flow"]
    marker_id: int = Field(default=0, strict=True, ge=0, le=49)
    roi: tuple[float, float, float, float] | None = None

    @field_validator("roi")
    @classmethod
    def valid_roi(cls, roi):
        if roi is not None:
            x, y, width, height = roi
            if (not all(math.isfinite(value) for value in roi) or min(x, y) < 0
                    or min(width, height) <= 0 or x + width > 1 or y + height > 1):
                raise ValueError("Select a region entirely inside the camera image.")
        return roi


@lru_cache(maxsize=3)
def design_module(design):
    # Reuse the experiments' actual implementations, with no second webcam.
    directory = Path(__file__).resolve().parents[1] / "designs"
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("pupvitals_design_runner", directory / "run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner.load_design(design)


class TrackingEngine:
    def __init__(self, config):
        import cv2
        import numpy as np
        module = design_module(config.design)
        from tracking_common import valid_quad
        self.cv2, self.np, self.valid_quad = cv2, np, valid_quad
        self.config = config
        self.tracker = (module.ArucoTracker(config.marker_id) if config.design == "aruco"
                        else module.OrbTracker() if config.design == "orb"
                        else module.OpticalFlowTracker())
        self.pending_roi = config.roi if config.design != "aruco" else None
        self.needs_selection = config.design != "aruco" and self.pending_roi is None
        self.shape = None

    def ready(self):
        return {"type": "ready", "design": self.config.design,
                "status": "needs_selection" if self.needs_selection else "searching",
                "detail": "Select a region on the original pad." if self.needs_selection
                else f"Show marker {self.config.marker_id}." if self.config.design == "aruco"
                else "Initializing selected pad region."}

    def process(self, jpeg):
        started = time.perf_counter()
        if not jpeg or len(jpeg) > 1_000_000 or not jpeg.startswith(b"\xff\xd8"):
            raise ValueError("Send one JPEG frame smaller than 1 MB.")
        frame = self.cv2.imdecode(self.np.frombuffer(jpeg, self.np.uint8), self.cv2.IMREAD_COLOR)
        if frame is None or min(frame.shape[:2]) < 32 or max(frame.shape[:2]) > 960:
            raise ValueError("Use a readable camera frame with sides between 32 and 960 pixels.")
        height, width = frame.shape[:2]
        if self.shape is not None and self.shape != frame.shape[:2] and self.config.design != "aruco":
            self.tracker.reset()
            self.pending_roi = None
            self.needs_selection = True
        self.shape = frame.shape[:2]
        if self.needs_selection:
            return self._selection_result(width, height, "Select the pad again to initialize tracking.")
        if self.pending_roi is not None:
            x, y, w, h = self.pending_roi
            x0, y0 = round(x * width), round(y * height)
            x1, y1 = min(width, round((x + w) * width)), min(height, round((y + h) * height))
            self.pending_roi = None
            try:
                result = self.tracker.initialize(frame, (x0, y0, x1 - x0, y1 - y0))
            except ValueError as error:
                self.needs_selection = True
                metrics = getattr(error, 'metrics', {})
                detail = str(error)
                if 'reference_features' in metrics:
                    if metrics['reference_features'] < metrics['required_reference_features']:
                        detail = 'Too few features on this pad region. Try a closer, sharply focused view of existing pad details.'
                    else:
                        detail = 'Natural features are too clustered in this selection. Include existing details spread across the pad region.'
                return self._selection_result(width, height, detail, metrics)
        else:
            result = self.tracker.update(frame)
        self.needs_selection = result.status == "needs_selection"
        corners = result.corners if result.tracked and self.valid_quad(result.corners, frame.shape) else None
        status = result.status if corners is not None or not result.tracked else "searching"
        return {"type": "tracking_result", "design": self.config.design, "status": status,
                "detail": result.detail, "corners": None if corners is None else corners.tolist(),
                "frame": {"width": width, "height": height}, "metrics": result.metrics,
                "processing_ms": round((time.perf_counter() - started) * 1000, 2)}

    def _selection_result(self, width, height, detail, metrics=None):
        return {"type": "tracking_result", "design": self.config.design, "status": "needs_selection",
                "detail": detail, "corners": None, "frame": {"width": width, "height": height},
                "metrics": metrics or {}, "processing_ms": 0}
