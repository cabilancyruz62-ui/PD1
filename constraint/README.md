# Tracking constraints and measured results

The revised three-design metrics are in [constraintv2](../constraintv2/README.md): storage, simulated input-to-feedback latency, Python maintainability, runtime RAM and CPU utilization. Each design has separate numbered result files. This folder retains the original tracker benchmark definitions and results.

This folder benchmarks the existing tracking implementations in `designs/`. Each design has its own results folder:

```text
constraint/
  design-1-aruco/results/
  design-2-orb-ransac/results/
  design-3-optical-flow/results/
  comparison.md
  comparison.json
```

**These are controlled synthetic measurements, not real-dummy validation or final 3D-model performance.** The generated images have known corner locations, so accuracy is measured against ground truth rather than trusting a tracker's own status. No camera is accessed.

## Install and run

From the repository root, use the existing project environment:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r constraint/requirements.txt
.\backend\.venv\Scripts\python.exe constraint/run.py
```

The default run measures all three designs sequentially at **1280 x 720, paced at 30 FPS**, with **180 frames per condition and 3 repeats**. That is 2,700 scored frames per design and about 4.5 minutes of measurement time overall, plus initialization. Each condition/repeat uses a fresh worker process. Design order rotates between repeats. Close resource-heavy applications for a cleaner comparison.

Results overwrite the latest report files only after all selected trials finish. The comparison contains the designs selected for that invocation. Each design writes:

- `results/summary.md`: readable constraint results and per-condition measurements.
- `results/summary.json`: metrics, configured limits, machine/software metadata, source fingerprints, and measurement boundaries.
- `results/trials.json`: each independent trial's timing, resource readings, initialization time, and environment.
- `results/frames.csv`: ground-truth visibility, correctness, errors, tracking status, and processing time for every scored frame.

A shorter exploratory run:

```powershell
.\backend\.venv\Scripts\python.exe constraint/run.py --design aruco --frames 90 --repeats 1
```

Use `--opencv-threads 1` to explicitly fix the thread count. The default preserves OpenCV's configured thread count and records it. `--unpaced` measures maximum-throughput operation; its CPU results are not equivalent to a paced camera station. `--output-root "C:/path/to/results"` keeps an additional run without overwriting this folder's results.

## Five constraints

The editable [limits.json](limits.json) contains **proposed project budgets**, not validated standards:

| Constraint | Initial limit | Measurement |
| --- | --- | --- |
| Memory consumption | At most 1 GB | Peak observed process resident RAM; GB means 1,000,000,000 bytes |
| Response time | Processing P95 at most 33 ms | Time spent in `tracker.update` per frame |
| Tracking performance | At least 95% correct visible frames; at most 1% false tracking on absent frames | A valid ordered quadrilateral within 5 pixels mean corner error counts as correct |
| GPU/3D rendering FPS | At least 30 FPS once integrated | **N/A here**: standalone OpenCV trackers have no shared 3D renderer |
| CPU utilization | Average at most 60% of total logical CPU capacity | Process user + system CPU time divided by wall time and logical CPU count |

Reports use `pass`, `fail`, `not_applicable`, and `insufficient_data`. Missing measurements never become zero or an automatic pass. A subset containing no visible targets cannot pass tracking accuracy; a test without absent frames cannot pass the combined tracking constraint either. Known failures remain failures even when another required measurement is missing.

## Test conditions and initialization

1. **Stationary:** fixed target and camera; also records alignment-error jitter.
2. **Camera motion:** small synthetic translation, rotation, and scale changes with exact transformed corners.
3. **Dim lighting:** after bright initialization, brightness steps to 42% plus an offset of 10. This tests an illumination change as well as a dim scene.
4. **Occlusion and recovery:** target visible in the first third, completely removed in the middle third, and restored in the final third.
5. **Target absent:** initial setup sees the target, then every scored frame lacks it. This tests false continued tracking after target removal.

ArUco uses marker 0 and measures its black-border corners. ORB and optical flow use the same textured planar patch and its outer corners; they do not use the ArUco pattern as a feature reference. Their target appearances and setup assistance differ by design, so these are controlled implementation comparisons, not identical-object recognition trials.

ORB receives its reference image. Optical flow receives a known initial rectangle as a surrogate for operator selection. Ten stationary warmup updates precede each trial. Initialization and warmup are excluded from scored frames and steady-state resource timing. Human selection time is not measured. Optical flow is never silently reinitialized after loss: failure to track a returning visible target counts against accuracy.

## What the measurements cover

RAM includes the Python/OpenCV worker, tracker, synthetic fixture buffers, and retained measurement rows. Sampling occurs every 50 ms and after each frame; shorter allocation peaks can be missed. Windows lifetime peak working set, when available, is reported separately because it includes initialization and does not represent just the measured interval.

CPU includes the whole worker's frame generation, tracking, scoring, monitoring, and pacing. It excludes the controller, browser, backend, and unrelated applications. Processing latency times only the tracker update, excluding frame generation, capture, communication, and display. Computation-only throughput is not camera FPS, rendering FPS, or end-to-end latency.

After loss, a tracker's cheap idle updates can look fast while accuracy is poor. Interpret timing and CPU together with per-condition tracking success. Synthetic target removal and uniform backgrounds do not replace tests with hands, clutter, curved dummy limbs, or realistic texture and lighting. These tests do not verify dummy identity.

GPU rendering, camera-to-overlay latency, model fitting, and manual reacquisition time remain separate measurements after system integration. The existing placeholder can be used for preliminary rendering tests; the final Blender asset needs a new run.

## Validate the benchmark code

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s constraint/tests -v
.\backend\.venv\Scripts\python.exe -m unittest discover -s designs/tests -v
```

References: [OpenCV timing](https://docs.opencv.org/4.x/dc/d71/tutorial_py_optimization.html), [psutil process CPU and memory](https://psutil.readthedocs.io/en/stable/#psutil.Process.cpu_times), and [browser animation frame scheduling](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame).
