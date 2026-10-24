"""Constraint 3: each tracking design's own Python Maintainability Index."""
from .shared import metric, number


NUMBER = 3
ID = "maintainability"
NAME = "3. Maintainability (Maintainability Index Score)"
UNIT = "0-100"


def build(report, source, trials):
    maintainability = source.get("maintainability", {})
    value = number(maintainability.get("score_0_100"), maximum=100)
    return metric(ID, NAME, UNIT, value,
                  maintainability.get("status", "unavailable") if value is not None else "unavailable",
                  "Radon per-file Python Maintainability Index, 0-100.",
                  "This design's own tracker.py only; no frontend or whole-application score is claimed.",
                  maintainability)
