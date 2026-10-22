# Design 2 constraint measurements

This folder stores measured results for the existing ORB + RANSAC tracker in `designs/design-2-orb-ransac/tracker.py`.

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe constraint/run.py --design orb
```

The benchmark supplies a synthetic textured planar reference image with exact corner annotations. The ArUco pattern is not used as the reference. GPU rendering FPS is not applicable to this standalone 2D tracker. See [the shared protocol](../README.md).

After a run, open `results/summary.md` and `results/summary.json`. `results/frames.csv` retains the frame measurements and `results/trials.json` retains individual trial summaries.
