"""Distribute bike racks and car parking along actual OSM street centerlines.

For each segment in design_config.json:
- Find the OSM way(s) matching the street name
- Trim to the configured from/to extent along that street
- Distribute points evenly with perpendicular offset

Writes:
- static/data/bike_parking_design.geojson
- static/data/car_parking_design.geojson
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "static/data/design_config.json"
ROADS = ROOT / "static/data/roads.geojson"
OUT = ROOT / "static/data"

LAT_M = 111_320.0


def haversine_m(a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


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


def merge_ways(ways):
    if not ways:
        return []
    remaining = [list(w) for w in ways]
    path = remaining.pop(0)
    progress = True
    while remaining and progress:
        progress = False
        for i, w in enumerate(remaining):
            if path[-1] == w[0]:
                path.extend(w[1:]); del remaining[i]; progress = True; break
            if path[-1] == w[-1]:
                path.extend(reversed(w[:-1])); del remaining[i]; progress = True; break
            if path[0] == w[-1]:
                path = w[:-1] + path; del remaining[i]; progress = True; break
            if path[0] == w[0]:
                path = list(reversed(w[1:])) + path; del remaining[i]; progress = True; break
    for w in remaining:
        path.extend(w)
    return path


def polyline_length(path):
    return sum(haversine_m(path[i - 1], path[i]) for i in range(1, len(path)))


def slice_between(path, p_from, p_to):
    def nearest_idx(p):
        return min(range(len(path)), key=lambda i: haversine_m(p, path[i]))
    i0 = nearest_idx(p_from); i1 = nearest_idx(p_to)
    if i0 == i1:
        return path
    if i0 < i1:
        return path[i0:i1 + 1]
    return list(reversed(path[i1:i0 + 1]))


def point_and_normal_at(path, t):
    total = polyline_length(path)
    target = total * t
    travelled = 0.0
    for i in range(1, len(path)):
        seg = haversine_m(path[i - 1], path[i])
        if travelled + seg >= target:
            f = (target - travelled) / seg if seg > 0 else 0
            p1 = path[i - 1]; p2 = path[i]
            lon = p1[0] + f * (p2[0] - p1[0])
            lat = p1[1] + f * (p2[1] - p1[1])
            return (lon, lat), p1, p2
        travelled += seg
    return path[-1], path[-2], path[-1]


def perpendicular_offset(p1, p2, offset_m, side):
    lon1, lat1 = p1; lon2, lat2 = p2
    mlat = LAT_M
    mlon = LAT_M * math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * mlon
    dy = (lat2 - lat1) * mlat
    length = math.hypot(dx, dy)
    if length == 0:
        return (0, 0)
    nx, ny = -dy / length, dx / length  # left-of-travel normal
    if side == "north":
        sign = 1 if ny > 0 else -1
    elif side == "south":
        sign = 1 if ny < 0 else -1
    elif side == "east":
        sign = 1 if nx > 0 else -1
    elif side == "west":
        sign = 1 if nx < 0 else -1
    else:
        sign = 1
    return (sign * nx * offset_m / mlon, sign * ny * offset_m / mlat)


def distribute(path, n, offset_m, side):
    if n <= 0 or len(path) < 2:
        return []
    pts = []
    for i in range(n):
        t = (i + 0.5) / n
        center, p1, p2 = point_and_normal_at(path, t)
        dlon, dlat = perpendicular_offset(p1, p2, offset_m, side)
        pts.append((center[0] + dlon, center[1] + dlat))
    return pts


def _feature(seg, kind, suffix, pt):
    capacity = 2 if kind == "bike" else 1
    return {
        "type": "Feature",
        "id": f"{seg['id']}-{suffix}",
        "geometry": {"type": "Point", "coordinates": [pt[0], pt[1]]},
        "properties": {
            "segment_id": seg["id"], "street": seg["street"], "side": seg["side"],
            "kind": kind, "capacity": capacity, "source": "pdf_design"
        }
    }


def expand(seg, kind, roads_by_name):
    name = seg["street"]
    ways = roads_by_name.get(name, [])
    if ways:
        merged = merge_ways(ways)
        path = slice_between(merged, tuple(seg["from"]), tuple(seg["to"]))
        if len(path) < 2:
            path = [tuple(seg["from"]), tuple(seg["to"])]
    else:
        print(f"  ! no OSM road for {name}")
        path = [tuple(seg["from"]), tuple(seg["to"])]

    n = seg["racks" if kind == "bike" else "spots"]
    side = seg["side"]
    feats = []
    if side == "both":
        half = n // 2
        # E-W vs N-S
        horizontal = abs(path[-1][0] - path[0][0]) > abs(path[-1][1] - path[0][1])
        sides = ("north", "south") if horizontal else ("east", "west")
        for sl in sides:
            for i, p in enumerate(distribute(path, half, seg["offset_m"], sl)):
                feats.append(_feature(seg, kind, f"{sl[0]}{i}", p))
    else:
        for i, p in enumerate(distribute(path, n, seg["offset_m"], side)):
            feats.append(_feature(seg, kind, str(i), p))
    return feats


def main():
    cfg = json.loads(CFG.read_text())
    roads = load_roads_by_name()
    bike, car = [], []
    for s in cfg["bike_parking_segments"]:
        bike.extend(expand(s, "bike", roads))
    for s in cfg["car_parking_segments"]:
        car.extend(expand(s, "car", roads))
    # Bike racks now come from detect_features.py (PDF-based), not from
    # interpolating along centerlines. Only car spots stay road-snapped here.
    _w("car_parking_design.geojson", car)
    print(f"car spots:  {len(car)}")


def _w(name, features):
    (OUT / name).write_text(json.dumps({"type": "FeatureCollection", "features": features}))


if __name__ == "__main__":
    main()
