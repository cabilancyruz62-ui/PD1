"""One ESP32 wire input, with a heartbeat timeout independent of UI settings."""
from threading import Lock
from time import monotonic


class WireMonitor:
    def __init__(self, timeout_seconds=5.0, clock=monotonic):
        self._timeout = timeout_seconds
        self._clock = clock
        self._lock = Lock()
        self._connected = False
        self._last_seen = None

    def update(self, connected):
        with self._lock:
            self._connected = connected
            self._last_seen = self._clock()
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            age = None if self._last_seen is None else max(0, self._clock() - self._last_seen)
            fresh = age is not None and age < self._timeout
            return {
                "source": "esp32", "connected": self._connected if fresh else None,
                "fresh": fresh, "age_seconds": age, "timeout_seconds": self._timeout,
            }
