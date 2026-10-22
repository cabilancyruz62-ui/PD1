# Design 1 constraint measurements

This folder stores measured results for the existing ArUco tracker in `designs/design-1-aruco/tracker.py`.

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe constraint/run.py --design aruco
```

The benchmark uses marker 0 with exact synthetic image-corner annotations. It measures process RAM, tracker processing time, correct tracking, false tracking, and CPU utilization. GPU rendering FPS is not applicable to this standalone 2D tracker. See [the shared protocol](../README.md).

After a run, open `results/summary.md` and `results/summary.json`. `results/frames.csv` retains the frame measurements and `results/trials.json` retains individual trial summaries.
