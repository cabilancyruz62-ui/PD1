"""Planar reference tracking with ORB descriptors and a RANSAC homography."""

import cv2
import numpy as np

from tracking_common import TrackingResult, valid_quad


class ReferenceSelectionError(ValueError):
    """Expose reference quality without weakening the matching checks."""
    def __init__(self, detail, metrics):
        super().__init__(detail)
        self.metrics = metrics


class OrbTracker:
    """Match a textured reference patch; this is not a trained dummy detector."""

    def __init__(self, reference: np.ndarray | None = None):
        self.orb = cv2.ORB_create(nfeatures=1800, edgeThreshold=15, fastThreshold=10)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.reference = None
        self.reference_points = None
        self.descriptors = None
        self._was_tracking = False
        if reference is not None:
            self._set_reference(reference)

    @staticmethod
    def _gray(frame):
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            raise ValueError("Provide a nonempty camera frame or reference image.")
        if frame.dtype != np.uint8:
            raise ValueError("Use an 8-bit image for ORB tracking.")
        if frame.ndim == 2:
            return frame
        if frame.ndim == 3 and frame.shape[2] == 3:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        raise ValueError("Use a grayscale or three-channel BGR image.")

    def _set_reference(self, reference):
        gray = self._gray(reference).copy()
        if min(gray.shape) < 48:
            raise ValueError("Choose a larger reference region (at least 48 pixels per side).")
        keypoints, descriptors = self.orb.detectAndCompute(gray, None)
        metrics = {"reference_features": len(keypoints), "required_reference_features": 24}
        if descriptors is None or len(keypoints) < 24:
            raise ReferenceSelectionError("The reference has too few features. Choose a larger, textured region.", metrics)
        points = np.float32([point.pt for point in keypoints])
        coverage = self._coverage(points, gray.shape)
        metrics.update(reference_coverage=round(coverage, 3), required_reference_coverage=0.08)
        if coverage < 0.08:
            raise ReferenceSelectionError("Reference features are too clustered. Include texture across the region.", metrics)
        self.reference = gray
        self.reference_points = points
        self.descriptors = descriptors
        self.reset()

    @staticmethod
    def _coverage(points, shape):
        if len(points) < 3:
            return 0.0
        height, width = shape[:2]
        return float(cv2.contourArea(cv2.convexHull(points))) / (height * width)

    def reset(self):
        """Keep the reference but discard tracking history and any previous transform."""
        self._was_tracking = False

    def initialize(self, frame, roi):
        """Capture the operator-selected (x, y, width, height) reference patch."""
        self._gray(frame)
        x, y, width, height = map(int, roi)
        if (x < 0 or y < 0 or width <= 0 or height <= 0
                or x + width > frame.shape[1] or y + height > frame.shape[0]):
            raise ValueError("Select a nonempty region entirely inside the camera image.")
        self._set_reference(frame[y:y + height, x:x + width])
        return self.update(frame)

    def _missing(self, detail, metrics):
        return TrackingResult(
            status="lost" if self._was_tracking else "searching",
            detail=detail, metrics=metrics,
        )

    def update(self, frame):
        if self.reference is None:
            return TrackingResult(
                status="needs_selection",
                detail="Press s to select a textured reference region on the dummy.",
            )
        gray = self._gray(frame)
        keypoints, descriptors = self.orb.detectAndCompute(gray, None)
        metrics = {"keypoints": len(keypoints), "matches": 0, "inliers": 0,
                   "reference_features": len(self.reference_points), "required_reference_features": 24}
        if descriptors is None or len(keypoints) < 12:
            return self._missing("Too few visible features; show the reference region.", metrics)

        pairs = self.matcher.knnMatch(self.descriptors, descriptors, k=2)
        candidates = [pair[0] for pair in pairs
                      if len(pair) == 2 and pair[0].distance < 0.72 * pair[1].distance]
        # A scene feature must not explain several reference features.
        matches, used_train = [], set()
        for match in sorted(candidates, key=lambda item: item.distance):
            if match.trainIdx not in used_train:
                matches.append(match)
                used_train.add(match.trainIdx)
        metrics["matches"] = len(matches)
        if len(matches) < 12:
            return self._missing("Not enough reliable matches to the reference.", metrics)

        source = np.float32([self.reference_points[m.queryIdx] for m in matches])
        target = np.float32([keypoints[m.trainIdx].pt for m in matches])
        homography, mask = cv2.findHomography(source, target, cv2.RANSAC, 3.0)
        if homography is None or mask is None or not np.isfinite(homography).all():
            return self._missing("Could not estimate a stable planar alignment.", metrics)
        inliers = mask.ravel().astype(bool)
        count = int(inliers.sum())
        coverage = self._coverage(source[inliers], self.reference.shape)
        metrics.update(inliers=count, inlier_ratio=count / len(matches),
                       reference_coverage=round(coverage, 3))
        spread = np.ptp(source[inliers], axis=0) if count else np.zeros(2)
        height, width = self.reference.shape
        if (count < 10 or count / len(matches) < 0.5 or coverage < 0.08
                or spread[0] < width * 0.25 or spread[1] < height * 0.25):
            return self._missing("Matches do not cover enough of the reference region.", metrics)

        reference_corners = np.float32([[0, 0], [width - 1, 0],
                                        [width - 1, height - 1], [0, height - 1]])
        # Reject homographies whose projective horizon crosses the reference.
        homogeneous = np.column_stack((reference_corners, np.ones(4))) @ homography.T
        divisors = homogeneous[:, 2]
        if np.any(np.abs(divisors) < 1e-6) or np.any(divisors * divisors[0] <= 0):
            return self._missing("Rejected an unstable perspective transform.", metrics)
        corners = cv2.perspectiveTransform(reference_corners[None], homography)[0]
        signed_area = cv2.contourArea(corners, oriented=True)
        edges = np.linalg.norm(np.roll(corners, -1, axis=0) - corners, axis=1)
        if (not valid_quad(corners, frame.shape) or signed_area <= 0
                or edges.min() < 12 or edges.max() / edges.min() > 8):
            return self._missing("Reference geometry is outside the usable camera view.", metrics)

        self._was_tracking = True
        return TrackingResult(
            status="tracking", detail="Planar reference matched.",
            corners=corners.astype(np.float32), points=target[inliers], metrics=metrics,
        )
