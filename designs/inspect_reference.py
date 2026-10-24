"""Check real target photographs with the existing trackers, without a camera.

This is a static image diagnostic. An identical-frame flow check is deliberately
labelled as such; it is not evidence of stable video tracking or a benchmark.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2

from run import load_design


def summarize(result):
    return {"status": result.status, "detail": result.detail, "metrics": result.metrics}


def inspect_profile(profile_path):
    profile_path = Path(profile_path).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    orb_module = load_design("orb")
    flow_module = load_design("optical-flow")
    aruco_module = load_design("aruco")
    photos = []
    frames = []
    references = []
    cv2.setRNGSeed(0)
    cv2.setNumThreads(1)
    for photo in profile["photos"]:
        image_path = profile_path.parent / photo["file"]
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"Cannot decode photo: {image_path}")
        roi = photo["surface_roi_xywh"]
        if len(roi) != 4 or any(type(value) is not int for value in roi):
            raise ValueError(f"ROI must contain four pixel integers: {photo['id']}")
        x, y, width, height = roi
        if min(x, y) < 0 or min(width, height) <= 0 or x+width > frame.shape[1] or y+height > frame.shape[0]:
            raise ValueError(f"ROI must be entirely inside the photo: {photo['id']}")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        patch = frame[y:y+height, x:x+width].copy()
        orb = orb_module.OrbTracker()
        reference_points, _ = orb.orb.detectAndCompute(gray[y:y+height, x:x+width], None)
        scene_points, _ = orb.orb.detectAndCompute(gray, None)
        entry = {
            "id": photo["id"], "file": photo["file"],
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "image_width_px": frame.shape[1], "image_height_px": frame.shape[0],
            "surface_roi_xywh": roi,
            "orb_reference_features": len(reference_points),
            "orb_scene_features": len(scene_points),
            "orb_scene_features_inside_roi": sum(x <= point.pt[0] < x+width and y <= point.pt[1] < y+height for point in scene_points),
        }
        try:
            entry["orb_same_photo_check"] = summarize(orb.initialize(frame, roi))
        except ValueError as error:
            entry["orb_same_photo_check"] = {"status": "reference_rejected", "detail": str(error), "metrics": {}}
        flow = flow_module.OpticalFlowTracker()
        initialized = flow.initialize(frame, roi)
        entry["flow_initialization"] = summarize(initialized)
        entry["flow_identical_frame_check"] = summarize(flow.update(frame)) if initialized.tracked else None
        entry["flow_video_tracking_validated"] = False
        marker = aruco_module.ArucoTracker(marker_id=profile["marker"]["id"])
        entry["aruco_unmarked_photo_check"] = summarize(marker.update(frame))
        photos.append(entry)
        frames.append(frame)
        references.append(patch)

    cross_view = []
    for index, reference in enumerate(references):
        try:
            tracker = orb_module.OrbTracker(reference)
        except ValueError:
            continue
        for other, frame in enumerate(frames):
            if index == other:
                continue
            tracker.reset()
            cross_view.append({"reference": photos[index]["id"], "scene": photos[other]["id"],
                **summarize(tracker.update(frame))})
    return {
        "target_id": profile["target_id"], "opencv_version": cv2.__version__,
        "analysis_type": "static_photo_intake",
        "live_tracking_validated": False, "metric_pose_calibrated": False,
        "notes": [
            "ROIs were manually selected inside the pad surface. Background, ruler, tubing, and pad boundaries are excluded.",
            "A successful identical-frame optical-flow check cannot establish stability under camera movement, lighting changes, or occlusion.",
            "Feature counts are image diagnostics, not constraint-benchmark results or proof of target identity.",
            "No ArUco marker is attached in the supplied photographs, so no marker detection is expected.",
        ],
        "photos": photos, "orb_cross_view_checks": cross_view,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect_profile(args.profile)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, cv2.error) as error:
        parser.exit(1, f"Reference inspection: {error}\n")
    print(f"Saved static photo diagnostic: {args.output}")
    for photo in report["photos"]:
        print(f"{photo['id']}: ORB reference features={photo['orb_reference_features']}, "
              f"ORB result={photo['orb_same_photo_check']['status']}, "
              f"flow initialization={photo['flow_initialization']['status']}; live video validation pending")


if __name__ == "__main__":
    main()
