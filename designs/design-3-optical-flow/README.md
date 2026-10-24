# Design 3: Sparse optical-flow tracking

Initial standalone OpenCV prototype: manually select a textured region on the
dummy, then follow Shi–Tomasi features with pyramidal Lucas–Kanade optical flow.
No training dataset or reference photograph is required. This is sparse optical
flow, rather than a full direct photometric pose-estimation implementation.

For the current injection pad, the planned trial uses its original surface **without a texture helper**. Remove printed targets and select only existing pad-surface details. The pad can stay stationary. A real camera recording is still needed; initializing points in a still photo does not establish video stability. See the [pad test plan](../references/injection-pad/README.md).

The same tracker also powers **Settings → Tracking mode → Design 3** in the frontend. Use **Select pad region** there to initialize the original surface, and select again after loss or stream interruption. See [frontend tracking](../../docs/TRACKING.md). Close the standalone preview before using the browser webcam.

From the repository root, install the shared dependencies and run:

```powershell
python -m pip install -r designs/requirements.txt
python designs/run.py --design optical-flow
```

Press **s** to select the target region (confirm the selection with Enter),
**r** to clear it, and **q** to quit. Select the physical dummy's textured surface
and exclude background and hands. Blank, smooth regions cannot provide enough
features. Both the dummy and camera may stay stationary: near-zero flow is valid.

The tracker checks forward/backward consistency and estimates a 2D similarity
transform with RANSAC to reject inconsistent points. It supports modest image
translation, rotation, and scale changes. A selected rectangle and its tracked
points are diagnostic overlays; this is not a calibrated 3D dog placement system.
Perspective changes, limb bending, occlusion, and accumulated drift remain limits.

When tracking fails, the target outline is removed. It stays lost until the
operator selects the target again; it does not automatically seed background
points. These checks do **not** recognize the dummy or prove it is present.
Features on a moving hand or background can still give a plausible transform.

Run the synthetic regression checks from the repository root:

```powershell
python -m unittest discover -s designs/tests -p test_optical_flow.py
```

Next validation: real webcam recordings with a stationary dummy, small camera
movement, student-hand occlusion, target removal, and manual reacquisition.
