"""Exercise the browser tracking protocol against a private real backend."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen

import cv2
import numpy as np
from websockets.sync.client import connect

from tracking import TrackingConfig, design_module


def jpeg(frame):
    ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError('JPEG encoder unavailable')
    return encoded.tobytes()


class TrackingTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='pupvitals-tracking-test-')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        env = {**os.environ, 'ASSESSMENT_DB_PATH': str(Path(cls.directory.name) / 'test.sqlite3')}
        cls.process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir',
            str(Path(__file__).parent), '--host', '127.0.0.1', '--port', str(cls.port),
            '--ws', 'websockets-sansio', '--log-level', 'warning'], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(80):
            try:
                with urlopen(cls.base + '/api/health', timeout=.3):
                    break
            except OSError:
                if cls.process.poll() is not None:
                    break
                time.sleep(.1)
        else:
            cls.process.terminate()
            raise RuntimeError('Private tracking backend did not start')
        if cls.process.poll() is not None:
            raise RuntimeError(cls.process.communicate()[0].decode(errors='replace'))

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill(); cls.process.communicate()
        cls.directory.cleanup()

    def socket(self):
        return connect(f'ws://127.0.0.1:{self.port}/api/ws/tracking', open_timeout=4)

    def configure(self, ws, design='aruco', **fields):
        ws.send(json.dumps({'type': 'configure', 'design': design, **fields}))
        return json.loads(ws.recv(timeout=10))

    def frame(self, ws, image):
        ws.send(jpeg(image))
        return json.loads(ws.recv(timeout=5))

    def marker(self, marker_id=0):
        image = np.full((480, 640, 3), 255, np.uint8)
        marker = design_module('aruco').generate_marker(marker_id, size=180, border=30)
        image[100:340, 180:420] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        return image

    def texture(self):
        # Synthetic test data only; no printed helper is required by the UI.
        rng = np.random.default_rng(71)
        patch = cv2.GaussianBlur(rng.integers(0, 256, (240, 280, 3), np.uint8), (3, 3), 0)
        image = np.full((480, 640, 3), 70, np.uint8)
        image[120:360, 180:460] = patch
        return image

    def test_aruco_stream_detects_loses_reacquires_and_ignores_wrong_id(self):
        with self.socket() as ws:
            self.assertEqual(self.configure(ws)['type'], 'ready')
            found = self.frame(ws, self.marker())
            self.assertEqual(found['status'], 'tracking')
            self.assertEqual(found['metrics']['detected_ids'], [0])
            self.assertEqual(found['frame'], {'width': 640, 'height': 480})
            np.testing.assert_allclose(found['corners'], [[210, 130], [389, 130], [389, 309], [210, 309]], atol=2)
            for image in (np.full((480, 640, 3), 255, np.uint8), self.marker(1)):
                lost = self.frame(ws, image)
                self.assertEqual(lost['status'], 'lost')
                self.assertIsNone(lost['corners'])
            self.assertEqual(self.frame(ws, self.marker())['status'], 'tracking')

    def test_orb_and_flow_use_selected_pixels_without_an_added_target_dependency(self):
        roi = [180 / 640, 120 / 480, 280 / 640, 240 / 480]
        for design in ('orb', 'optical-flow'):
            with self.subTest(design=design), self.socket() as ws:
                self.assertEqual(self.configure(ws, design, roi=roi)['type'], 'ready')
                image = self.texture()
                self.assertEqual(self.frame(ws, image)['status'], 'tracking')
                stationary = self.frame(ws, image)
                self.assertEqual(stationary['status'], 'tracking')
                moved = cv2.warpAffine(image, np.float32([[1, 0, 4], [0, 1, 3]]), (640, 480), borderValue=(70, 70, 70))
                self.assertEqual(self.frame(ws, moved)['status'], 'tracking')
                blank = np.full_like(image, 70)
                self.assertIsNone(self.frame(ws, blank)['corners'])
                again = self.frame(ws, image)
                self.assertEqual(again['status'], 'tracking' if design == 'orb' else 'lost')

    def test_selection_is_required_and_featureless_regions_are_reported(self):
        blank = np.full((480, 640, 3), 150, np.uint8)
        for design in ('orb', 'optical-flow'):
            with self.subTest(design=design), self.socket() as ws:
                self.assertEqual(self.configure(ws, design)['status'], 'needs_selection')
                self.assertEqual(self.frame(ws, blank)['status'], 'needs_selection')
            with self.socket() as ws:
                self.configure(ws, design, roi=[.2, .2, .5, .5])
                result = self.frame(ws, blank)
                self.assertEqual(result['status'], 'needs_selection')
                self.assertIsNone(result['corners'])
                if design == 'orb':
                    self.assertEqual(result['metrics']['reference_features'], 0)
                    self.assertEqual(result['metrics']['required_reference_features'], 24)

    def test_clustered_reference_reports_quality_without_allowing_a_false_anchor(self):
        image = np.full((480, 640, 3), 80, np.uint8)
        rng = np.random.default_rng(91)
        image[200:264, 280:344] = rng.integers(0, 256, (64, 64, 3), np.uint8)
        with self.socket() as ws:
            self.configure(ws, 'orb', roi=[180 / 640, 120 / 480, 280 / 640, 240 / 480])
            result = self.frame(ws, image)
            self.assertEqual(result['status'], 'needs_selection')
            self.assertIsNone(result['corners'])
            self.assertIn('too clustered', result['detail'])
            self.assertGreaterEqual(result['metrics']['reference_features'], 24)
            self.assertLess(result['metrics']['reference_coverage'], .08)

    def test_connections_keep_independent_marker_state(self):
        with self.socket() as first, self.socket() as second:
            self.configure(first, marker_id=0)
            self.configure(second, marker_id=1)
            self.assertEqual(self.frame(first, self.marker(0))['status'], 'tracking')
            self.assertEqual(self.frame(second, self.marker(0))['status'], 'searching')
            self.assertEqual(self.frame(second, self.marker(1))['status'], 'tracking')

    def test_invalid_configs_and_frames_fail_with_clear_errors(self):
        for config in ({'design': 'normal'}, {'marker_id': 50}, {'roi': [-1, 0, 1, 1]}, {'roi': [0, 0, 2, 1]}):
            with self.subTest(config=config), self.socket() as ws:
                message = self.configure(ws, **config)
                self.assertEqual(message['type'], 'error')
        with self.socket() as ws:
            self.configure(ws)
            ws.send(b'not a JPEG')
            self.assertEqual(json.loads(ws.recv(timeout=3))['type'], 'error')

    def test_resolution_change_requires_a_new_flow_selection(self):
        with self.socket() as ws:
            self.configure(ws, 'optical-flow', roi=[.2, .2, .6, .6])
            self.assertEqual(self.frame(ws, self.texture())['status'], 'tracking')
            changed = self.frame(ws, cv2.resize(self.texture(), (320, 240)))
            self.assertEqual(changed['status'], 'needs_selection')
            self.assertIsNone(changed['corners'])


if __name__ == '__main__':
    unittest.main()
