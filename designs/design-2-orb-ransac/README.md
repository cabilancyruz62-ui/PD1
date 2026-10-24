# Design 2: ORB + RANSAC homography

This Python/OpenCV prototype matches a textured reference region with ORB descriptors and estimates its planar image transform with RANSAC. It requires no ML training. Its output is a 2D quadrilateral and tracking status, used by both the standalone preview and the frontend's target-driven dog overlay.

For the current injection pad, the planned trial uses its original surface **without a texture helper**. Remove printed targets and capture a working-camera reference of the pad itself. The supplied unmodified-pad photos failed the existing matching checks; record insufficient features as a result if a new capture still cannot support tracking. See the [pad test plan](../references/injection-pad/README.md).

From the repository root, after installing `designs/requirements.txt`:

```powershell
python designs/run.py --design orb
python designs/run.py --design orb --reference "path/to/dummy-reference.jpg"
```

Without a reference image, press **s** and drag a rectangle around a distinctive region on the dummy in the selection window, then press Enter or Space to accept it. A region with printed details or irregular texture works better than a smooth, plain limb. **r** clears tracking history while retaining the reference; **q** exits. If the image has too few features, select a larger, more textured region.

The runner draws the current reference boundary only after sufficient unique feature matches, RANSAC inliers, reference coverage, and geometry checks pass. A failed frame has no boundary to render. Every frame is independently matched, so an available reference can be reacquired after occlusion or removal. No transform from an earlier frame is reused.

Use a small, approximately flat, rigid region for this first experiment. A single homography does not represent a curved limb, limb bending, or the whole dog's 3D pose. Matching reference texture is evidence of that region; it does not establish that the entire dummy is present. A photograph of the reference can also match.

The camera runner remains a standalone experiment. The same tracker also powers **Settings → Tracking mode → Design 2** in PupVitals, driving the dog's 2D overlay after manual pad-region selection. Camera calibration and Blender-rig integration remain separate work. See [frontend tracking](../../docs/TRACKING.md).

Validation from the repository root:

```powershell
python -m unittest discover -s designs/tests -v
```
