# Tracking constraint comparison

**Measured on synthetic inputs only. Rendering FPS has not been measured.**

Run started: 2026-10-21T18:40:05+00:00 (UTC).

| Design | Peak observed RAM (GB) | Processing P95 (ms) | Correct visible frames (%) | False tracking (%) | Normalized CPU (%) | 3D FPS |
| --- | --- | --- | --- | --- | --- | --- |
| [design-1-aruco](design-1-aruco/results/summary.md) | 0.0698 | 8.74 | 100.00 | 0.00 | 6.08 | N/A |
| [design-2-orb-ransac](design-2-orb-ransac/results/summary.md) | 0.1833 | 44.40 | 100.00 | 0.00 | 26.96 | N/A |
| [design-3-optical-flow](design-3-optical-flow/results/summary.md) | 0.0733 | 15.13 | 63.64 | 0.00 | 11.18 | N/A |

See each design report for limits, pass/fail results, conditions, environment, and measurement boundaries.
These measurements are not evidence of physical-dummy recognition or final-model performance.
