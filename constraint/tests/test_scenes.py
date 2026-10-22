"""Verify synthetic fixture geometry and lifecycle independently of trackers."""

import math
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scenes import SyntheticScene, conditions


class SyntheticSceneTests(unittest.TestCase):
    def test_default_dimensions_and_deterministic_texture(self):
        for design in ("aruco", "orb", "optical-flow"):
            first = SyntheticScene(design, "stationary")
            second = SyntheticScene(design, "stationary")
            frame, corners, visible = first.frame(0, 9)
            self.assertEqual(frame.shape, (720, 1280, 3))
            self.assertEqual(frame.dtype, np.uint8)
            self.assertTrue(visible)
            np.testing.assert_array_equal(frame, second.frame(0, 9)[0])
            np.testing.assert_array_equal(corners, first.expected_initial_corners)
            # Caller drawing must not corrupt subsequent frames or ground truth.
            frame[:] = 0
            corners[:] = 0
            self.assertGreater(first.frame(0, 9)[0].mean(), 0)
            self.assertGreater(first.frame(0, 9)[1].min(), 0)

    def test_orb_and_flow_have_identical_non_marker_texture(self):
        orb = SyntheticScene("orb", "stationary")
        flow = SyntheticScene("optical-flow", "stationary")
        np.testing.assert_array_equal(orb.reference, flow.reference)
        self.assertEqual(orb.reference.shape, (240, 320, 3))
        keypoints, _ = cv2.ORB_create().detectAndCompute(orb.reference, None)
        self.assertGreater(len(keypoints), 24)
        self.assertFalse(np.array_equal(orb.reference,
                                       SyntheticScene("orb", "stationary", seed=9).reference))

    def test_aruco_ground_truth_excludes_white_margin(self):
        scene = SyntheticScene("aruco", "stationary")
        detector = cv2.aruco.ArucoDetector(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
        corners, ids, _ = detector.detectMarkers(scene.initial_frame)
        self.assertEqual(ids.ravel().tolist(), [0])
        np.testing.assert_allclose(corners[0].reshape(4, 2),
                                   scene.expected_initial_corners, atol=0.1)
        self.assertEqual(scene.roi[2:], (288, 288))

    def test_absence_and_occlusion_keep_visible_startup(self):
        for condition in ("target_absent", "occlusion_recovery"):
            scene = SyntheticScene("orb", condition)
            self.assertGreater(float(scene.initial_frame.std()), 0)
            for index in range(9):
                frame, corners, visible = scene.frame(index, 9)
                expected_visible = condition != "target_absent" and not 3 <= index < 6
                self.assertEqual(visible, expected_visible)
                if visible:
                    self.assertIsNotNone(corners)
                else:
                    self.assertIsNone(corners)
                    self.assertEqual(float(frame.std()), 0)

    def test_motion_corners_match_independent_similarity_projection(self):
        scene = SyntheticScene("orb", "camera_motion")
        _, corners, visible = scene.frame(3, 13)
        self.assertTrue(visible)
        # At phase pi/2: translation (+40, 0), rotation 4 degrees.
        angle = math.radians(4)
        scale = 1 + 0.025 * math.sin(math.pi / 4)
        rotation = scale * np.array([[math.cos(angle), math.sin(angle)],
                                     [-math.sin(angle), math.cos(angle)]])
        center = np.array([639.5, 359.5])
        expected = (scene.expected_initial_corners - center) @ rotation.T
        expected += center + np.array([40, 0])
        np.testing.assert_allclose(corners, expected, atol=0.0001)
        self.assertGreater(float(np.linalg.norm(corners - scene.expected_initial_corners)), 30)
        # Frame zero is the same view used during initialization.
        np.testing.assert_array_equal(scene.frame(0, 13)[0], scene.initial_frame)

    def test_dim_light_is_stable_and_preserves_geometry(self):
        scene = SyntheticScene("optical-flow", "dim_light")
        first, corners, visible = scene.frame(0, 9)
        self.assertTrue(visible)
        self.assertLess(first.mean(), scene.initial_frame.mean())
        self.assertGreater(float(first.std()), 10)
        np.testing.assert_array_equal(first, scene.frame(8, 9)[0])
        np.testing.assert_array_equal(corners, scene.expected_initial_corners)

    def test_invalid_inputs_fail_early(self):
        self.assertEqual(len(conditions()), 5)
        for args in (("unknown", "stationary"), ("orb", "unknown")):
            with self.assertRaises(ValueError):
                SyntheticScene(*args)
        scene = SyntheticScene("orb", "stationary")
        for index, total in ((-1, 3), (3, 3), (0, 0), (True, 3), (0.5, 3)):
            with self.assertRaises(ValueError):
                scene.frame(index, total)


if __name__ == "__main__":
    unittest.main()
