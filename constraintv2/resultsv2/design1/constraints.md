# Design 1: ArUco

| Constraint | Value |
| --- | ---: |
| [1. Storage Efficiency (Storage Consumption)](constraint1.md) | 0.002890 MB |
| [2. Performance (Latency)](constraint2.md) | 356.94 ms |
| [3. Maintainability (Maintainability Index Score)](constraint3.md) | 64.27 / 100 |
| [4. Memory Efficiency (RAM Consumption)](constraint4.md) | 1,427.70 MB |
| [5. Computational Efficiency (CPU Utilization)](constraint5.md) | 44.00 % |

Each constraint has its own JSON record and readable Markdown report. Edit the corresponding calculation in constraintv2/constraints/constraintN.py and selectively regenerate it, or refresh the comparison after a saved-record correction.

- MB = 1,000,000 bytes. Storage and Maintainability Index cover each design's own tracker.py, not the complete application.
- Latency and RAM show successful-sample means. CPU shows time-weighted mean utilization normalized across logical CPUs for the owned browser and backend processes.
- Legacy observations used headless Edge with SwiftShader software rendering and synthetic camera/simulated inputs. These do not measure physical ESP32 latency or validate unchanged-pad tracking accuracy.
- CPU was not recorded in the earlier measurements: missing CPU data stays Not measured. Dog triangle counts remain supplementary metadata.
- No acceptance limits have been set. Each numbered constraint JSON keeps its own evidence and measurement dates; comparison refresh does not collect new measurements.
- Measurement window: 2026-10-23T18:06:31.037100+00:00 to 2026-10-23T18:08:10.578113+00:00. See each constraint file for its own provenance.
- Measurement window: 2026-10-23T19:02:23.290740+00:00 to 2026-10-23T19:03:43.730821+00:00. See each constraint file for its own provenance.

[Overall comparison](../comparison.md)
