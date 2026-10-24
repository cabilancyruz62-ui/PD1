"""Generate the Design 1 print sheet and check the digital target artwork.

The generated images are proposed mounting targets, not calibrated photographs
of the physical pad. Synthetic checks do not establish real camera performance.
The separate texture artwork is retained for optional assisted experiments;
it is excluded from the print sheet and the planned Design 2/3 pad trials.
"""
import argparse
from html import escape
import json
from pathlib import Path

import cv2
import numpy as np

from run import load_design


PIXELS_PER_MM = 12
TEXTURE_WIDTH_MM = 40
TEXTURE_HEIGHT_MM = 25
MARKER_SIZE_MM = 24
MARKER_MARGIN_MM = 4
TEXTURE_SEED = 2051


def make_texture():
    """Draw the same non-coded irregular polygons as raster and SVG artwork."""
    rng = np.random.default_rng(TEXTURE_SEED)
    image = np.full((TEXTURE_HEIGHT_MM * PIXELS_PER_MM,
                     TEXTURE_WIDTH_MM * PIXELS_PER_MM), 255, np.uint8)
    artwork = ['<rect width="40" height="25" fill="white"/>']
    # Jittered positions distribute distinctive corners throughout the patch.
    # Sizes and polygon shapes vary; there are no repeating cells or encoded IDs.
    for row in range(9):
        for column in range(15):
            center = np.array([1.4 + column * 2.65, 1.3 + row * 2.75])
            center += rng.uniform(-0.5, 0.5, 2)
            count = int(rng.integers(3, 7))
            angles = np.sort(rng.uniform(0, 2 * np.pi, count))
            radii = rng.uniform(0.45, 1.05, count)
            points = center + np.column_stack((np.cos(angles), np.sin(angles))) * radii[:, None]
            points[:, 0] = np.clip(points[:, 0], 0.3, TEXTURE_WIDTH_MM - 0.3)
            points[:, 1] = np.clip(points[:, 1], 0.3, TEXTURE_HEIGHT_MM - 0.3)
            points = np.round(points, 3)
            shade = int(rng.choice([0, 0, 0, 65, 115]))
            cv2.fillPoly(image, [np.rint(points * PIXELS_PER_MM).astype(np.int32)], shade)
            vertices = " ".join(f"{x:g},{y:g}" for x, y in points)
            artwork.append(f'<polygon points="{vertices}" fill="rgb({shade},{shade},{shade})"/>')
    return image, "\n".join(artwork)


def svg_document(width_mm, height_mm, content):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" '
            f'height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">\n'
            f'{content}\n</svg>\n')


def marker_artwork():
    """Use OpenCV's actual six-by-six marker cells, including the black border."""
    cells = cv2.aruco.generateImageMarker(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), 0, 6)
    artwork = ['<rect width="32" height="32" fill="white"/>']
    for row, column in np.argwhere(cells == 0):
        artwork.append(f'<rect x="{4 + int(column) * 4}" y="{4 + int(row) * 4}" '
                       'width="4" height="4" fill="black"/>')
    return "\n".join(artwork)


def print_sheet(marker_svg):
    def text(x, y, value, size=3.2, bold=False):
        weight = ' font-weight="700"' if bold else ''
        return f'<text x="{x}" y="{y}" font-size="{size}"{weight}>{escape(value)}</text>'

    content = ['<rect width="210" height="297" fill="white"/>',
               '<g font-family="Arial, sans-serif" fill="#111">',
               text(20, 22, 'PupVitals | Design 1: ArUco tracking', 5, True),
               text(20, 32, 'A4 paper. Print at 100% / Actual size. Turn off Fit to page.'),
               text(20, 39, 'Cut around the dashed outline. Preserve the complete white margin.'),
               text(20, 51, 'ArUco DICT_4X4_50 / ID 0', 3.8, True),
               f'<g transform="translate(20 57)">{marker_svg}</g>',
               '<g fill="none" stroke="#777" stroke-width="0.15" stroke-dasharray="1 1">',
               '<rect x="19.5" y="56.5" width="33" height="33"/>',
               '</g>',
               text(65, 66, 'Black square: 24 x 24 mm'),
               text(65, 74, 'White margin: 4 mm per side'),
               text(65, 82, 'Complete marker card: 32 x 32 mm'),
               text(20, 108, 'Mount and test Design 1', 4, True)]
    instructions = [
        '1. Attach the marker to a removable rigid tab fixed to the pad.',
        '2. Keep the injection area, tubes, and sensor positions clear.',
        '3. Keep the complete marker flat, sharp, and visible to the camera.',
        '4. Start the ArUco experiment with marker ID 0 and camera 0.',
        '5. Show the marker, hide it, then uncover it to check reacquisition.',
        '6. Keep the pad stationary; test small camera movements separately.',
        '7. Press q or Esc in the preview to stop and release the camera.',
    ]
    for index, instruction in enumerate(instructions):
        content.append(text(20, 118 + index * 8, instruction))
    content.extend([
        text(20, 184, 'Later: Designs 2 and 3 use the unchanged pad.', 3.5, True),
        text(20, 192, 'Remove printed targets. No added texture helper is used in those trials.'),
        text(20, 207, 'Print scale check', 4, True),
        text(20, 216, 'Measure between the end ticks: exactly 50 mm.'),
        '<path d="M20 226 H70 M20 223 V229 M70 223 V229" fill="none" '
        'stroke="black" stroke-width="0.3"/>',
        text(20, 241, 'Measure the printed black square before recording any physical scale.'),
        text(20, 249, 'Artwork sizes are proposals. Camera and 3D registration remain uncalibrated.'),
        text(20, 270, 'Digital artwork checks are synthetic; physical tracking still needs a camera trial.', 3),
        '</g>',
    ])
    return svg_document(210, 297, "\n".join(content))


def check_artwork(marker, texture):
    """Exercise the real trackers on a known digital target and transformation."""
    cv2.setRNGSeed(0)
    cv2.setNumThreads(1)
    aruco_module = load_design("aruco")
    marker_check = aruco_module.ArucoTracker().update(cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR))
    no_marker = aruco_module.ArucoTracker().update(cv2.cvtColor(texture, cv2.COLOR_GRAY2BGR))
    if not marker_check.tracked or marker_check.metrics['detected_ids'] != [0]:
        raise ValueError("Generated marker does not decode as the configured ID 0.")
    if no_marker.metrics['detected_ids']:
        raise ValueError("Non-coded texture unexpectedly decodes as an ArUco marker.")

    height, width = texture.shape
    roi = (80, 90, width, height)
    scene = np.full((480, 640, 3), 255, np.uint8)
    scene[90:90 + height, 80:80 + width] = cv2.cvtColor(texture, cv2.COLOR_GRAY2BGR)
    transform = cv2.getRotationMatrix2D((320, 240), 3, 0.96)
    transform[:, 2] += (6, -4)
    moved = cv2.warpAffine(scene, transform, (640, 480), borderValue=(255, 255, 255))
    original_corners = np.float32([[80, 90], [80 + width - 1, 90],
                                   [80 + width - 1, 90 + height - 1], [80, 90 + height - 1]])
    expected = cv2.transform(original_corners[None], transform)[0]
    orb = load_design("orb").OrbTracker(texture)
    flow = load_design("optical-flow").OpticalFlowTracker()
    results = {"orb_stationary": orb.update(scene), "orb_moved": orb.update(moved),
               "flow_initialized": flow.initialize(scene, roi),
               "flow_stationary": flow.update(scene), "flow_moved": flow.update(moved)}
    checks = {}
    for name, result in results.items():
        if not result.tracked:
            raise ValueError(f"Synthetic artwork check failed: {name}: {result.detail}")
        target_corners = expected if name.endswith('_moved') else original_corners
        error = float(np.linalg.norm(result.corners - target_corners, axis=1).max())
        if error > 4:
            raise ValueError(f"Synthetic artwork alignment error: {name}: {error:.2f} px")
        checks[name] = {"status": result.status, "metrics": result.metrics,
                        "maximum_corner_error_px": round(error, 3)}
    return {
        "analysis_type": "synthetic_artwork_checks", "opencv_version": cv2.__version__,
        "texture_helper_used_in_planned_pad_trials": False,
        "physical_tracking_validated": False, "metric_pose_calibrated": False,
        "marker_ids_detected": marker_check.metrics['detected_ids'],
        "texture_aruco_ids_detected": no_marker.metrics['detected_ids'],
        "texture_reference_features": len(orb.reference_points),
        "movement": {"rotation_degrees": 3, "scale": 0.96, "translation_px": [6, -4]},
        "checks": checks,
        "note": "Digital artwork only; no printer, camera, lighting, hand occlusion, or physical pad was tested.",
    }


def generate(output):
    output = Path(output)
    marker = load_design("aruco").generate_marker(
        marker_id=0, size=MARKER_SIZE_MM * PIXELS_PER_MM,
        border=MARKER_MARGIN_MM * PIXELS_PER_MM)
    texture, texture_svg = make_texture()
    report = check_artwork(marker, texture)
    output.mkdir(parents=True, exist_ok=True)
    for name, image in (("marker-0.png", marker), ("texture-patch.png", texture)):
        if not cv2.imwrite(str(output / name), image):
            raise OSError(f"Could not write {output / name}")
    marker_svg = marker_artwork()
    (output / "marker-0.svg").write_text(svg_document(32, 32, marker_svg), encoding="utf-8")
    (output / "texture-patch.svg").write_text(
        svg_document(TEXTURE_WIDTH_MM, TEXTURE_HEIGHT_MM, texture_svg), encoding="utf-8")
    (output / "print-targets.svg").write_text(print_sheet(marker_svg), encoding="utf-8")
    (output / "artwork-check.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "references/injection-pad/targets")
    args = parser.parse_args()
    try:
        report = generate(args.output)
    except (OSError, ValueError, cv2.error) as error:
        parser.exit(1, f"Target generation: {error}\n")
    print(f"Saved Design 1 print sheet in {args.output}")
    print(f"Marker ID 0 decoded; texture has {report['texture_reference_features']} ORB features.")
    print("Synthetic stationary/movement checks passed. Physical camera validation is pending.")
    print("Separate texture artwork is optional and excluded from the planned Design 2/3 pad trials.")


if __name__ == "__main__":
    main()
