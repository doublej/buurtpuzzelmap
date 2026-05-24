"""Bake the PDF→world affine transform produced by /calibrate into the
PDF-derived GeoJSONs (bike racks, trees, car spots). Two paths to invoke:

  uv run scripts/align_to_osm.py path/to/calibration.json
  pbpaste | uv run scripts/align_to_osm.py -

The JSON shape is whatever the calibrate page writes to the clipboard.
Each feature's [lng, lat] in the targets is recomputed by inverting the
*old* linear bounds (used to emit it) back to PDF px, then applying the
new affine. Existing files are rewritten in place.
"""

import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static" / "data"
TRANSFORM_FILE = ROOT / "scripts" / "pdf_transform.json"

# Only files emitted in raw PDF-pixel space go here. car_parking_design.geojson
# is excluded — expand_design.py snaps those to OSM road centerlines, so the
# coordinates are already in real-world space and applying the PDF→world
# affine on top would double-correct them.
TARGETS = [
    STATIC / "bike_parking_design.geojson",
    STATIC / "bike_parking_detected.geojson",
    STATIC / "trees_detected.geojson",
]

# Original PDF -> world linear map used by detect_features.py to emit the
# current GeoJSON coords. Used to back-project lng/lat -> px before applying
# the corrected affine.
SOUTH, NORTH = 52.07320, 52.07620
WEST, EAST = 5.11530, 5.12030
PNG_W, PNG_H = 3580, 1870


def lnglat_to_px(lng, lat):
    fx = (lng - WEST) / (EAST - WEST)
    fy = (NORTH - lat) / (NORTH - SOUTH)
    return fx * PNG_W, fy * PNG_H


def apply_affine(coeffs, x, y):
    a, b, c, d, tx, ty = coeffs
    return a * x + b * y + tx, c * x + d * y + ty


def load_calibration(arg: str):
    if arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(arg).read_text()
    return json.loads(raw)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: align_to_osm.py <calibration.json | ->")
    cal = load_calibration(sys.argv[1])
    coeffs = cal.get("affine_pdfpx_to_lnglat")
    if not coeffs or len(coeffs) != 6:
        raise SystemExit("calibration JSON missing affine_pdfpx_to_lnglat[6]")

    # Sanity: residuals from the page if present
    if "max_residual_m" in cal:
        print(f"max residual at fit time: {cal['max_residual_m']:.1f} m")

    TRANSFORM_FILE.write_text(json.dumps(cal, indent=2))
    print(f"wrote {TRANSFORM_FILE.relative_to(ROOT)}")

    for path in TARGETS:
        if not path.exists():
            print(f"skip (missing): {path.name}")
            continue
        fc = json.loads(path.read_text())
        n = 0
        for f in fc.get("features", []):
            geom = f.get("geometry") or {}
            if geom.get("type") != "Point":
                continue
            lng, lat = geom["coordinates"][:2]
            px, py = lnglat_to_px(lng, lat)
            new_lng, new_lat = apply_affine(coeffs, px, py)
            geom["coordinates"] = [new_lng, new_lat]
            n += 1
        path.write_text(json.dumps(fc))
        print(f"rewrote {path.name}: {n} points")


if __name__ == "__main__":
    main()
