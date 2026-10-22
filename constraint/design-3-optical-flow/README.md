# Design 3 constraint measurements

This folder stores measured results for the existing sparse optical-flow tracker in `designs/design-3-optical-flow/tracker.py`.

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe constraint/run.py --design optical-flow
```

The benchmark supplies the known initial target rectangle as a surrogate for an operator's manual selection. Human selection time is not measured. After tracking is lost, no automatic reselection is performed. A visible target returning after occlusion can therefore remain lost, and is counted as a tracking failure. GPU rendering FPS is not applicable to this standalone 2D tracker. See [the shared protocol](../README.md).

After a run, open `results/summary.md` and `results/summary.json`. `results/frames.csv` retains the frame measurements and `results/trials.json` retains individual trial summaries.
