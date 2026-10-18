import unittest
from wire import WireMonitor


class WireMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.monitor = WireMonitor(clock=lambda: self.now)

    def test_unknown_before_first_heartbeat(self):
        self.assertIsNone(self.monitor.snapshot()["connected"])
        self.assertFalse(self.monitor.snapshot()["fresh"])

    def test_connection_disconnect_and_expiry(self):
        self.assertTrue(self.monitor.update(True)["connected"])
        self.now = 4.9
        self.assertTrue(self.monitor.snapshot()["fresh"])
        self.now = 5.0
        self.assertIsNone(self.monitor.snapshot()["connected"])
        self.assertFalse(self.monitor.snapshot()["fresh"])
        self.assertFalse(self.monitor.update(False)["connected"])
        self.assertTrue(self.monitor.snapshot()["fresh"])

    def test_heartbeat_refreshes_expiry(self):
        self.monitor.update(True)
        self.now = 4.0
        self.monitor.update(True)
        self.now = 8.0
        self.assertTrue(self.monitor.snapshot()["connected"])


if __name__ == "__main__":
    unittest.main()
