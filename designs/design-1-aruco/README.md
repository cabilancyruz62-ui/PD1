# Design 1: Marker-based computer vision

Initial implementation: detect a configured OpenCV ArUco marker (`DICT_4X4_50`,
IDs 0–49) and expose its four image corners to the shared preview. It needs no
ML training or reference photographs.

Run these commands from the repository root after installing
`designs/requirements.txt`:

```powershell
python designs/run.py --generate-marker designs/design-1-aruco/marker-0.png
python designs/run.py --design aruco --marker-id 0
```

Print the generated marker with its white margin intact and attach it flat to
the dummy. Keep all four corners visible to the webcam. Press **r** to reset
and **q** to quit. Only the configured marker ID enables the preview anchor;
other IDs are ignored. When that marker disappears, tracking is lost and the
anchor is hidden immediately. A visible marker is a proxy for the dummy: this
does not prove that the dummy itself is present.

`generate_marker(marker_id=0, size=400, border=40)` returns a grayscale image.
`size` is the marker's pixel width; `border` is the surrounding white margin,
so defaults produce a 480 × 480 image. Both are integers; `size` must be at
least 6 and `border` at least 1. For practical printing, use the larger defaults.

This milestone provides **2D detection only**. It does not estimate a calibrated
3D pose or align the finished Blender dog. That next step needs camera
calibration, the printed marker's physical dimensions, and a defined transform
from the marker to the model.

Reference: [OpenCV ArUco detection documentation](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html).
