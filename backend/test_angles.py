import math
import unittest
from angles import surface_angle, AnglePipeline


IDENTITY = [0, 0, 0, 1]
CALIBRATION = {"syringe_axis_sensor": [1, 0, 0], "surface_normal_sensor": [0, 0, 1], "syringe_reference_rotation_xyzw": IDENTITY, "dummy_reference_rotation_xyzw": IDENTITY}


def pitch(degrees):
    half = math.radians(degrees)/2
    return [0, math.sin(half), 0, math.cos(half)]


class AngleTests(unittest.TestCase):
    def test_plane_angle_is_not_angle_to_normal(self):
        for degrees in (0, 15, 22, 30, 90):
            self.assertAlmostEqual(surface_angle(pitch(-degrees), IDENTITY, CALIBRATION), degrees)

    def test_both_sensor_frames_and_mounting_axes_are_applied(self):
        self.assertAlmostEqual(surface_angle(pitch(18), pitch(40), CALIBRATION), 22)
        mount = {**CALIBRATION, "syringe_axis_sensor": [0, 1, 0]}
        half = math.radians(22)/2
        self.assertAlmostEqual(surface_angle([math.sin(half), 0, 0, math.cos(half)], IDENTITY, mount), 22)
        aligned = {**CALIBRATION, "syringe_reference_rotation_xyzw": pitch(10)}
        self.assertAlmostEqual(surface_angle(pitch(-32), IDENTITY, aligned), 22)

    def test_invalid_geometry_is_not_accepted(self):
        with self.assertRaises(ValueError):
            surface_angle([0,0,0,0], IDENTITY, CALIBRATION)
        with self.assertRaises(ValueError):
            surface_angle(IDENTITY, IDENTITY, {**CALIBRATION, "surface_normal_sensor": [0,0,0]})

    def test_smoothing_resets_for_stage_calibration_and_expiry(self):
        self.now = 100
        config = {"angle_smoothing_alpha": .35, "hardware_timeout_seconds": 5, "angle_min_deg": 15, "angle_max_deg": 30, "angle_calibrations": {"registered": CALIBRATION}}
        pipeline = AnglePipeline(config, lambda: self.now)
        def sample(value, stage="a", calibration="test"):
            return pipeline.ingest({"angle_deg": value, "calibrated": True, "calibration_id": calibration}, "esp32", stage)
        self.assertEqual(sample(22)["angle_deg"], 22)
        # Smoothing cannot conceal an out-of-range latest raw sample.
        sample(10)
        self.assertFalse(pipeline.snapshot("esp32", "a", True)["within_target"])
        self.assertEqual(sample(30, stage="b")["angle_deg"], 30)
        self.assertIsNone(pipeline.snapshot("esp32", "a", True))
        self.assertEqual(sample(20, stage="b", calibration="changed")["angle_deg"], 20)
        self.now += 6
        self.assertFalse(pipeline.snapshot("esp32", "b", True)["fresh"])
        self.assertEqual(sample(25, stage="b", calibration="changed")["angle_deg"], 25)

    def test_paired_orientations_require_registered_calibration(self):
        config = {"angle_smoothing_alpha": .35, "hardware_timeout_seconds": 5, "angle_min_deg": 15, "angle_max_deg": 30, "angle_calibrations": {"registered": CALIBRATION}}
        pipeline = AnglePipeline(config, lambda: 100)
        data = {"syringe_quaternion": pitch(-22), "dummy_quaternion": IDENTITY, "calibration_id": "registered", "calibrated": True}
        measured = pipeline.ingest(data, "esp32", "a")
        self.assertEqual(measured["angle_deg"], 22)
        self.assertEqual(measured["method"], "paired_quaternion_surface_angle")
        invalid = pipeline.ingest({**data, "calibration_id": "missing", "angle_deg": 22}, "esp32", "a")
        self.assertFalse(invalid["calibrated"])
        self.assertIsNone(invalid["angle_deg"])


if __name__ == "__main__":
    unittest.main()
