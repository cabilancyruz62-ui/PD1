"""Small shared validation and observation-pooling helpers.

Constraint modules format existing observations; importing them does not collect
measurements, read application files, or start any application processes.
"""
from __future__ import annotations

import copy
import math

from runtime_metrics import summarize_latency, summarize_memory


def number(value, *, maximum=None):
    """Return an eligible finite nonnegative measurement, otherwise unknown."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0 or maximum is not None and value > maximum:
        return None
    return value


def metric(identifier, name, unit, value, status, statistic, scope, evidence):
    return {"id": identifier, "name": name, "unit": unit, "value": value,
            "status": status, "statistic": statistic, "scope": scope,
            "evidence": copy.deepcopy(evidence)}


def runtime_metric(trials, kind):
    """Pool raw observations rather than repeat means or percentiles.

    One legacy summary can be shown with its limitation. Multiple summary-only
    repeats cannot establish a pooled distribution. Failed/missing trials and
    failed raw samples stay visible rather than becoming successful zeroes.
    """
    definitions = {
        "latency": ("mean_ms", ("p50_ms", "p95_ms"), None),
        "memory": ("mean_mb", ("sampled_peak_mb",), None),
        "cpu": ("mean_pct", ("p95_pct", "sampled_peak_pct"), 100),
    }
    if kind not in definitions:
        raise ValueError(f"Unknown runtime measurement: {kind}")
    primary, secondary, maximum = definitions[kind]
    eligible = [trial for trial in trials if trial.get("status") in {"measured", "partial"}]
    observations, missing_raw = [], []
    for index, trial in enumerate(eligible, 1):
        source = trial.get(kind, {})
        raw = source.get("observations")
        if isinstance(raw, list):
            observations.extend(copy.deepcopy(raw))
        else:
            missing_raw.append(trial.get("repeat", index))
    if observations:
        try:
            if kind == "cpu":
                # Older saved reports have no CPU observations. Do not require
                # the optional CPU collector merely to render their other rows.
                from runtime_metrics import summarize_cpu
                summarize = summarize_cpu
            else:
                summarize = summarize_latency if kind == "latency" else summarize_memory
            result = summarize(observations)
            for key in (primary, *secondary):
                value = result.get(key)
                if value is not None and number(value, maximum=maximum) is None:
                    raise ValueError(f"Invalid {kind} summary value: {key}")
        except (ImportError, ValueError, KeyError, TypeError) as error:
            return {"status": "unavailable", primary: None,
                    **{key: None for key in secondary}, "observations": observations,
                    "reason": "Raw observations could not be summarized: " + str(error)}
        good = result["successful_samples"]
        all_measured = len(eligible) == len(trials) and all(trial.get("status") == "measured" for trial in trials)
        result["status"] = ("measured" if good and not result["failed_samples"] and not missing_raw and all_measured
                            else "partial" if good else "unmeasured")
        result["aggregation"] = ("Pooled successful raw intervals across repeats; mean is weighted by interval duration, while P95 and peak describe sampled intervals; failed samples remain in counts."
                                 if kind == "cpu" else
                                 "Pooled successful raw sample observations across repeats; failed samples remain in counts.")
        result["excluded_summary_only_repeats"] = missing_raw
        result["failed_or_missing_trials"] = len(trials) - len(eligible)
        return result
    if len(trials) == 1 and len(eligible) == 1:
        source = eligible[0].get(kind, {})
        value = number(source.get(primary), maximum=maximum)
        if value is not None and not isinstance(source.get("observations"), list):
            result = copy.deepcopy(source)
            result[primary] = value
            for key in secondary:
                result[key] = number(source.get(key), maximum=maximum)
            result["status"] = eligible[0]["status"]
            result["aggregation"] = "Existing single-trial summary only; raw sample observations are unavailable. No samples were reconstructed."
            return result
    return {"status": "unmeasured" if trials else "not_measured", primary: None,
            **{key: None for key in secondary},
            "aggregation": "No pooled value is available.",
            "reason": ("Raw observations are unavailable; multiple trial summaries cannot establish a pooled distribution."
                       if len(eligible) > 1 else "No successful observations are available for this design."),
            "failed_or_missing_trials": len(trials) - len(eligible),
            "excluded_summary_only_repeats": missing_raw}
