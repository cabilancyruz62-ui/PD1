"""Process resource measurements for a complete benchmark worker.

The measured window includes frame generation, tracking, scoring, pacing, and
the sampling thread. RSS is sampled, so brief allocation peaks can be missed.
"""

import math
import platform
import threading
import time

import cv2
import numpy as np
import psutil


def environment_info():
    """Return reproducible machine facts without hostnames or user paths."""
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "psutil_version": psutil.__version__,
        "cpu_model": platform.processor() or None,
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "total_ram_gb": psutil.virtual_memory().total / 1e9,
        "gpu": None,
        "gpu_note": "GPU inventory and GPU rendering are not measured.",
    }


class ResourceMonitor:
    """Sample this process's RSS and measure its interval CPU consumption."""

    def __init__(self, sample_interval=0.05, *, process=None, logical_cpu_count=None):
        if not math.isfinite(sample_interval) or sample_interval <= 0:
            raise ValueError("sample_interval must be positive and finite")
        self.process = process if process is not None else psutil.Process()
        self.logical_cpu_count = (
            psutil.cpu_count(logical=True)
            if logical_cpu_count is None else logical_cpu_count
        )
        if self.logical_cpu_count is not None and self.logical_cpu_count <= 0:
            raise ValueError("logical_cpu_count must be positive")
        self.sample_interval = sample_interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._finished = False
        self._samples = 0
        self._peak = self._baseline = self._lifetime_peak = None
        self._errors = set()

    def _read(self, method):
        try:
            return getattr(self.process, method)()
        except (psutil.Error, OSError, AttributeError) as exc:
            with self._lock:
                self._errors.add(f"{method}: {type(exc).__name__}")
            return None

    def _cpu_time(self):
        value = self._read("cpu_times")
        return value.user + value.system if value is not None else None

    def observe(self):
        """Take an extra RSS sample; return GB, or None if unavailable."""
        value = self._read("memory_info")
        if value is None:
            return None
        with self._lock:
            if self._samples == 0:
                self._baseline = value.rss
            self._samples += 1
            self._peak = max(self._peak or 0, value.rss)
            lifetime_peak = getattr(value, "peak_wset", None)
            if lifetime_peak is not None:
                self._lifetime_peak = max(self._lifetime_peak or 0, lifetime_peak)
        return value.rss / 1e9

    def _sample_loop(self):
        while not self._stop.wait(self.sample_interval):
            self.observe()

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeError("ResourceMonitor instances cannot be reused")
        self._wall_start = time.perf_counter()
        self._cpu_start = self._cpu_time()
        self.observe()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        self._thread.join()
        self.observe()
        cpu_end = self._cpu_time()
        self._wall_seconds = time.perf_counter() - self._wall_start
        self._cpu_seconds = (
            max(0.0, cpu_end - self._cpu_start)
            if cpu_end is not None and self._cpu_start is not None else None
        )
        self._finished = True
        return False

    def summary(self):
        if not self._finished:
            raise RuntimeError("Read summary after the monitoring context exits")
        one_core_pct = (
            self._cpu_seconds / self._wall_seconds * 100
            if self._cpu_seconds is not None and self._wall_seconds > 0 else None
        )
        result = {
            "peak_memory_gb": self._peak / 1e9 if self._peak is not None else None,
            "baseline_memory_gb": (
                self._baseline / 1e9 if self._baseline is not None else None
            ),
            "cpu_normalized_pct": (
                one_core_pct / self.logical_cpu_count
                if one_core_pct is not None and self.logical_cpu_count else None
            ),
            "cpu_one_core_pct": one_core_pct,
            "cpu_seconds": self._cpu_seconds,
            "wall_seconds": self._wall_seconds,
            "samples": self._samples,
            "memory_measurement": (
                "Peak observed process RSS sampled at start, end, every "
                f"{self.sample_interval:g} seconds, and explicit observations; "
                "not allocation growth or guaranteed interval maximum. GB = 1e9 bytes."
            ),
            "measurement_errors": sorted(self._errors),
        }
        if self._lifetime_peak is not None:
            result["windows_lifetime_peak_working_set_gb"] = self._lifetime_peak / 1e9
        return result
