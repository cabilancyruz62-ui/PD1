# Injection pad used as the dummy

The three supplied photographs are saved unchanged in [photos](photos/). Their filenames, hashes, manually selected pad-only regions, and actual tracker results are recorded in [profile.json](profile.json) and [photo-check.json](photo-check.json). These photographs show the original smooth pad before the printed targets and sensors are mounted.

## Findings from the supplied photographs

| Photograph | Pad-only ROI: x, y, width, height (pixels) | ORB reference features | ORB result on the same photograph | Optical-flow initialization points |
| --- | --- | --- | --- | --- |
| Oblique | 200, 335, 235, 100 | 0 | Reference rejected | 182 |
| Working view | 280, 425, 280, 140 | 0 | Reference rejected | 182 |
| Ruler view | 150, 220, 170, 600 | 214 | Searching; insufficient matching coverage | 200 |

Regions exclude the ruler, patterned fabric, tubing, and pad boundaries. The ruler-view reference also failed to match the other two views. No marker is attached in these photographs, so Design 1 correctly finds none. The flow checks initialize image points and repeat the identical still photograph; this does **not** validate stability across real video frames. Fine grain, reflections, and image compression can provide points without providing a dependable physical target.

The existing tracking thresholds were retained. These results are photo diagnostics, not memory/CPU/FPS benchmarks, recognition accuracy, or proof of a calibrated 3D pose. The reported physical dimensions are retained in the profile; scale remains unverified, including the length/width units.

## Design 1: print and mount ArUco

Print [print-targets.pdf](targets/print-targets.pdf) on **A4 at 100% / Actual size**, with Fit to page disabled. The sheet contains only ArUco marker 0. Measure the **50 mm check bar** and the **24 mm black marker square** after printing. The surrounding white margin is 4 mm per side, making the marker card 32 x 32 mm. These are proposed artwork dimensions, not measured calibration values. Cut around the dashed outline with scissors, keeping the complete white margin.

The editable source is [print-targets.svg](targets/print-targets.svg). Separate marker SVG and PNG files are in [targets](targets/). PNG files have pixel dimensions only; printing them through an image viewer may rescale them. Use the A4 PDF to preserve the intended layout and measure the result. To re-export a changed SVG, open it in a browser, print to PDF using A4, zero margins, 100% scale, and no headers/footers. Existing texture artwork is retained for optional assisted experiments and is excluded from the planned trials.

Attach the marker flat to a **removable rigid tab fixed to the pad**. Keep the injection surface, tubes, and sensor positions clear. A loose card on the table will track the card rather than stay registered to the pad. Use matte printing and avoid reflective tape over the artwork. Photograph the assembly again after installing sensors if their placement changes the camera view.

| Design | Target visible during its trial | Initialization |
| --- | --- | --- |
| 1: ArUco | Marker 0, including all four corners and its white margin | Automatic detection with the configured dictionary and ID |
| 2: ORB + RANSAC (later) | Original pad surface; no ArUco card or added texture | Press **s** and select a natural surface region, or supply a cropped working-camera photograph of it |
| 3: Sparse optical flow (later) | Original pad surface; no ArUco card or added texture | Press **s** and select existing surface details in the first frame |

The test order is **Design 1 first**, then **Designs 2 and 3 without a texture helper**. Remove printed targets from the scene for those later trials and exclude background, sensors, and hands from the selected surface region. Preserve comparable camera, resolution, and lighting conditions and record the mounting condition for each method. If the unchanged pad cannot supply reliable features, report that limitation. Do not infer natural-pad tracking from successful synthetic texture tests or lower quality checks merely to make the trial pass.

Use a plain matte background, diffuse lighting, and a sharply focused camera. For Design 1, keep the complete marker and white margin visible. Move closer if the marker is too small or blurry to detect; if you enlarge its artwork, record the measured printed size. For later natural-surface trials, capture the pad sharply and check whether usable details actually exist in the selected region.

## Run Design 1 now

From the repository root, use a Python environment containing `designs/requirements.txt`. The existing backend environment was used for the saved checks:

```powershell
.\backend\.venv\Scripts\python.exe designs/run.py --design aruco --marker-id 0
```

The runner defaults to camera 0; add `--camera 1` if the working webcam uses that index. Close other apps using the camera. Show marker 0: the status should become `tracking` and its current outline should appear. Cover it completely: the outline should disappear and status become `lost`. Uncover it: detection should resume. Keep the pad stationary while testing a small slow camera movement separately. Press **q** or **Esc** in the preview to exit and release the camera. A successful camera opening alone does not validate marker detection; show the actual mounted print to perform this check.

The standalone runner outputs a **2D outline and status in a camera window**. To use the same tracker on the website, close that window and choose **Settings → Tracking mode → Design 1**. The frontend follows the target in 2D and hides the camera dog when tracking is invalid. Metric pose and the calibrated pad-to-dog transform remain unimplemented. See [frontend tracking instructions](../../../docs/TRACKING.md).

## Later: Designs 2 and 3 without added texture

Remove the ArUco card and any other printed helper from the scene. Run one experiment at a time:

```powershell
.\backend\.venv\Scripts\python.exe designs/run.py --design orb
.\backend\.venv\Scripts\python.exe designs/run.py --design optical-flow
```

Press **s**, select only an existing surface region on the pad, and confirm with Enter or Space. For ORB, a cropped reference photo of that original region is also supported. Optical flow needs manual selection and does not automatically recognize the pad. Retain rejected references, tracking loss, and insufficient features as trial outcomes.

## Next physical capture

For the current Design 1 trial, capture:

1. A sharp top-down view showing the complete assembly, with the injection area and target positions visible.
2. A view from the camera angle students will actually use, with marker 0 exposed and unobstructed.
3. A short video from that working camera: about 5 seconds with the camera and pad stationary, a small slow camera movement, then partial hand occlusion and uncovering. Keep the pad stationary throughout. Capture target removal separately when testing loss and reacquisition.

Later, capture corresponding photos and video of the unchanged pad for Designs 2 and 3, with all printed targets removed. Prefer original-resolution files with the camera position, resolution, lighting, and mounting condition recorded. A ruler can be included in a separate size-check photo; exclude it from the ORB reference and flow selection. Avoid including hands, background patterns, or sensors in the selected pad-surface region.

Use those recordings to assess detection, tracking stability, hand occlusion, loss/reacquisition, and computational constraints. Design 3 needs manual selection again after tracking is lost. The current still photographs cannot supply those temporal results.

## Reproduce the saved checks

```powershell
.\backend\.venv\Scripts\python.exe designs/inspect_reference.py --profile designs/references/injection-pad/profile.json --output designs/references/injection-pad/photo-check.json
.\backend\.venv\Scripts\python.exe designs/make_pad_targets.py
.\backend\.venv\Scripts\python.exe -m unittest discover -s designs/tests -v
```

`make_pad_targets.py` recreates the ArUco-only print sheet, separate PNG/SVG artwork, and [artwork-check.json](targets/artwork-check.json); the PDF is a browser export of the A4 SVG. The generator decodes marker 0 and retains optional texture-artwork checks for reproducibility. Those exercise the actual ORB/flow trackers on stationary and mildly transformed digital artwork, rejecting failed tracking or corner error above 4 pixels. These **synthetic artwork checks** do not validate printing, a physical camera, lighting, occlusion, or natural-pad tracking. The texture helper is excluded from the planned Design 2/3 pad trials.
