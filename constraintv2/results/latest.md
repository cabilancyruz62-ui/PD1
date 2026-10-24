# PupVitals constraint v2: three-design comparison

Collected: 2026-10-23T18:06:31.037100+00:00

Comparison derived from existing observations; no new experiment was run. Source: C:\Users\norud\Desktop\Veterinary-Anesthesia-AR-Starter\Veterinary-Anesthesia-AR\constraintv2\results\20261023T180810.578113Z\summary.json

These are measurements, with no pass/fail limits assigned. MB means 1,000,000 bytes.

Official comparison: Design 1 (ArUco), Design 2 (ORB + RANSAC), Design 3 (optical flow). Normal mode is outside this comparison.

## Design-specific source measurements

Each row covers that design's tracker module only. Shared frontend/backend, common tracking code and assets are excluded from these module totals; these are not standalone application footprints.

| Design | Tracker source MB | Tracker Python MI / 100 |
| --- | ---: | ---: |
| Design 1: ArUco | 0.002890 | 64.27 |
| Design 2: ORB + RANSAC | 0.007358 | 32.98 |
| Design 3: Optical flow | 0.006090 | 40.97 |

## Shared application context

The three designs use the same application infrastructure and models. The following totals include all three trackers and are supplementary context, not separate per-design scores.

| Metric | Result | Scope |
| --- | --- | --- |
| Raw application storage | 0.302520 MB | Source, configuration, models and runtime assets; excludes installed dependencies/builds |
| Raw repository storage | 0.970257 MB | Also includes documentation, tests, reference photos and measurement tools |
| Python Maintainability Index mean | 43.21 / 100 | 12 of 12 eligible Python files |
| Python Maintainability Index median | 44.00 / 100 | Per-file summary; frontend JS/JSX is unmeasured |

Non-Python source files outside MI coverage: 41. No whole-application MI is claimed.

## Canine model complexity

| Breed | Standing triangles | Lying triangles | Model |
| --- | ---: | ---: | --- |
| Labrador Retriever | 36,856 | 36,856 | Current procedural dog |
| Beagle | 38,760 | 38,760 | Current procedural dog |
| Dalmatian | 39,320 | 39,320 | Current procedural dog |

All three designs use the same canine geometry for a selected breed. Counts apply to one visible model and are a shared control, not a difference between trackers. They are triangle counts, not original Blender polygon counts or rendering FPS. Final Blender/GLB assets require another measurement.

## Simulation latency and RAM

Preliminary headless Edge with SwiftShader software rendering and synthetic camera targets. Latency starts at a simulated-angle control click and ends at matching DOM feedback plus two animation-frame callbacks, a display-update proxy. Physical acquisition/transport and pixel presentation are excluded.

| Repeat | Mode | Status | Latency samples OK/attempted | Mean ms | P95 ms | Mean RAM MB | Sampled peak RAM MB |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | aruco | measured | 5/5 | 356.94 | 534.86 | 1,427.70 | 1,570.82 |
| 1 | orb | measured | 5/5 | 376.30 | 451.88 | 1,338.55 | 1,362.77 |
| 1 | optical-flow | measured | 5/5 | 434.28 | 630.00 | 1,413.62 | 1,593.98 |

RAM sums the isolated browser and Python backend process working sets. Shared pages can be counted more than once; sampling can miss short peaks. Preview server/controller and unrelated applications are excluded.
Tracking uses synthetic ArUco or non-coded texture artwork; it does not validate the unchanged physical injection pad. See JSON for setup failures, tracking diagnostics, raw samples and component RAM.

Physical sensor latency, final GPU operation, final Blender assets and a packaged Electron application still require measurements in their intended operating conditions.

Full per-file inventory, exclusions, environment, source fingerprints, errors and raw observations are in the companion JSON.
