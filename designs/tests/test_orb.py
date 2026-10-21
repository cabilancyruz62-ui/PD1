"""Exercise matching and failure behavior on deterministic synthetic images."""

import importlib.util
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

DESIGNS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGNS))
spec = importlib.util.spec_from_file_location("orb_tracker", DESIGNS / "design-2-orb-ransac/tracker.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
OrbTracker = module.OrbTracker


def textured_patch(seed=23):
    rng = np.random.default_rng(seed)
    image = np.full((280, 360, 3), 230, dtype=np.uint8)
    for _ in range(180):
        x, y = rng.integers([12, 12], [348, 268])
        radius = int(rng.integers(2, 8))
        color = tuple(int(value) for value in rng.integers(0, 210, 3))
        cv2.circle(image, (int(x), int(y)), radius, color, -1)
    for row, text in enumerate(("PUP VITALS 42", "REFERENCE ABC", "DUMMY LIMB 7")):
        cv2.putText(image, text, (20, 65 + row * 75), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 0, 0), 2, cv2.LINE_AA)
    return image


class OrbTrackerTests(unittest.TestCase):
    def setUp(self):
        cv2.setRNGSeed(5)
        self.reference = textured_patch()
        self.expected = np.float32([[140, 90], [475, 72], [500, 365], [120, 385]])
        source = np.float32([[0, 0], [359, 0], [359, 279], [0, 279]])
        transform = cv2.getPerspectiveTransform(source, self.expected)
        self.frame = cv2.warpPerspective(self.reference, transform, (640, 480))

    def test_matches_perspective_reference(self):
        result = OrbTracker(self.reference).update(self.frame)
        self.assertTrue(result.tracked, result.detail)
        self.assertLess(float(np.linalg.norm(result.corners - self.expected, axis=1).max()), 4)
        self.assertGreaterEqual(result.metrics["inliers"], 10)

    def test_loss_clears_overlay_and_reference_can_reacquire(self):
        tracker = OrbTracker(self.reference)
        self.assertTrue(tracker.update(self.frame).tracked)
        lost = tracker.update(np.zeros_like(self.frame))
        self.assertEqual(lost.status, "lost")
        self.assertIsNone(lost.corners)
        self.assertIsNone(lost.points)
        self.assertTrue(tracker.update(self.frame).tracked)

    def test_unrelated_texture_is_not_a_match(self):
        unrelated = np.random.default_rng(109).integers(0, 256, (480, 640, 3), dtype=np.uint8)
        result = OrbTracker(self.reference).update(unrelated)
        self.assertFalse(result.tracked)
        self.assertIsNone(result.corners)

    def test_live_roi_and_reset_preserve_reference(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:380, 150:510] = self.reference
        tracker = OrbTracker()
        self.assertEqual(tracker.update(frame).status, "needs_selection")
        self.assertTrue(tracker.initialize(frame, (150, 100, 360, 280)).tracked)
        tracker.reset()
        self.assertIsNone(tracker.update(np.zeros_like(frame)).corners)
        self.assertTrue(tracker.update(frame).tracked)

    def test_rejects_unusable_reference_and_invalid_roi(self):
        for reference in (np.zeros((200, 200, 3), np.uint8), np.zeros((1, 1), np.uint8)):
            with self.assertRaises(ValueError):
                OrbTracker(reference)
        with self.assertRaises(ValueError):
            OrbTracker().initialize(self.frame, (-1, 0, 100, 100))


if __name__ == "__main__":
    unittest.main()
