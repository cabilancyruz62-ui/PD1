# Five-constraint design comparison

| Constraint | Design 1 | Design 2 | Design 3 |
| --- | ---: | ---: | ---: |
| 1. Storage Efficiency (Storage Consumption) | 0.002890 MB | 0.007358 MB | 0.006090 MB |
| 2. Performance (Latency) | 356.94 ms | 376.30 ms | 434.28 ms |
| 3. Maintainability (Maintainability Index Score) | 64.27 / 100 | 32.98 / 100 | 40.97 / 100 |
| 4. Memory Efficiency (RAM Consumption) | 1,427.70 MB | 1,338.55 MB | 1,413.62 MB |
| 5. Computational Efficiency (CPU Utilization) | 44.00 % | 50.76 % | 47.20 % |

- MB = 1,000,000 bytes. Storage and Maintainability Index cover each design's own tracker.py, not the complete application.
- Latency and RAM show successful-sample means. CPU shows time-weighted mean utilization normalized across logical CPUs for the owned browser and backend processes.
- Legacy observations used headless Edge with SwiftShader software rendering and synthetic camera/simulated inputs. These do not measure physical ESP32 latency or validate unchanged-pad tracking accuracy.
- CPU was not recorded in the earlier measurements: missing CPU data stays Not measured. Dog triangle counts remain supplementary metadata.
- No acceptance limits have been set. Each numbered constraint JSON keeps its own evidence and measurement dates; comparison refresh does not collect new measurements.
- Measurement window: 2026-10-23T18:06:31.037100+00:00 to 2026-10-23T18:08:10.578113+00:00. See each constraint file for its own provenance.
- Measurement window: 2026-10-23T19:02:23.290740+00:00 to 2026-10-23T19:03:43.730821+00:00. See each constraint file for its own provenance.

Detailed results: [Design 1](design1/constraints.md), [Design 2](design2/constraints.md), [Design 3](design3/constraints.md).
