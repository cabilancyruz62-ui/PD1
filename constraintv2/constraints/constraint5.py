"""Constraint 5: runtime CPU utilization normalized to total CPU capacity."""
from .shared import metric, runtime_metric


NUMBER = 5
ID = "computational_efficiency"
NAME = "5. Computational Efficiency (CPU Utilization)"
UNIT = "%"


def build(report, source, trials):
    cpu = runtime_metric(trials, "cpu")
    return metric(ID, NAME, UNIT, cpu.get("mean_pct"), cpu["status"],
                  "Mean CPU utilization weighted by observed interval duration, normalized across logical CPUs; sampled P95, peak and failures are retained in evidence.",
                  "Owned browser and Python backend process groups while the selected design runs; percent of total logical CPU capacity, not whole-system CPU utilization or a physical ESP32 measurement.",
                  cpu)
