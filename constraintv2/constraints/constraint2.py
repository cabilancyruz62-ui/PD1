"""Constraint 2: simulated input-to-display latency."""
from .shared import metric, runtime_metric


NUMBER = 2
ID = "performance"
NAME = "2. Performance (Latency)"
UNIT = "ms"


def build(report, source, trials):
    latency = runtime_metric(trials, "latency")
    return metric(ID, NAME, UNIT, latency.get("mean_ms"), latency["status"],
                  "Mean successful simulated input-to-display latency; P50/P95 and failures are retained in evidence.",
                  "Actual simulated-angle control click to matching DOM feedback plus two animation-frame callbacks; physical ESP32 transport and pixel presentation are excluded.",
                  latency)
