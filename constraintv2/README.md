# Three-design constraints v2

The official comparison covers **Design 1: ArUco, Design 2: ORB + RANSAC, and Design 3: optical flow only**. Normal mode is excluded. This folder implements the proposed five measurements while each design is used. The earlier [tracker benchmarks](../constraint/README.md) and their results remain separate. Electron is not required to begin: measure the current production website now and repeat on the final executable, hardware and Blender models later.

| Constraint | Metric and unit | Measurement boundary |
| --- | --- | --- |
| Storage efficiency | Tracker source storage, MB; shared application footprint separately | Each design's own tracker module is measured separately. Shared source, configuration and assets are supplementary totals, not three independent application builds. |
| Performance | Simulated input-to-display latency, ms | Actual Low/High angle control click through the frontend command, backend response and corresponding numeric angle/feedback popup. Mean, median and P95. Physical sensor latency requires a separate trial. |
| Maintainability | Tracker Python Maintainability Index, 0–100 | Radon MI for each design's tracker module. Shared Python mean/median are supplementary. Frontend JavaScript/JSX remains unmeasured. |
| Memory efficiency | Runtime RAM, MB | Mean and sampled peak of browser plus backend process-tree resident/working-set memory during simulation. |
| Computational efficiency | CPU utilization, % | Interval-weighted mean and sampled P95/peak CPU for the owned browser and backend process groups, normalized across logical CPUs. |

**These are metrics until acceptance limits are agreed.** [definitions.json](definitions.json) leaves the five proposed limits `null`; the reports do not invent passing grades. A maintainability score alone does not establish whether people can understand or safely modify the code. Keep actual tracking correctness and loss/recovery trials from v1 alongside these five metrics; low latency alone cannot establish successful tracking.

## Install and measure

Run from the repository root using the existing backend environment:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r constraintv2/requirements.txt
.\backend\.venv\Scripts\python.exe constraintv2/run.py
```

This measures storage and Python MI without launching a camera, browser or server. Dog triangles remain supplementary model metadata. Latency, RAM and CPU require a runtime trial; missing observations remain unmeasured.

To measure the running simulation as well, first build the current frontend:

```powershell
cd frontend
npm.cmd run build
cd ..
.\backend\.venv\Scripts\python.exe constraintv2/run.py --runtime
```

The default runtime trial uses **only ArUco, ORB and optical flow**, one repeat, at least five seconds of sampling and five latency events per design. A longer exploratory run is:

```powershell
.\backend\.venv\Scripts\python.exe constraintv2/run.py --runtime --seconds 30 --samples 30 --repeats 3
```

The output uses this layout:

```text
constraintv2/
  constraints/
    constraint1.py         # Storage calculation and description
    constraint2.py         # Latency calculation and description
    constraint3.py         # Maintainability calculation and description
    constraint4.py         # RAM calculation and description
    constraint5.py         # CPU calculation and description
  resultsv2/
    comparison.md          # Overall five-row table: Design 1 / Design 2 / Design 3
    comparison.csv         # Same table for spreadsheets
    comparison.json        # Machine-readable comparison
    measurements.json      # Full source inventory, environment and raw observations
    design1/
      constraint1.md       # Storage result
      constraint1.json     # Independent saved record and evidence
      constraint2.md       # Latency result
      constraint2.json
      constraint3.md       # Maintainability result
      constraint3.json
      constraint4.md       # RAM result
      constraint4.json
      constraint5.md       # CPU result
      constraint5.json
      constraints.md       # Linked overview, derived from the numbered files
      constraints.json     # Combined view, derived from the numbered files
    design2/               # The same five independent result files for ORB
    design3/               # The same five independent result files for optical flow
```

Open [resultsv2/comparison.md](resultsv2/comparison.md) for the overall table. Each design's numbered JSON files are independent saved results with their own evidence and measurement dates. Matching Markdown files are readable views. `constraints.md` links to all five. The overall table uses mean latency/RAM and interval-weighted mean CPU; individual reports also show sampled P95/peaks and failures.

To change how one constraint is calculated or described, edit only its module, such as [constraints/constraint5.py](constraints/constraint5.py). Then regenerate only that numbered result from a saved experiment:

```powershell
.\backend\.venv\Scripts\python.exe constraintv2/run.py --from-report constraintv2/resultsv2/measurements.json --constraints 5
```

This replaces only `constraint5.json` and its Markdown across the three designs, then refreshes their overviews and the overall comparison. Constraints 1-4 remain unchanged, including their dates and file contents. The original `measurements.json` also stays unchanged during a selective update. Selecting multiple numbers, such as `--constraints 2 4`, is supported. Old saved experiments have no CPU observations, so regenerating constraint 5 from them correctly shows **Not measured**.

To collect fresh CPU data and update only constraint 5, use the current production build and run:

```powershell
.\backend\.venv\Scripts\python.exe constraintv2/run.py --runtime --constraints 5
```

The same isolated runtime workload runs; only the selected result records are replaced. Their new CPU evidence and timestamps live in the individual `constraint5.json` files. Other constraint results retain their original observations.

If a saved JSON result needs a correction, edit that specific `resultsv2/designN/constraintN.json`, then refresh its readable views and comparison without remeasurement:

```powershell
.\backend\.venv\Scripts\python.exe constraintv2/run.py --refresh-comparison
```

Refresh reads the numbered JSON records, preserves their contents and timestamps, and marks records edited since generation with an asterisk. It does not silently present an edited number as a new measured result. Editing generated Markdown alone does not change the saved measurement. Invalid records are rejected before derived reports change; missing records show unmeasured values.

`--modes aruco orb`, for example, selects a subset of the three designs; untested runtime cells remain unmeasured. A full run replaces all five saved constraint records; `--constraints` limits replacements. `--output-root PATH` writes the same layout to another directory; use a directory outside the repository or named `resultsv2`, `results`, `reports` or `runs` so later storage inventories exclude it. `measurements.json` includes the complete original experiment, source/build fingerprints, tool/environment information and raw observations. After selective updates, each numbered JSON record is authoritative for that result's evidence and date. Rebuild immediately before a new runtime measurement.

`--from-report PATH/summary.json` (or a saved `measurements.json`) creates the new output layout from existing observations, retaining their measurement timestamps and recording the source report. It does not rerun the experiment. Earlier timestamped reports in `constraintv2/results/` remain unchanged as historical records; new outputs go into `resultsv2/`.

## What the results mean

**Storage:** 1 MB = 1,000,000 bytes throughout. The primary per-design measurement covers its own `designs/design-*/tracker.py`. It excludes shared infrastructure and is not a standalone application footprint. For supplementary context, `application_raw` covers frontend source/public files and entry/build manifests, backend production/configuration, AR assets and all imported tracking code. `total_mb` additionally includes repository documentation, tests, photos, printing assets and measurement tooling. Installed dependencies, virtual environments, Git history, builds, packaged binaries, runtime databases, environment files, caches and generated reports are excluded. Neither total is installer size, deployed footprint or filesystem allocated space. A procedural dog is source code; absent Blender/GLB files consume no model-asset bytes. Adding the final assets changes the shared footprint.

**Maintainability:** Each design receives the Radon MI score for its own tracker module; shared backend/frontend/common tracking code is excluded from that score. Scores depend on the selected MI formula and its treatment of comments, complexity and source length; compare using the same tool/version/scope. Mean/median of other eligible Python application files are supplementary descriptions, not a combined application MI. The JSON reports the number and extensions of omitted non-Python files. Do not report a tracker score as a maintainability score for the complete React/Python system. Selecting a compatible JavaScript analyzer and documenting its formula is additional work if a complete-language assessment is required. See [Radon's MI definition and cautions](https://radon.readthedocs.io/en/latest/intro.html#maintainability-index).

**Latency:** The runtime runner starts a private backend with a temporary SQLite database, serves the existing production build through Vite preview and opens an isolated headless Edge profile with a synthetic camera. It uses the actual frontend simulation controls and dismisses feedback via its Continue button. Timing begins immediately before clicking Low/High and ends when the matching fresh numeric angle and feedback popup exist in the visible DOM, followed by two animation-frame callbacks. This is a display-update proxy, not evidence of pixel presentation in a headless browser. Failed events are retained, not assigned zero milliseconds. This does not include MPU6050 sampling, ESP32 firmware, USB/serial/Wi-Fi transport or physical monitor scanout. Final sensor-to-display timing must start at a known physical sensor event with synchronized timestamps or an independent recording method. Five default samples support a smoke measurement, not a stable P95 claim.

**RAM:** The isolated browser and backend, including their child processes, are sampled about every 100 ms. Initialization, reference selection and a two-second warmup are excluded. Sampling continues through the latency events and for at least the requested steady interval. Reports include mean, sampled peak and browser/backend components. Shared pages may be counted more than once in a sum of process resident sets, and short peaks may fall between samples. The measurement controller, Vite preview server, other applications and the operating system are excluded. See [psutil memory semantics](https://psutil.readthedocs.io/en/latest/#psutil.Process.memory_info).

**CPU:** CPU sampling uses user + system CPU-time changes for unique processes in the owned browser/backend trees. It runs alongside RAM sampling after warmup. Each interval is normalized as `100 * CPU seconds / wall seconds / logical CPU count`; 100% means all logical CPU capacity. The primary mean is weighted by interval duration. P95 and peak describe the sampled interval percentages. The preview server, controller and unrelated applications are excluded. Missing process readings remain unknown; new processes are baselined at first sighting, and final CPU activity of processes exiting between samples can be missed. SwiftShader software graphics contributes to browser CPU, so these observations are preliminary and must be repeated with the intended GPU/Electron configuration. See [psutil CPU accounting](https://psutil.io/api/#psutil.Process.cpu_percent).

**Runtime comparability:** Every mode uses a fresh seeded backend and temporary browser profile, the same production build, assigned breed, injection stage, viewport and camera dimensions. Runtime graphics explicitly use SwiftShader software rendering in headless Edge, so these are preliminary controlled-browser observations, not final GPU or Electron results. Repeats rotate the starting mode; order is otherwise sequential. ArUco uses synthetic marker artwork, and ORB/flow use synthetic non-coded texture artwork with an operator-equivalent region selection. This is helper-assisted tracking, not a successful test of the unchanged physical pad. Tracking-status diagnostics establish that the workload ran, not geometric accuracy. No physical camera or user assessment database is used. Existing user services are left running, so their resource contention and other system activity can still affect the results.

**Supplementary model information:** Geometry is counted before view/occlusion culling and excludes extra rendering passes. Triangle counts remain in full measurement metadata, outside the five constraints. Current models are procedural stand-ins; repeat the geometry measurement when final Blender assets are integrated.

Tracker source storage and Python MI are reported separately for the three designs. Latency and RAM are measured while each design is selected. The application infrastructure and selected dog's geometry are shared controls; switching trackers does not produce three different complete application builds. Keep machine, workload, camera, model, lighting and trial duration consistent for comparisons; use longer repeated trials for a formal study and retain real-pad correctness/loss measurements separately.

The initial runtime protocol covers the initial injection stage, with each mode's default dog alignment and screen size. It compares the current mode configurations; it does not isolate tracker cost or establish peak RAM across an entire completed complication scenario.

## Check the measurement code

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s constraintv2/tests -p "test_*.py" -v
node --test constraintv2/tests/model_complexity.test.mjs
```
