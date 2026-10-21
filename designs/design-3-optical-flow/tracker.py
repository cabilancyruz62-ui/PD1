"""Manually initialized sparse optical flow; it does not recognize a dummy."""

import cv2
import numpy as np

from tracking_common import TrackingResult, valid_quad


class OpticalFlowTracker:
    """Follow selected features with LK and a robust 2D similarity transform."""

    MIN_POINTS = 10

    def __init__(self):
        self.reset()

    def reset(self):
        self._gray = None
        self._points = None
        self._corners = None
        self._shape = None
        self._lost = False

    def initialize(self, frame, roi):
        """Select a textured region in a native-resolution BGR camera frame."""
        self.reset()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        x, y, w, h = (int(value) for value in roi)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
        if x1 - x0 < 12 or y1 - y0 < 12:
            return TrackingResult("needs_selection", "Select a larger textured region.")

        corners = np.float32(
            [[x0, y0], [x1 - 1, y0], [x1 - 1, y1 - 1], [x0, y1 - 1]]
        )
        if not valid_quad(corners, frame.shape):
            return TrackingResult("needs_selection", "Selection is outside the camera view.")
        mask = np.zeros_like(gray)
        # Leave a margin so selected points belong to the surface, not its edge.
        mask[y0 + 4:y1 - 4, x0 + 4:x1 - 4] = 255
        points = cv2.goodFeaturesToTrack(
            gray, maxCorners=200, qualityLevel=0.02, minDistance=5,
            mask=mask, blockSize=7,
        )
        count = 0 if points is None else len(points)
        if count < self.MIN_POINTS:
            return TrackingResult(
                "needs_selection", "Too few features; select a more textured region.",
                metrics={"features": count},
            )
        self._gray, self._points = gray, points
        self._corners, self._shape = corners, gray.shape
        return self._result("Selection initialized; follow the selected surface.")

    def update(self, frame):
        if self._lost:
            return TrackingResult("lost", "Tracking lost. Press s to select the target again.")
        if self._gray is None:
            return TrackingResult("needs_selection", "Press s to select a textured target region.")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if gray.shape != self._shape:
            return self._lose("Camera dimensions changed. Select the target again.")

        lk_options = dict(
            winSize=(21, 21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
            minEigThreshold=1e-4,
        )
        forward, status, errors = cv2.calcOpticalFlowPyrLK(
            self._gray, gray, self._points, None, **lk_options
        )
        if forward is None or status is None or errors is None:
            return self._lose("Target features could not be followed.")
        backward, back_status, _ = cv2.calcOpticalFlowPyrLK(
            gray, self._gray, forward, None, **lk_options
        )
        if backward is None or back_status is None:
            return self._lose("Target features failed the consistency check.")

        old, new = self._points.reshape(-1, 2), forward.reshape(-1, 2)
        fb_error = np.linalg.norm(old - backward.reshape(-1, 2), axis=1)
        height, width = gray.shape
        good = (
            (status.ravel() == 1) & (back_status.ravel() == 1)
            & np.isfinite(new).all(axis=1) & np.isfinite(fb_error)
            & (fb_error <= 1.5) & (errors.ravel() <= 25)
            & (new[:, 0] >= 0) & (new[:, 0] < width)
            & (new[:, 1] >= 0) & (new[:, 1] < height)
        )
        if int(good.sum()) < self.MIN_POINTS:
            return self._lose("Too few consistent features; the target may be covered.")

        old, new = old[good], new[good]
        transform, mask = cv2.estimateAffinePartial2D(
            old, new, method=cv2.RANSAC, ransacReprojThreshold=2.5,
            maxIters=2000, confidence=0.99, refineIters=10,
        )
        if transform is None or mask is None or not np.isfinite(transform).all():
            return self._lose("A stable surface transformation could not be estimated.")
        inliers = mask.ravel().astype(bool)
        count, ratio = int(inliers.sum()), float(inliers.mean())
        if count < self.MIN_POINTS or ratio < 0.6:
            return self._lose("Features no longer agree on the target movement.")

        scale = float(np.linalg.norm(transform[:, 0]))
        corners = cv2.transform(self._corners[None, :, :], transform)[0]
        movement = np.linalg.norm(corners - self._corners, axis=1).max()
        if (not 0.8 <= scale <= 1.25 or movement > max(width, height) * 0.3
                or not valid_quad(corners, frame.shape)):
            return self._lose("Target movement or geometry is outside the supported range.")

        # Keep only the original surviving features. Automatic reseeding could
        # attach to a hand or background after the selected object disappears.
        self._gray = gray
        self._points = new[inliers].reshape(-1, 1, 2).astype(np.float32)
        self._corners = corners.astype(np.float32)
        return self._result(
            "Following selected image features; target identity is not verified.",
            {"inliers": count, "inlier_ratio": ratio,
             "fb_error_px": float(np.median(fb_error[good][inliers]))},
        )

    def _result(self, detail, metrics=None):
        values = {"features": len(self._points)}
        values.update(metrics or {})
        return TrackingResult(
            "tracking", detail, corners=self._corners.copy(),
            points=self._points.reshape(-1, 2).copy(), metrics=values,
        )

    def _lose(self, detail):
        self._gray = self._points = self._corners = None
        self._lost = True
        return TrackingResult("lost", detail)
