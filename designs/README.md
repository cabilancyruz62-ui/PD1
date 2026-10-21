# PupVitals tracking designs

Three initial Python/OpenCV experiments for tracking a region on the physical dummy. They share a camera/video runner and draw a target outline, tracked points, and status. They run separately from the React frontend and FastAPI backend; the Blender model and ML training are not required.

| Folder | Implementation | Target setup |
| --- | --- | --- |
| [design-1-aruco](design-1-aruco/) | ArUco detection, configured marker ID, printable marker generator | Attach the generated marker to the dummy |
| [design-2-orb-ransac](design-2-orb-ransac/) | ORB feature matching and RANSAC planar homography | Reference photograph or live selection of a textured region |
| [design-3-optical-flow](design-3-optical-flow/) | Sparse pyramidal Lucas-Kanade optical flow and RANSAC similarity transform | Manual selection of a textured region |

## Windows setup

Run from the repository root. Python 3.10 or later is required. This separate environment keeps the experiments' dependencies apart from the backend.

```powershell
py -m venv designs/.venv
.\designs\.venv\Scripts\python.exe -m pip install -r designs/requirements.txt
```

Use the environment's executable directly; PowerShell activation is not necessary. Install only one OpenCV wheel variant in that environment. This prototype needs GUI-enabled `opencv-python`, rather than a headless package, for the interactive camera window and region selection. [OpenCV package instructions](https://github.com/opencv/opencv-python#installation-and-usage)

## Start an experiment

Generate and print marker 0, preserving its white margin. Attach it flat to the dummy, then run Design 1:

```powershell
.\designs\.venv\Scripts\python.exe designs/run.py --generate-marker designs/design-1-aruco/marker-0.png
.\designs\.venv\Scripts\python.exe designs/run.py --design aruco --marker-id 0
```

Run Design 2, then press **s** to capture a reference region from the live camera:

```powershell
.\designs\.venv\Scripts\python.exe designs/run.py --design orb
```

Alternatively, provide a cropped photograph of the physical dummy's target region:

```powershell
.\designs\.venv\Scripts\python.exe designs/run.py --design orb --reference "C:/path/to/dummy-reference.jpg"
```

Run Design 3, then press **s** to select the region to follow:

```powershell
.\designs\.venv\Scripts\python.exe designs/run.py --design optical-flow
```

All examples use camera index 0. Add `--camera 1` to try another webcam. Close other apps using the webcam if it cannot open; running these experiments does not require PupVitals to be open.

Keyboard controls:

- **s**: select a region for ORB or optical flow; drag a rectangle and press Enter or Space to confirm. Press **c** in the selection dialog to cancel.
- **r**: reset tracking. ORB retains its reference; optical flow needs a new selection.
- **q** or **Esc**: quit the preview.

Keep hands and background outside the selected region. Both camera and dummy can stay stationary. Optical flow should then report near-zero movement rather than requiring the dummy to move.

## Recorded video and camera-free checks

Use `--video` to process a local recording. `--headless` suppresses windows; ORB needs a reference or initial ROI, and optical flow needs an initial ROI. ROI coordinates are `X Y WIDTH HEIGHT` in the original video resolution, before any preview resizing.

```powershell
.\designs\.venv\Scripts\python.exe designs/run.py --design optical-flow --video "C:/path/to/trial.avi" --roi 100 120 200 160 --headless --max-frames 100
.\designs\.venv\Scripts\python.exe -m unittest discover -s designs/tests -v
```

Tests use generated images and temporary video files; they do not open a webcam. They check marker IDs, reference matching, stationary tracking, modest movement, target loss, reacquisition behavior, and the command-line runner.

## Shared output and current limits

`tracking_common.py` defines `TrackingResult`: status, detail, image-space corners, tracked points, and method-specific metrics. Status is `needs_selection`, `searching`, `tracking`, or `lost`. The preview draws the target proxy only for a valid current result, and never intentionally holds a lost target's old outline. Optical flow stays lost until manually selected again; ArUco and ORB can reacquire their configured marker/reference.

These are **2D tracking prototypes**. They do not yet drive the website's dog visibility or provide camera calibration, metric scale, a 3D pose, or model-to-dummy registration. The `processing` time shown is tracker computation time, not end-to-end camera latency. A matching marker/reference or consistent image points do not prove that the actual dummy is present. The "no dummy, no dog" behavior still requires target validation and frontend integration.

Use a roughly planar reference region for the ORB homography. Optical flow initially supports modest translation, rotation, and scale changes; it does not model perspective changes or limb bending. The synthetic checks do not replace physical-dummy tests under hand occlusion, lighting changes, or camera movement.

Keep Blender source files in `AR model/` and the final application model at `frontend/public/models/canine.glb`. Next integration milestone: connect a selected tracker's output to a calibrated renderer using a simple proxy before fitting the final model.

Implementation references: [ArUco detection](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html), [ORB feature matching](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html), [homography](https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html), and [optical flow](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html).
