"""Exercise actual marker decoding using deterministic camera-free images."""

import importlib.util
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np


DESIGNS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGNS))
SPEC = importlib.util.spec_from_file_location("aruco_tracker", DESIGNS / "design-1-aruco" / "tracker.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ArucoTracker = MODULE.ArucoTracker
generate_marker = MODULE.generate_marker


def marker_frame(marker_id=0):
    frame = np.full((540, 720, 3), 255, dtype=np.uint8)
    marker = generate_marker(marker_id, size=180, border=30)
    frame[120:360, 100:340] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return frame


class ArucoTests(unittest.TestCase):
    def test_detects_expected_marker_and_corners(self):
        result = ArucoTracker(marker_id=0).update(marker_frame(0))
        self.assertTrue(result.tracked)
        self.assertEqual(result.status, "tracking")
        self.assertEqual(result.metrics["detected_ids"], [0])
        self.assertEqual(result.corners.dtype, np.float32)
        np.testing.assert_allclose(
            result.corners,
            np.array([[130, 150], [309, 150], [309, 329], [130, 329]]),
            atol=2,
        )

    def test_wrong_id_does_not_enable_anchor(self):
        result = ArucoTracker(marker_id=0).update(marker_frame(1))
        self.assertEqual(result.status, "searching")
        self.assertEqual(result.metrics["detected_ids"], [1])
        self.assertFalse(result.tracked)
        self.assertIsNone(result.corners)

    def test_loss_has_no_stale_corners_and_can_reacquire(self):
        tracker = ArucoTracker()
        self.assertTrue(tracker.update(marker_frame()).tracked)
        for frame in (np.full((540, 720, 3), 255, dtype=np.uint8), marker_frame(1)):
            result = tracker.update(frame)
            self.assertEqual(result.status, "lost")
            self.assertFalse(result.tracked)
            self.assertIsNone(result.corners)
            self.assertIsNone(result.points)
        self.assertTrue(tracker.update(marker_frame()).tracked)
        tracker.reset()
        self.assertEqual(tracker.update(marker_frame(1)).status, "searching")

    def test_marker_generation_includes_white_margin(self):
        marker = generate_marker(marker_id=49, size=120, border=20)
        self.assertEqual(marker.shape, (160, 160))
        self.assertEqual(marker.dtype, np.uint8)
        self.assertTrue(np.all(marker[:20] == 255))
        self.assertTrue(np.all(marker[-20:] == 255))
        self.assertTrue(np.all(marker[:, :20] == 255))
        self.assertTrue(np.all(marker[:, -20:] == 255))

    def test_invalid_marker_ids_have_friendly_errors(self):
        for marker_id in (-1, 50, 1.5, "0", True):
            with self.subTest(marker_id=marker_id):
                with self.assertRaisesRegex(ValueError, "marker_id"):
                    ArucoTracker(marker_id)
                with self.assertRaisesRegex(ValueError, "marker_id"):
                    generate_marker(marker_id)

    def test_invalid_marker_dimensions_have_friendly_errors(self):
        for size in (0, 5, 120.5, True):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "size"):
                generate_marker(size=size)
        for border in (-1, 0, 20.5, True):
            with self.subTest(border=border), self.assertRaisesRegex(ValueError, "border"):
                generate_marker(border=border)


if __name__ == "__main__":
    unittest.main()
