# Tracking constraint comparison

**Measured on synthetic inputs only. Rendering FPS has not been measured.**

Run started: 2026-10-21T18:04:00+00:00 (UTC).

| Design | Peak observed RAM (GB) | Processing P95 (ms) | Correct visible frames (%) | False tracking (%) | Normalized CPU (%) | 3D FPS |
| --- | --- | --- | --- | --- | --- | --- |
| [design-1-aruco](design-1-aruco/results/summary.md) | 0.0703 | 15.17 | 100.00 | 0.00 | 8.11 | N/A |
| [design-2-orb-ransac](design-2-orb-ransac/results/summary.md) | 0.1832 | 68.14 | 100.00 | 0.00 | 27.31 | N/A |
| [design-3-optical-flow](design-3-optical-flow/results/summary.md) | 0.0727 | 31.35 | 63.64 | 0.00 | 16.74 | N/A |

See each design report for limits, pass/fail results, conditions, environment, and measurement boundaries.
These measurements are not evidence of physical-dummy recognition or final-model performance.
