"""Deterministic planar fixtures; these do not test physical-dummy recognition.

Frames are generated lazily. Only one visible startup frame is retained so an
optical-flow tracker can initialize before an absence or low-light sequence.
"""

import math

import cv2
import numpy as np


def conditions():
    """Return the common scenarios, in the order used by benchmark reports."""
    return ("stationary", "camera_motion", "dim_light", "occlusion_recovery",
            "target_absent")


def _texture(seed):
    rng = np.random.default_rng(seed)
    image = np.full((240, 320, 3), 225, dtype=np.uint8)
    for _ in range(150):
        x, y = (int(value) for value in rng.integers([12, 12], [308, 228]))
        color = tuple(int(value) for value in rng.integers(0, 190, 3))
        cv2.circle(image, (x, y), int(rng.integers(2, 8)), color, -1)
    for row, text in enumerate(("PUP VITALS 42", "PLANAR TARGET", "SYNTHETIC 7")):
        cv2.putText(image, text, (14, 53 + row * 74), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, (15, 15, 15), 2, cv2.LINE_AA)
    return image


class SyntheticScene:
    """Provide known target corners for synthetic 2D tracking measurements.

    The ORB and flow target is the same textured planar patch, not a photograph
    of a dummy. ArUco uses marker 0 from DICT_4X4_50. A target being present in
    these scenes cannot establish that any method recognizes a real dummy.
    """

    def __init__(self, design, condition, width=1280, height=720, seed=42):
        if design not in ("aruco", "orb", "optical-flow"):
            raise ValueError("Unknown design: " + str(design))
        if condition not in conditions():
            raise ValueError("Unknown condition: " + str(condition))
        if (isinstance(width, bool) or isinstance(height, bool)
                or not isinstance(width, int) or not isinstance(height, int)
                or width < 480 or height < 360):
            raise ValueError("Frame dimensions must be integers of at least 480x360.")
        self.design, self.condition = design, condition
        self.width, self.height = width, height
        self.reference = None if design == "aruco" else _texture(seed)
        if design == "aruco":
            marker_size, margin = 240, 24
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            marker = cv2.aruco.generateImageMarker(dictionary, 0, marker_size)
            marker = cv2.copyMakeBorder(marker, margin, margin, margin, margin,
                                        cv2.BORDER_CONSTANT, value=255)
            self._patch = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
            local_corners = np.float32([
                [margin, margin], [margin + marker_size - 1, margin],
                [margin + marker_size - 1, margin + marker_size - 1],
                [margin, margin + marker_size - 1],
            ])
        else:
            self._patch = self.reference
            local_corners = np.float32([[0, 0], [319, 0], [319, 239], [0, 239]])
        patch_height, patch_width = self._patch.shape[:2]
        self._x = (width - patch_width) // 2
        self._y = (height - patch_height) // 2
        self.roi = (self._x, self._y, patch_width, patch_height)
        self.expected_initial_corners = local_corners + np.float32([self._x, self._y])
        self.initial_frame = self._background()
        self.initial_frame[self._y:self._y + patch_height,
                           self._x:self._x + patch_width] = self._patch

    def _background(self):
        # A uniform background ensures features belong to the intended target.
        return np.full((self.height, self.width, 3), 105, dtype=np.uint8)

    def frame(self, index, total):
        """Return BGR pixels, ordered target corners (or None), and visibility.

        Startup initialization is deliberately outside this sequence. Complete
        middle-third occlusion tests loss and subsequent reacquisition without
        moving hand features or misleading substitute geometry.
        """
        if (isinstance(index, bool) or isinstance(total, bool)
                or not isinstance(index, int) or not isinstance(total, int)
                or total <= 0 or index < 0 or index >= total):
            raise ValueError("Use an integer total > 0 and 0 <= index < total.")
        hidden = self.condition == "target_absent" or (
            self.condition == "occlusion_recovery"
            and total // 3 <= index < (2 * total) // 3)
        if hidden:
            return self._background(), None, False

        corners = self.expected_initial_corners.copy()
        if self.condition == "camera_motion":
            phase = 2 * math.pi * index / max(total - 1, 1)
            # Small frame-to-frame changes remain within LK's supported motion.
            transform = cv2.getRotationMatrix2D(
                ((self.width - 1) / 2, (self.height - 1) / 2),
                4 * math.sin(phase), 1 + 0.025 * math.sin(phase / 2))
            transform[:, 2] += [40 * math.sin(phase), 24 * math.sin(phase * 2)]
            frame = cv2.warpAffine(self.initial_frame, transform,
                                   (self.width, self.height),
                                   flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(105, 105, 105))
            corners = cv2.transform(corners[None], transform)[0]
        elif self.condition == "dim_light":
            frame = cv2.convertScaleAbs(self.initial_frame, alpha=0.42, beta=10)
        else:
            frame = self.initial_frame.copy()
        return frame, corners.astype(np.float32), True
