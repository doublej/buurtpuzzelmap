"""Convert raw Overpass JSON to clean GeoJSON layers.

Outputs to static/data/:
- roads.geojson         (LineString features, walkable highways)
- buildings.geojson     (Polygon features, with addr:* tags rolled up)
- addresses.geojson     (Point features, all addr:housenumber nodes)
- bike_parking.geojson  (Point features, amenity=bicycle_parking)
- car_parking.geojson   (mixed geometry, amenity=parking)
- meta.json             (bbox + counts)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "static/data/osm-raw.json"
OUT = ROOT / "static/data"

WALKABLE = {
    "residential", "living_street", "pedestrian", "footway",
    "path", "service", "unclassified", "tertiary", "secondary",
    "primary", "cycleway", "track", "steps"
}

def main() -> None:
    raw = json.loads(SRC.read_text())
    nodes = {e["id"]: e for e in raw["elements"] if e["type"] == "node"}
    ways = [e for e in raw["elements"] if e["type"] == "way"]

    roads, buildings, addresses, bike, car = [], [], [], [], []

    for n in nodes.values():
        tags = n.get("tags") or {}
        if "addr:housenumber" in tags:
            addresses.append({
                "type": "Feature",
                "id": f"n{n['id']}",
                "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
                "properties": {
                    "street": tags.get("addr:street"),
                    "housenumber": tags.get("addr:housenumber"),
                    "postcode": tags.get("addr:postcode"),
                    "city": tags.get("addr:city")
                }
            })
        if tags.get("amenity") == "bicycle_parking":
            bike.append({
                "type": "Feature",
                "id": f"n{n['id']}",
                "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
                "properties": {
                    "capacity": _int(tags.get("capacity")),
                    "covered": tags.get("covered"),
                    "source": "osm"
                }
            })
        if tags.get("amenity") == "parking":
            car.append({
                "type": "Feature",
                "id": f"n{n['id']}",
                "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
                "properties": {
                    "capacity": _int(tags.get("capacity")),
                    "access": tags.get("access"),
                    "fee": tags.get("fee"),
                    "source": "osm"
                }
            })

    for w in ways:
        tags = w.get("tags") or {}
        coords = [[nodes[nid]["lon"], nodes[nid]["lat"]] for nid in w["nodes"] if nid in nodes]
        if len(coords) < 2:
            continue
        highway = tags.get("highway")
        if highway:
            roads.append({
                "type": "Feature",
                "id": f"w{w['id']}",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "highway": highway,
                    "name": tags.get("name"),
                    "walkable": highway in WALKABLE,
                    "oneway": tags.get("oneway"),
                    "maxspeed": tags.get("maxspeed")
                }
            })
        if "building" in tags:
            # close polygon
            poly = coords if coords[0] == coords[-1] else coords + [coords[0]]
            buildings.append({
                "type": "Feature",
                "id": f"w{w['id']}",
                "geometry": {"type": "Polygon", "coordinates": [poly]},
                "properties": {
                    "building": tags.get("building"),
                    "street": tags.get("addr:street"),
                    "housenumber": tags.get("addr:housenumber"),
                    "postcode": tags.get("addr:postcode"),
                    "levels": _int(tags.get("building:levels"))
                }
            })
        if tags.get("amenity") == "parking":
            poly = coords if coords[0] == coords[-1] else coords + [coords[0]]
            car.append({
                "type": "Feature",
                "id": f"w{w['id']}",
                "geometry": {"type": "Polygon", "coordinates": [poly]},
                "properties": {
                    "capacity": _int(tags.get("capacity")),
                    "parking": tags.get("parking"),
                    "access": tags.get("access"),
                    "source": "osm"
                }
            })

    _write("roads.geojson", roads)
    _write("buildings.geojson", buildings)
    _write("addresses.geojson", addresses)
    _write("bike_parking.geojson", bike)
    _write("car_parking.geojson", car)

    meta = {
        "bbox": [5.1155, 52.0735, 5.1205, 52.0762],
        "center": [5.1180, 52.0748],
        "counts": {
            "roads": len(roads),
            "buildings": len(buildings),
            "addresses": len(addresses),
            "bike_parking_osm": len(bike),
            "car_parking_osm": len(car)
        }
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta["counts"], indent=2))


def _int(v):
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _write(name: str, features: list) -> None:
    (OUT / name).write_text(json.dumps({
        "type": "FeatureCollection",
        "features": features
    }))


if __name__ == "__main__":
    sys.exit(main() or 0)
