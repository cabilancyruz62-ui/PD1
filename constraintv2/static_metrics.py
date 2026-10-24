"""Raw-project storage inventory and explicitly Python-only maintainability.

This is a source-tree measurement, not an installer size or disk allocation
measurement. Dependencies, generated reports, runtime data and build products
are excluded before walking their contents. No dependency is installed here.
"""

import argparse
from collections import Counter
import importlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
from statistics import mean, median


MB = 1_000_000
CATEGORIES = (
    "source_code", "models_3d", "assets", "project_metadata", "documentation",
    "tests", "measurement_tools", "other",
)
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".sh", ".ps1"}
MODEL_SUFFIXES = {
    ".blend", ".glb", ".gltf", ".fbx", ".obj", ".stl", ".ply", ".dae", ".3ds",
    ".usd", ".usdz", ".usda", ".usdc", ".mtl",
}
ASSET_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".ico", ".tif", ".tiff",
    ".mp3", ".wav", ".ogg", ".mp4", ".webm", ".mov", ".avi", ".ttf", ".otf", ".woff",
    ".woff2", ".hdr", ".exr", ".ktx", ".ktx2", ".bin",
}
EXCLUDED_DIRS = {
    ".git": "version-control history",
    "node_modules": "installed dependencies",
    ".venv": "Python virtual environment",
    "venv": "Python virtual environment",
    "env": "environment directory",
    ".env": "environment directory",
    "dist": "generated build output",
    "build": "generated build output",
    "out": "generated build output",
    "release": "packaged application output",
    "releases": "packaged application output",
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "test cache",
    ".mypy_cache": "type-checker cache",
    ".ruff_cache": "linter cache",
    ".cache": "tool cache",
    "coverage": "generated test coverage",
    "htmlcov": "generated test coverage",
    "reports": "generated measurement reports",
    "results": "generated measurement results",
    "resultsv2": "generated v2 measurement results",
    "runs": "generated measurement runs",
    ".codex": "local assistant configuration",
    ".agents": "local assistant configuration",
    ".aws": "local credentials/configuration",
}
EXCLUDED_REPORT_NAMES = {
    "comparison.json", "comparison.csv", "comparison.md", "photo-check.json", "artwork-check.json",
}


def _excluded(relative, is_directory):
    """Explain omissions without reading dependency trees or private data."""
    lower = relative.name.lower()
    if is_directory:
        # Patient/profile constants under frontend/src/data are source, whereas
        # backend/data contains saved assessments and other mutable runtime data.
        if tuple(part.lower() for part in relative.parts) in {("backend", "data"), ("data",)}:
            return "runtime data directory"
        if lower in EXCLUDED_DIRS:
            return EXCLUDED_DIRS[lower]
        if len(relative.parts) == 1 and lower == "microsoft":
            return "PowerShell tool cache"
    else:
        if lower == ".env" or lower.startswith(".env."):
            return "environment configuration"
        if relative.suffix.lower() in {".pyc", ".pyo", ".log", ".exe", ".dll", ".pyd", ".so", ".dylib", ".o"}:
            return "compiled artifact or runtime log"
        if lower in EXCLUDED_REPORT_NAMES:
            return "generated diagnostic report"
        if lower in {".coverage", ".ds_store", "thumbs.db"}:
            return "generated tool metadata"
    return None


def _category(relative):
    suffix = relative.suffix.lower()
    parts = [part.lower() for part in relative.parts]
    name = relative.name.lower()
    if "tests" in parts or name.startswith("test_") or ".test." in name or ".browser." in name:
        return "tests"
    if suffix in MODEL_SUFFIXES:
        return "models_3d"
    if suffix in ASSET_SUFFIXES or (suffix == ".pdf" and "docs" not in parts):
        return "assets"
    if suffix in {".md", ".rst", ".pdf"} or (suffix == ".txt" and not name.startswith("requirements")):
        return "documentation"
    if parts[0] in {"constraint", "constraintv2"} and suffix in SOURCE_SUFFIXES:
        return "measurement_tools"
    if suffix in SOURCE_SUFFIXES:
        return "source_code"
    if suffix in {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".lock", ".txt"} or name in {".gitignore", ".gitattributes"}:
        return "project_metadata"
    return "other"


def _totals(files):
    size = sum(item["bytes"] for item in files)
    return {"file_count": len(files), "bytes": size, "mb": size / MB}


def _application_payload(relative, category):
    """Define the raw application files separately from repository support."""
    parts = [part.lower() for part in relative.parts]
    if category in {"tests", "documentation", "measurement_tools"}:
        return False
    if len(parts) >= 2 and parts[:2] in (["frontend", "src"], ["frontend", "public"]):
        return True
    if len(parts) == 2 and parts[0] == "frontend" and parts[1] in {
        "index.html", "package.json", "package-lock.json", "vite.config.js", "vite.config.ts",
    }:
        return True
    if parts[0] == "backend":
        return category in {"source_code", "project_metadata", "assets", "models_3d"}
    if parts[0] == "ar model":
        return category in {"source_code", "project_metadata", "assets", "models_3d"}
    # The backend dynamically imports the existing tracking prototypes.
    if parts[0] == "designs":
        return relative.as_posix().lower() in {
            "designs/run.py", "designs/tracking_common.py", "designs/requirements.txt",
            "designs/design-1-aruco/tracker.py", "designs/design-2-orb-ransac/tracker.py",
            "designs/design-3-optical-flow/tracker.py",
        }
    return False


def measure_storage(project_root):
    """Return logical file lengths with an auditable exclusion/category list.

    Symlinks and Windows junctions are omitted to avoid following files outside
    the selected source tree or counting targets twice. Directory entry sizes,
    compression and filesystem allocation overhead are deliberately not counted.
    """
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project_root must be a directory")
    files, exclusions, errors = [], [], []

    def walk_error(error):
        path = Path(error.filename) if error.filename else root
        errors.append({"path": os.path.relpath(path, root), "reason": str(error)})

    for current, directories, names in os.walk(root, followlinks=False, onerror=walk_error):
        directory = Path(current)
        kept = []
        for name in sorted(directories):
            path = directory / name
            relative = path.relative_to(root)
            reason = _excluded(relative, True)
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                reason = "symbolic link or Windows junction"
            if reason:
                exclusions.append({"path": relative.as_posix() + "/", "reason": reason})
            else:
                kept.append(name)
        directories[:] = kept
        for name in sorted(names):
            path = directory / name
            relative = path.relative_to(root)
            reason = _excluded(relative, False)
            if path.is_symlink():
                reason = "symbolic link"
            if reason:
                exclusions.append({"path": relative.as_posix(), "reason": reason})
                continue
            try:
                if not path.is_file():
                    exclusions.append({"path": relative.as_posix(), "reason": "not a regular file"})
                    continue
                category = _category(relative)
                files.append({"path": relative.as_posix(), "category": category, "bytes": path.stat().st_size,
                              "application_payload": _application_payload(relative, category)})
            except OSError as error:
                errors.append({"path": relative.as_posix(), "reason": str(error)})
    files.sort(key=lambda item: item["path"])
    totals = _totals(files)
    top_levels = sorted({item["path"].split("/")[0] if "/" in item["path"] else "(root files)" for item in files})
    return {
        "status": "partial" if errors else "measured",
        "scope": "raw project files; includes source, models, assets, metadata, docs, tests and measurement code",
        "measurement": "sum of logical file byte lengths; excludes directory entries and filesystem allocation overhead",
        "mb_definition": "1 MB = 1,000,000 bytes",
        "total_bytes": totals["bytes"],
        "total_mb": totals["mb"],
        "file_count": totals["file_count"],
        "categories": {category: _totals([item for item in files if item["category"] == category]) for category in CATEGORIES},
        "application_raw": {
            **_totals([item for item in files if item["application_payload"]]),
            "scope": "frontend/src and frontend/public; frontend entry/build manifests; backend production source/config; AR model assets; dynamically imported designs tracking source",
            "excluded_support": "documentation, tests, measurement tools, standalone target/reference photos and printing assets",
            "categories": {category: _totals([item for item in files if item["application_payload"] and item["category"] == category]) for category in CATEGORIES},
        },
        "repository_support": _totals([item for item in files if not item["application_payload"]]),
        "by_top_level": {
            name: _totals([item for item in files if (item["path"].split("/")[0] if "/" in item["path"] else "(root files)") == name])
            for name in top_levels
        },
        "files": files,
        "exclusions": sorted(exclusions, key=lambda item: item["path"]),
        "errors": errors,
    }


def measure_python_maintainability(project_root, storage=None):
    """Use Radon's MI only for runtime/prototype Python source, if installed.

    Per-file scores are primary. The mean and median are descriptive summaries
    of those Python files; they are not a whole-application MI and do not cover
    JavaScript/JSX, CSS, tests or measurement tools.
    """
    root = Path(project_root).resolve(strict=True)
    storage = measure_storage(root) if storage is None else storage
    source = [item for item in storage["files"] if item["category"] == "source_code" and item["application_payload"]]
    python_files = [item for item in source if Path(item["path"]).suffix.lower() == ".py"]
    omitted = Counter(Path(item["path"]).suffix.lower() for item in source if Path(item["path"]).suffix.lower() != ".py")
    report = {
        "status": "unavailable",
        "language": "Python only",
        "method": "Radon mi_visit(source, multi=True), per-file 0-100 Maintainability Index",
        "aggregation": "unweighted mean and median of successfully analyzed Python files; no whole-application score",
        "scope": "application_raw Python source_code files; excludes tests and measurement tooling",
        "score_0_100": None,
        "mean_score_0_100": None,
        "median_score_0_100": None,
        "coverage": {
            "python_files_eligible": len(python_files),
            "python_files_analyzed": 0,
            "non_python_source_files_not_analyzed": sum(omitted.values()),
            "non_python_source_extensions_not_analyzed": dict(sorted(omitted.items())),
            "frontend_javascript_jsx_covered": False,
        },
        "files": [],
        "errors": [],
        "radon_version": None,
    }
    try:
        radon_metrics = importlib.import_module("radon.metrics")
    except ImportError as error:
        report["reason"] = "Radon is not available in this Python environment; no MI score was calculated."
        report["dependency_error"] = str(error)
        return report
    try:
        report["radon_version"] = metadata.version("radon")
    except metadata.PackageNotFoundError:
        pass
    for item in python_files:
        try:
            # Python's documented encoding declarations are honored by Radon
            # through tokenize.open; UTF-8 is not assumed for all source files.
            import tokenize
            with tokenize.open(root / item["path"]) as source_file:
                score = float(radon_metrics.mi_visit(source_file.read(), multi=True))
            if not math.isfinite(score) or not 0 <= score <= 100:
                raise ValueError("Radon returned an invalid 0-100 MI score")
            report["files"].append({"path": item["path"], "score_0_100": score})
        except (OSError, SyntaxError, UnicodeError, ValueError, TypeError) as error:
            report["errors"].append({"path": item["path"], "reason": str(error)})
    scores = [item["score_0_100"] for item in report["files"]]
    report["coverage"]["python_files_analyzed"] = len(scores)
    if scores:
        report["status"] = "partial" if report["errors"] or storage["errors"] else "measured"
        report["mean_score_0_100"] = mean(scores)
        report["median_score_0_100"] = median(scores)
        report["reason"] = "Python-only MI; frontend JavaScript/JSX has not been measured."
    else:
        report["status"] = "unavailable" if report["errors"] else "not_applicable"
        report["reason"] = "No eligible Python source files were successfully analyzed."
    return report


def collect_static_metrics(project_root):
    """Collect both static measurements against the same source inventory."""
    storage = measure_storage(project_root)
    return {"storage": storage, "maintainability": measure_python_maintainability(project_root, storage)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="JSON report destination; stdout if omitted")
    args = parser.parse_args()
    result = collect_static_metrics(args.project_root)
    output = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
