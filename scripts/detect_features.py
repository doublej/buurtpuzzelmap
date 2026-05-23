"""Detect features in the design PDF render via color thresholding + clustering.

Per the legend:
- Blue dashes (blauwe streepjes) = fietsnietjes (bike hoops).
  Each dash represents one rack (= 2 bikes capacity).
- Green circles (with overlapping darker green) = trees. The text mentions
  7 new trees added, 4 transplanted, 2 cut.
- Yellow shading marks the redesign zone.

Strategy: filter pixels by RGB, dilate/erode to clean up, connected-component
label, split clusters where blobs merged multiple dashes, drop noise.

Outputs:
- static/data/bike_parking_detected.geojson
- static/data/trees_detected.geojson
- static/data/design-plan-cropped.png is the reference image
- debug_*.png overlays
"""

import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "static/data/design-plan-cropped.png"
ROADS = ROOT / "static/data/roads.geojson"
OUT = ROOT / "static/data"
DEBUG = ROOT


def haversine_m(a, b):
    R = 6_371_000.0
    p1 = math.radians(a[1])
    p2 = math.radians(b[1])
    dp = math.radians(b[1] - a[1])
    dl = math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def nearest_street_name(lon: float, lat: float, roads_index) -> str | None:
    best_name = None
    best_d = float("inf")
    for name, coords_list in roads_index.items():
        for coords in coords_list:
            for c in coords:
                d = haversine_m((lon, lat), c)
                if d < best_d:
                    best_d = d
                    best_name = name
    return best_name


def load_roads_by_name():
    fc = json.loads(ROADS.read_text())
    by_name: dict[str, list[list[tuple]]] = {}
    for f in fc["features"]:
        name = (f["properties"] or {}).get("name")
        if not name:
            continue
        coords = [tuple(c) for c in f["geometry"]["coordinates"]]
        by_name.setdefault(name, []).append(coords)
    return by_name

# Geographic bounds the cropped PNG covers (matches DEFAULT_PDF_BOUNDS in state)
SOUTH, NORTH = 52.07320, 52.07620
WEST, EAST = 5.11530, 5.12030


def detect_blue_dashes(img_arr: np.ndarray) -> np.ndarray:
    r = img_arr[:, :, 0].astype(int)
    g = img_arr[:, :, 1].astype(int)
    b = img_arr[:, :, 2].astype(int)
    # The fietsnietjes have a saturated mid-blue (mean ~71/112/171 from sampling).
    # Allow some range but keep clearly-blue pixels only.
    mask = (
        (b > 130)
        & (r < 110)
        & (g < 145)
        & (b - r > 45)
        & (b - g > 25)
    )
    # Cleanup: dilate then erode to merge thin gaps within a single dash
    mask = ndimage.binary_dilation(mask, iterations=1)
    mask = ndimage.binary_erosion(mask, iterations=1)
    return mask


def cluster_marks(mask: np.ndarray) -> list[tuple[int, int, int]]:
    """Return list of (row, col, area_px) for each connected blue region."""
    labels, n = ndimage.label(mask)
    centroids = ndimage.center_of_mass(mask, labels, range(1, n + 1))
    sizes = ndimage.sum(mask, labels, range(1, n + 1)).astype(int)
    out = []
    for (row, col), area in zip(centroids, sizes):
        out.append((int(round(row)), int(round(col)), int(area)))
    return out


def filter_dashes(marks: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    # Reject tiny noise (a few stray blue pixels) and very large blobs (text).
    # An individual fietsnietje dash is ~30×5 px = ~150 px².
    return [(r, c, a) for r, c, a in marks if 6 <= a <= 600]


def split_clustered_dashes(marks, mask):
    """Where blob is wider than a single dash (~6-8 px), split it back into individual dashes.

    Several adjacent dashes can get merged into one blob by the dilation step.
    For each blob, count the horizontal extent / typical dash spacing to split.
    """
    from scipy import ndimage as nd
    labels, n = nd.label(mask)
    new_marks = []
    for label_id in range(1, n + 1):
        ys, xs = np.where(labels == label_id)
        if len(xs) == 0:
            continue
        area = len(xs)
        if not (6 <= area <= 1200):
            continue
        w_ext = xs.max() - xs.min() + 1
        h_ext = ys.max() - ys.min() + 1
        # Typical dash: ~5–8 px wide, ~15–35 tall
        dash_w = 8
        n_dashes = max(1, round(w_ext / (dash_w * 1.6)))
        if n_dashes == 1:
            new_marks.append((int(ys.mean()), int(xs.mean()), area))
        else:
            # Split by x-quantiles
            xs_sorted = np.sort(xs)
            slices = np.array_split(xs_sorted, n_dashes)
            for s in slices:
                xmid = int(s.mean())
                # Find ys for this x range
                mask_slice = (xs >= s.min()) & (xs <= s.max())
                if mask_slice.sum() == 0:
                    continue
                ymid = int(ys[mask_slice].mean())
                new_marks.append((ymid, xmid, len(s)))
    return new_marks


def pixel_to_lonlat(row: int, col: int, w: int, h: int) -> tuple[float, float]:
    fx = col / w  # 0 = west, 1 = east
    fy = row / h  # 0 = north, 1 = south
    lon = WEST + fx * (EAST - WEST)
    lat = NORTH - fy * (NORTH - SOUTH)
    return lon, lat


def save_debug_overlay(img_arr: np.ndarray, marks: list, path: Path) -> None:
    pil = Image.fromarray(img_arr).convert("RGB")
    draw = ImageDraw.Draw(pil)
    for row, col, _ in marks:
        draw.ellipse([col - 10, row - 10, col + 10, row + 10], outline=(255, 0, 0), width=2)
    pil.save(path)


def detect_tree_circles(img_arr: np.ndarray) -> np.ndarray:
    """Detect green tree circles.

    Trees in the design are drawn as green-ish circles ~25–50 px diameter.
    The fill is a mid green; existing trees in the aerial below are darker.
    """
    r = img_arr[:, :, 0].astype(int)
    g = img_arr[:, :, 1].astype(int)
    b = img_arr[:, :, 2].astype(int)
    mask = (g > 110) & (g - r > 25) & (g - b > 25) & (g < 220)
    mask = ndimage.binary_opening(mask, iterations=1)
    mask = ndimage.binary_closing(mask, iterations=2)
    return mask


def filter_trees(marks):
    # Tree symbols are roughly 400–3000 px² (circles 20–60 px diameter)
    return [(r, c, a) for r, c, a in marks if 250 <= a <= 4000]


def main() -> None:
    arr = np.array(Image.open(IMG))
    h, w = arr.shape[:2]

    # ── bike racks (blue dashes) ───────────────────────────────────────────
    mask = detect_blue_dashes(arr)
    raw = cluster_marks(mask)
    keep = split_clustered_dashes(raw, mask)
    print(f"raw blue components: {len(raw)}, after split: {len(keep)}")

    # Look up nearest street name for each detected rack so tooltips are useful
    roads_index = load_roads_by_name()

    feats = []
    for i, (row, col, area) in enumerate(keep):
        lon, lat = pixel_to_lonlat(row, col, w, h)
        street = nearest_street_name(lon, lat, roads_index)
        feats.append({
            "type": "Feature",
            "id": f"bp-detect-{i}",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "kind": "bike",
                "capacity": 2,
                "source": "pdf_detected",
                "street": street,
                "pixel_area": area,
                "px": [col, row]
            }
        })
    (OUT / "bike_parking_detected.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"wrote {len(feats)} bike racks → bike_parking_detected.geojson")

    # Debug overlays for bikes
    Image.fromarray((mask * 255).astype(np.uint8)).save(DEBUG / "debug_bike_mask.png")
    save_debug_overlay(arr, keep, DEBUG / "debug_bike_overlay.png")

    # ── trees (green circles) ─────────────────────────────────────────────
    tmask = detect_tree_circles(arr)
    traw = cluster_marks(tmask)
    tkeep = filter_trees(traw)
    print(f"raw green components: {len(traw)}, after size filter: {len(tkeep)}")
    tfeats = []
    for i, (row, col, area) in enumerate(tkeep):
        lon, lat = pixel_to_lonlat(row, col, w, h)
        tfeats.append({
            "type": "Feature",
            "id": f"tree-{i}",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "kind": "tree",
                "source": "pdf_detected",
                "pixel_area": area,
                "px": [col, row]
            }
        })
    (OUT / "trees_detected.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": tfeats}))
    print(f"wrote {len(tfeats)} trees → trees_detected.geojson")
    Image.fromarray((tmask * 255).astype(np.uint8)).save(DEBUG / "debug_tree_mask.png")


if __name__ == "__main__":
    main()
