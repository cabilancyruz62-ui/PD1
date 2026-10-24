"""Constraint 1: each tracking design's own source storage."""
from .shared import metric, number


NUMBER = 1
ID = "storage_efficiency"
NAME = "1. Storage Efficiency (Storage Consumption)"
UNIT = "MB"


def build(report, source, trials):
    storage = source.get("storage", {})
    value = number(storage.get("mb"))
    return metric(ID, NAME, UNIT, value,
                  storage.get("status", "unavailable") if value is not None else "unavailable",
                  "Logical tracker source bytes / 1,000,000.",
                  "This design's own tracker.py only; shared application code, assets, dependencies and builds are excluded.",
                  storage)
