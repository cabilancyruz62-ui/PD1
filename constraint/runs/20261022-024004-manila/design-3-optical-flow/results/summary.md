# design-3-optical-flow constraint results

**Controlled synthetic benchmark; not a physical-dummy validation.**

Measured: 2026-10-21T18:40:05+00:00 (UTC).

Resolution: 1280 x 720; source: 30 FPS; paced: True; frames per condition/repeat: 180; repeats: 3.

Limits are proposed project budgets, not clinical or industry standards.

| Constraint | Observed | Target | Result |
| --- | --- | --- | --- |
| Peak observed RAM | 0.0733 GB | <= 1 GB | pass |
| Processing P95 | 15.13 ms | <= 33 ms | pass |
| Correct visible frames | 63.64 % | >= 95 % | fail |
| 3D rendering FPS | N/A FPS | >= 30 FPS | not_applicable |
| Normalized CPU | 11.18 % | <= 60 % | pass |

| Condition | Processing P95 (ms) | Correct visible frames (%) | False tracking when absent (%) | Corner error P95 (px) |
| --- | --- | --- | --- | --- |
| stationary | 18.32 | 100.00 | N/A | 0.00 |
| camera_motion | 16.27 | 100.00 | N/A | 0.02 |
| dim_light | 0.03 | 0.00 | N/A | N/A |
| occlusion_recovery | 14.17 | 50.00 | 0.00 | 0.00 |
| target_absent | 0.03 | N/A | 0.00 | N/A |

Frames scored: 2700; visible: 1980; absent: 720.
Overall false tracking: 0.00%; limit: 1% of absent frames.
Stationary error jitter RMS: 0.00 px.
Mean normalized CPU: 11.18%; largest individual trial mean: 26.75%.

## Measurement boundaries

- The existing production tracker modules are imported without algorithm changes; each trial runs in a fresh isolated process.
- All designs use the same resolution, conditions, seed, pacing, and repeat count. ArUco requires a marker; ORB/flow use a textured patch, not the marker pattern.
- Correctness requires a tracked, valid quadrilateral with mean ordered-corner error within the configured tolerance; tracker status alone is insufficient.
- Initialization and warmup are excluded from scored frames, processing latency, and interval CPU. Reference/ROI preparation is supplied automatically; human setup time is not measured.
- RAM is peak observed process RSS in decimal GB, sampled every 50 ms and after each frame. Includes Python, OpenCV, target fixtures, tracker, and growing measurement rows; short peaks may be missed.
- CPU covers the complete worker window, including synthetic-frame preparation, scoring, sampling, and pacing. It is normalized across logical cores. It does not describe the browser/backend or the whole computer's background load.
- Processing time covers tracker.update only; excludes capture, frame generation, scoring, display, network, and camera-to-overlay latency. CPU/memory and processing time therefore have different measurement boundaries.
- No camera, video decoder, website, or 3D renderer is running in this test. Rendering FPS is N/A, not zero or a passing result; final-model rendering must be measured after integration.
- Camera-motion frames are synthetic similarity warps. Dim-light frames step from bright initialization to alpha=0.42, beta=10; this also tests an illumination change.
- Occlusion removes the complete target for the middle third. Optical flow is not automatically reselected; missing a returned visible target counts as failure. No human recovery time is inferred.
- A cheap lost-state update can lower processing time/CPU while accuracy fails. Interpret resource and correctness results together; these tests do not prove dummy identity or realistic hand-occlusion robustness.

## Environment

```json
{
  "platform": "Windows",
  "platform_release": "11",
  "python_version": "3.12.10",
  "opencv_version": "4.14.0",
  "numpy_version": "2.5.4",
  "psutil_version": "7.2.2",
  "cpu_model": "AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD",
  "logical_cpu_count": 16,
  "physical_cpu_count": 8,
  "total_ram_gb": 16.469532672,
  "gpu": null,
  "gpu_note": "GPU inventory and GPU rendering are not measured."
}
```

Raw frames: [frames.csv](frames.csv). Individual trial summaries: [trials.json](trials.json).
