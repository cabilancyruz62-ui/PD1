"""Deterministic image tests using real OpenCV flow and transformation fitting."""

import importlib.util
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np


DESIGNS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGNS))
spec = importlib.util.spec_from_file_location(
    "optical_flow_tracker", DESIGNS / "design-3-optical-flow" / "tracker.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
OpticalFlowTracker = module.OpticalFlowTracker


class OpticalFlowTests(unittest.TestCase):
    ROI = (60, 45, 140, 130)

    def setUp(self):
        cv2.setRNGSeed(7)
        rng = np.random.default_rng(7)
        image = np.full((240, 320), 40, np.uint8)
        texture = rng.integers(25, 231, (130, 140), dtype=np.uint8)
        image[45:175, 60:200] = cv2.GaussianBlur(texture, (3, 3), 0)
        self.frame = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        self.tracker = OpticalFlowTracker()

    def test_static_frame_remains_tracked_with_near_zero_motion(self):
        initial = self.tracker.initialize(self.frame, self.ROI)
        self.assertTrue(initial.tracked)
        for _ in range(4):
            result = self.tracker.update(self.frame)
            self.assertTrue(result.tracked)
            np.testing.assert_allclose(result.corners, initial.corners, atol=0.25)

    def test_small_translation_updates_selected_region(self):
        initial = self.tracker.initialize(self.frame, self.ROI)
        translated = cv2.warpAffine(
            self.frame, np.float32([[1, 0, 6], [0, 1, 4]]), (320, 240),
            borderValue=(40, 40, 40),
        )
        result = self.tracker.update(translated)
        self.assertTrue(result.tracked, result.detail)
        np.testing.assert_allclose(result.corners, initial.corners + [6, 4], atol=0.75)

    def test_blank_selection_needs_features(self):
        blank = np.full_like(self.frame, 40)
        result = self.tracker.initialize(blank, self.ROI)
        self.assertEqual(result.status, "needs_selection")
        self.assertFalse(result.tracked)
        self.assertIsNone(result.corners)

    def test_blank_occlusion_loses_target_until_reinitialized(self):
        self.tracker.initialize(self.frame, self.ROI)
        result = self.tracker.update(np.full_like(self.frame, 40))
        self.assertEqual(result.status, "lost")
        self.assertIsNone(result.corners)
        self.assertEqual(self.tracker.update(self.frame).status, "lost")
        self.assertTrue(self.tracker.initialize(self.frame, self.ROI).tracked)

    def test_changed_dimensions_lose_target(self):
        self.tracker.initialize(self.frame, self.ROI)
        changed = cv2.resize(self.frame, (320, 260))
        self.assertEqual(self.tracker.update(changed).status, "lost")
        self.assertEqual(self.tracker.update(self.frame).status, "lost")

    def test_reset_requires_new_selection(self):
        self.tracker.initialize(self.frame, self.ROI)
        self.tracker.reset()
        self.assertEqual(self.tracker.update(self.frame).status, "needs_selection")


if __name__ == "__main__":
    unittest.main()
