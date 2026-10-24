"""Constraint 4: runtime browser and backend memory consumption."""
from .shared import metric, runtime_metric


NUMBER = 4
ID = "memory_efficiency"
NAME = "4. Memory Efficiency (RAM Consumption)"
UNIT = "MB"


def build(report, source, trials):
    memory = runtime_metric(trials, "memory")
    return metric(ID, NAME, UNIT, memory.get("mean_mb"), memory["status"],
                  "Mean sampled browser plus Python backend process-tree RSS; sampled peak and failures are retained in evidence.",
                  "Resident/working-set sum in decimal MB; shared pages may be counted more than once, and sampling can miss short peaks.",
                  memory)
