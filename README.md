# Buurtpuzzelmap

Interactive map of the *Ontwerp Buurtpuzzel laatste fase* (final-phase neighborhood
puzzle design) for **Rivierenwijk, Utrecht** — Mijdrechtstraat, Alblasstraat,
Nieuwravenstraat, Volkerakstraat and Runstraat.

Overlays the design PDF on real OpenStreetMap geometry, models bike racks
(*fietsnietjes*) and car parking spots from the design, and computes the
nearest spot per address + projected demand vs. capacity per spot using
configurable household-size defaults.

## Run locally

```sh
bun install
bun run dev
```

## Rebuild the data

```sh
python3 scripts/process_osm.py    # raw OSM → clean GeoJSON layers
python3 scripts/expand_design.py  # design_config.json → parking points
```

The Overpass query is in `scripts/process_osm.py`; rerun by re-fetching
`static/data/osm-raw.json` first (see top of the file for the query).

## Layers

- **Roads / Buildings / Addresses / Bike parking / Car parking** — OSM via
  Overpass.
- **Bike racks (design) / Car spots (design)** — interpolated along OSM road
  centerlines using counts and segments declared in
  `static/data/design_config.json`. Edit that JSON and rerun
  `expand_design.py` to refine.
- **Design PDF** — `static/data/design-plan-cropped.png` overlaid with editable
  bounds + rotation (saved per browser via localStorage).

## Calculations

- Each address is assigned to its nearest bike rack and nearest car spot
  using a 1.3× haversine walking-distance approximation.
- Per-address demand = `households × persons/HH × bikes/person` for bikes,
  `households × cars/HH` for cars. Defaults configurable in the sidebar,
  per-address overrides editable by clicking an address.
- Each spot's *utilization* = assigned demand / capacity. Colored on the map
  (blue → green → yellow → orange → red as utilization climbs past 100%).

## Deploy

GitHub Actions builds on push to `main` and publishes to GitHub Pages
(see `.github/workflows/deploy.yml`).
