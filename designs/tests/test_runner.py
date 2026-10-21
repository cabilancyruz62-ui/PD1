"""Run the actual CLI against small videos without accessing a physical camera."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import cv2
import numpy as np

DESIGNS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGNS))
from run import load_design
from tracking_common import TrackingResult, draw_result, valid_quad


class RunnerTests(unittest.TestCase):
    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(DESIGNS / "run.py"), *map(str, arguments)],
            capture_output=True, text=True, timeout=30,
        )

    def test_marker_command_writes_a_decodable_image(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "marker with spaces.png"
            result = self.cli("--generate-marker", output, "--marker-id", 7)
            self.assertEqual(result.returncode, 0, result.stderr)
            image = cv2.imread(str(output))
            self.assertIsNotNone(image)
            self.assertTrue(load_design("aruco").ArucoTracker(7).update(image).tracked)

    def test_all_designs_process_video_and_target_loss(self):
        rng = np.random.default_rng(37)
        texture = rng.integers(0, 256, (240, 280, 3), dtype=np.uint8)
        texture = cv2.GaussianBlur(texture, (3, 3), 0)
        frame = np.full((480, 640, 3), 60, np.uint8)
        frame[120:360, 180:460] = texture
        blank = np.full_like(frame, 60)
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.png"
            self.assertTrue(cv2.imwrite(str(reference), texture))
            for mode in ("aruco", "orb-reference", "orb-roi", "optical-flow"):
                with self.subTest(mode=mode):
                    first = frame.copy()
                    if mode == "aruco":
                        marker = load_design("aruco").generate_marker(size=180, border=30)
                        first[120:360, 180:420] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
                    video = Path(directory) / f"{mode} trial.avi"
                    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (640, 480))
                    if not writer.isOpened():
                        writer.release()
                        self.skipTest("MJPG encoder unavailable in this OpenCV build")
                    try:
                        for image in (first, first, blank, first):
                            writer.write(image)
                    finally:
                        writer.release()
                    design = "orb" if mode.startswith("orb") else mode
                    extra = []
                    if mode == "orb-reference":
                        extra = ["--reference", reference]
                    elif mode != "aruco":
                        extra = ["--roi", 180, 120, 280, 240]
                    result = self.cli("--design", design, "--video", video, "--headless", *extra)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = 2 if design == "optical-flow" else 3
                    self.assertIn(f"Processed 4 frames; target tracked in {expected} frames.", result.stdout)

    def test_headless_flow_requires_selection_before_opening_camera(self):
        result = self.cli("--design", "optical-flow", "--headless")
        self.assertEqual(result.returncode, 2)
        self.assertIn("headless ORB/optical flow needs", result.stderr)

    def test_headless_flow_rejects_a_featureless_initial_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "blank.avi"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
            if not writer.isOpened():
                writer.release()
                self.skipTest("MJPG encoder unavailable in this OpenCV build")
            try:
                writer.write(np.full((120, 160, 3), 40, np.uint8))
            finally:
                writer.release()
            result = self.cli("--design", "optical-flow", "--video", video,
                              "--headless", "--roi", 20, 20, 60, 60)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Too few features", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_bad_reference_file_has_a_friendly_error(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "unreadable.png"
            reference.write_text("not an image", encoding="utf-8")
            result = self.cli("--design", "orb", "--reference", reference, "--headless")
            self.assertEqual(result.returncode, 1)
            self.assertIn("could not decode reference image", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


class OverlayTests(unittest.TestCase):
    def test_lost_result_does_not_draw_stale_target(self):
        frame = np.zeros((300, 400, 3), np.uint8)
        corners = np.float32([[100, 150], [250, 150], [250, 250], [100, 250]])
        tracked = draw_result(frame, TrackingResult("tracking", "test", corners), "test", 1)
        lost = draw_result(frame, TrackingResult("lost", "test", corners), "test", 1)
        self.assertTrue(tracked[150:251, 100:251].any())
        self.assertFalse(lost[150:251, 100:251].any())
        self.assertFalse(frame.any(), "Drawing must not change the tracker input")

    def test_invalid_geometry_is_rejected(self):
        shape = (300, 400, 3)
        invalid = [
            None,
            np.float32([[10, 10]] * 4),
            np.float32([[0, 0], [100, 100], [100, 0], [0, 100]]),
            np.float32([[0, 0], [500, 0], [500, 100], [0, 100]]),
            np.full((4, 2), np.nan, np.float32),
        ]
        for corners in invalid:
            self.assertFalse(valid_quad(corners, shape))


if __name__ == "__main__":
    unittest.main()
