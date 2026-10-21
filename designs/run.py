"""Run one tracking experiment without the website, backend, or Blender model."""

import argparse
import importlib.util
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parent
DESIGNS = {
    "aruco": ("design-1-aruco", "ArUco marker"),
    "orb": ("design-2-orb-ransac", "ORB + RANSAC"),
    "optical-flow": ("design-3-optical-flow", "Lucas-Kanade optical flow"),
}


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def load_design(design: str):
    path = ROOT / DESIGNS[design][0] / "tracker.py"
    spec = importlib.util.spec_from_file_location(f"pupvitals_{design.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", choices=DESIGNS, default="aruco")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, help="OpenCV camera index; defaults to 0")
    source.add_argument("--video", type=Path, help="Read a local video instead of a webcam")
    parser.add_argument("--marker-id", type=int, choices=range(50), default=0, metavar="0..49")
    parser.add_argument("--generate-marker", type=Path, metavar="PNG", help="Write a printable marker and exit")
    parser.add_argument("--reference", type=Path, help="Cropped reference photo for the ORB design")
    parser.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"), help="Initial region for ORB or optical flow, in source pixels")
    parser.add_argument("--headless", action="store_true", help="Process without opening a window")
    parser.add_argument("--max-frames", type=positive_int, help="Stop after this many frames")
    args = parser.parse_args(argv)
    if args.generate_marker:
        if args.generate_marker.suffix.lower() != ".png":
            parser.error("--generate-marker needs a .png output path")
        return args
    if args.camera is not None and args.camera < 0:
        parser.error("--camera must be 0 or greater")
    if args.video is not None and not args.video.is_file():
        parser.error(f"video file does not exist: {args.video}")
    if args.reference is not None:
        if args.design != "orb":
            parser.error("--reference is only used by --design orb")
        if not args.reference.is_file():
            parser.error(f"reference image does not exist: {args.reference}")
    if args.roi is not None:
        if args.design == "aruco":
            parser.error("ArUco uses a marker, not --roi")
        if min(args.roi[:2]) < 0 or min(args.roi[2:]) <= 0:
            parser.error("--roi needs nonnegative X/Y and positive WIDTH/HEIGHT")
        if args.reference is not None:
            parser.error("use either --reference or --roi for ORB initialization")
    if args.headless and args.design != "aruco" and args.roi is None and args.reference is None:
        parser.error("headless ORB/optical flow needs --reference (ORB only) or --roi")
    return args


def run(args) -> int:
    import cv2
    from tracking_common import draw_result

    module = load_design("aruco" if args.generate_marker else args.design)
    if args.generate_marker:
        marker = module.generate_marker(args.marker_id)
        args.generate_marker.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.generate_marker), marker):
            raise ValueError(f"could not write marker to {args.generate_marker}")
        print(f"Saved DICT_4X4_50 marker {args.marker_id}: {args.generate_marker}")
        return 0

    if args.design == "aruco":
        tracker = module.ArucoTracker(marker_id=args.marker_id)
    elif args.design == "orb":
        reference = None
        if args.reference is not None:
            reference = cv2.imread(str(args.reference))
            if reference is None:
                raise ValueError(f"could not decode reference image: {args.reference}")
        tracker = module.OrbTracker(reference=reference)
    else:
        tracker = module.OpticalFlowTracker()

    capture = cv2.VideoCapture(str(args.video) if args.video is not None else args.camera or 0)
    frames = tracked_frames = 0
    window = "PupVitals tracking experiment"
    try:
        if not capture.isOpened():
            raise ValueError("could not open video/camera; check the source and close other apps using the webcam")
        if not args.headless:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        print("2D tracking experiment. Target identity and calibrated 3D pose are not verified.")
        while args.max_frames is None or frames < args.max_frames:
            ok, frame = capture.read()
            if not ok or frame is None:
                if not frames:
                    raise ValueError("source opened but supplied no readable frames")
                if args.video is None:
                    raise ValueError("camera stopped supplying frames; reconnect and restart the experiment")
                break
            started = time.perf_counter()
            if frames == 0 and args.roi is not None:
                result = tracker.initialize(frame, tuple(args.roi))
                if args.headless and not result.tracked:
                    raise ValueError(f"initial --roi could not be tracked: {result.detail}")
            else:
                result = tracker.update(frame)
            processing_ms = (time.perf_counter() - started) * 1000
            frames += 1
            tracked_frames += int(result.tracked)
            if args.headless:
                continue
            cv2.imshow(window, draw_result(frame, result, DESIGNS[args.design][1], processing_ms))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("r"):
                tracker.reset()
            elif key == ord("s") and args.design != "aruco":
                roi = cv2.selectROI(window, frame, showCrosshair=True, fromCenter=False)
                if roi[2] > 0 and roi[3] > 0:
                    try:
                        selected = tracker.initialize(frame, roi)
                        print(selected.detail)
                    except ValueError as error:
                        print(f"Selection rejected: {error}", file=sys.stderr)
    finally:
        capture.release()
        if not args.headless:
            cv2.destroyAllWindows()
    print(f"Processed {frames} frames; target tracked in {tracked_frames} frames.")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        import cv2
    except ImportError as error:
        print(f"Missing tracking dependency: {error}. Install with: python -m pip install -r designs/requirements.txt", file=sys.stderr)
        return 1
    try:
        return run(args)
    except ImportError as error:
        print(f"Missing tracking dependency: {error}. Install with: python -m pip install -r designs/requirements.txt", file=sys.stderr)
        return 1
    except (ValueError, OSError, cv2.error) as error:
        print(f"Tracking experiment: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
