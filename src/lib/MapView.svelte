<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type { Map as LMap, TileLayer, Layer, LayerGroup } from 'leaflet';
  import type { Layers } from '$lib/data/load';
  import { ui, basemaps, results } from '$lib/state.svelte';

  interface Props { layers: Layers; }
  let { layers }: Props = $props();

  let mapEl: HTMLDivElement;
  let map: LMap;
  let L: typeof import('leaflet');

  let tileLayer: TileLayer | null = null;

  let groupBuildings: LayerGroup;
  let groupRoads: LayerGroup;
  let groupAddresses: LayerGroup;
  let groupCarOSM: LayerGroup;
  let groupBikeDesign: LayerGroup;
  let groupCarDesign: LayerGroup;
  let groupTrees: LayerGroup;
  let ready = $state(false);

  onMount(async () => {
    L = await import('leaflet');
    await import('leaflet/dist/leaflet.css');

    const [w, s, e, n] = layers.meta.bbox;
    const cLat = (s + n) / 2;
    const cLng = (w + e) / 2;

    map = L.map(mapEl, { zoomControl: true, preferCanvas: true });
    map.setView([cLat, cLng], 18);

    // Calibration mode: tap to drop numbered markers and show the lat/lng.
    // Activated with ?calibrate=1 in the URL. The captured points print in the
    // sheet for copying back.
    const isCalibrate = typeof location !== 'undefined' && new URLSearchParams(location.search).get('calibrate') === '1';
    if (isCalibrate) {
      ui.calibrate.active = true;
      map.on('click', (e: any) => {
        if (ui.calibrate.points.length >= 4) return;
        const n = ui.calibrate.points.length + 1;
        const lat = Number(e.latlng.lat.toFixed(6));
        const lng = Number(e.latlng.lng.toFixed(6));
        ui.calibrate.points = [...ui.calibrate.points, { n, lat, lng }];
        L.marker(e.latlng, {
          icon: L.divIcon({
            className: 'cal-marker',
            html: `<div>${n}</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          })
        }).addTo(map);
        ui.sheetOpen = true;
      });
    }

    // Delegate clicks inside popups (the "Edit overrides" link).
    map.on('popupopen', (e: any) => {
      const root: HTMLElement = e.popup.getElement();
      if (!root) return;
      const btn = root.querySelector('[data-action="open-sheet"]') as HTMLButtonElement | null;
      if (btn) {
        btn.addEventListener('click', () => {
          ui.sheetOpen = true;
          map.closePopup();
        }, { once: true });
      }
    });

    applyBasemap();
    buildLayers();
    bindToggles();
    repaintDesignByLoad();

    // Wait for the container to size, then re-center at neighborhood zoom.
    requestAnimationFrame(() => {
      map.invalidateSize();
      map.setView([cLat, cLng], 18, { animate: false });
      ready = true;
    });
  });

  function applyBasemap() {
    if (tileLayer) tileLayer.remove();
    const cfg = basemaps[ui.basemap];
    const opts: any = { attribution: cfg.attribution, maxZoom: cfg.maxZoom };
    if (cfg.subdomains) opts.subdomains = cfg.subdomains;
    tileLayer = L.tileLayer(cfg.url, opts);
    // Cached tiles can land before the load listener attaches, leaving them stuck
    // at opacity 0. Force opacity to 1 after the image is decoded.
    tileLayer.on('tileload', (e: any) => {
      e.tile.style.opacity = '1';
    });
    tileLayer.addTo(map);
    tileLayer.bringToBack();
  }

  function buildLayers() {
    groupBuildings = L.geoJSON(layers.buildings as any, {
      style: { color: '#888', weight: 0.5, fillColor: '#bbb', fillOpacity: 0.25 }
    });
    groupRoads = L.geoJSON(layers.roads as any, {
      style: (f: any) => ({
        color: f.properties.walkable ? '#3a3' : '#999',
        weight: 1.5,
        opacity: 0.6
      })
    });

    groupAddresses = L.layerGroup(
      layers.addresses.map((a) =>
        L.circleMarker([a.lat, a.lng], {
          radius: 3, color: '#222', weight: 0.6, fillColor: '#fff', fillOpacity: 0.9
        })
          .bindPopup(() => addressPopupHTML(a.id), { autoPan: false, closeButton: true })
          .on('click', () => { ui.selectedAddressId = a.id; ui.selectedSpotId = null; })
      )
    );

    groupCarOSM = L.geoJSON(layers.carOSM as any, {
      style: { color: '#a40', weight: 1, fillColor: '#fc6', fillOpacity: 0.4 },
      pointToLayer: (_f: any, ll: any) =>
        L.circleMarker(ll, { radius: 5, color: '#a40', fillColor: '#fc6', fillOpacity: 0.8 })
    });

    groupBikeDesign = L.layerGroup(
      layers.bikeDesign.map((s) =>
        L.circleMarker([s.lat, s.lng], {
          radius: 6, color: '#003e8c', weight: 1.5, fillColor: '#3af', fillOpacity: 0.95
        })
          .bindPopup(() => spotPopupHTML(s.id, 'bike'), { autoPan: false, closeButton: true })
          .on('click', () => { ui.selectedSpotId = s.id; ui.selectedAddressId = null; })
      )
    );

    groupCarDesign = L.layerGroup(
      layers.carDesign.map((s) =>
        L.circleMarker([s.lat, s.lng], {
          radius: 5, color: '#7a2900', weight: 1, fillColor: '#f96', fillOpacity: 0.95
        })
          .bindPopup(() => spotPopupHTML(s.id, 'car'), { autoPan: false, closeButton: true })
          .on('click', () => { ui.selectedSpotId = s.id; ui.selectedAddressId = null; })
      )
    );

    groupTrees = L.layerGroup(
      layers.trees.map((t) =>
        L.circleMarker([t.lat, t.lng], {
          radius: 4, color: '#0a5e1c', weight: 1.5, fillColor: '#3aa64a', fillOpacity: 0.8
        }).bindPopup('Tree (detected from PDF)', { autoPan: false, closeButton: true })
      )
    );
  }

  function addressPopupHTML(id: string): string {
    const a = layers.addresses.find((x) => x.id === id);
    if (!a) return '';
    const asg = results.assignments.find((x) => x.addressId === id);
    const bike = asg ? `${Math.round(asg.nearestBikeMeters)} m` : '—';
    const car = asg ? `${Math.round(asg.nearestCarMeters)} m` : '—';
    return `<div class="pp">
      <strong>${esc(a.street)} ${esc(a.housenumber)}</strong>
      <table>
        <tr><td>Nearest bike rack</td><td>${bike}</td></tr>
        <tr><td>Nearest car spot</td><td>${car}</td></tr>
      </table>
      <button type="button" class="pp-more" data-action="open-sheet">Edit overrides →</button>
    </div>`;
  }

  function spotPopupHTML(id: string, kind: 'bike' | 'car'): string {
    const s = (kind === 'bike' ? layers.bikeDesign : layers.carDesign).find((x) => x.id === id);
    if (!s) return '';
    const load = (kind === 'bike' ? results.bikeLoad : results.carLoad).find((r) => r.spotId === id);
    const util = load ? `${(load.utilization * 100).toFixed(0)}%` : '—';
    const cap = load?.capacity ?? s.capacity;
    const assigned = load ? load.assigned.toFixed(1) : '—';
    const addr = load?.addresses.length ?? 0;
    const over = load && load.utilization > 1;
    return `<div class="pp">
      <strong>${kind === 'bike' ? 'Bike rack' : 'Car spot'} · ${esc(s.street ?? '')}</strong>
      <table>
        <tr><td>Capacity</td><td>${cap}</td></tr>
        <tr><td>Demand</td><td>${assigned}</td></tr>
        <tr><td>Utilization</td><td${over ? ' class="over"' : ''}>${util}</td></tr>
        <tr><td>Addresses served</td><td>${addr}</td></tr>
      </table>
    </div>`;
  }

  function esc(s: string): string {
    return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
  }

  function bindToggles() {
    syncLayer(groupBuildings, ui.showBuildings);
    syncLayer(groupRoads, ui.showRoads);
    syncLayer(groupAddresses, ui.showAddresses);
    syncLayer(groupCarOSM, ui.showCarOSM);
    syncLayer(groupBikeDesign, ui.showBikeDesign);
    syncLayer(groupCarDesign, ui.showCarDesign);
    syncLayer(groupTrees, ui.showTrees);
  }

  function syncLayer(layer: Layer | null, visible: boolean) {
    if (!layer || !map) return;
    if (visible && !map.hasLayer(layer)) layer.addTo(map);
    if (!visible && map.hasLayer(layer)) map.removeLayer(layer);
  }

  $effect(() => {
    void ui.basemap;
    if (ready) applyBasemap();
  });
  $effect(() => {
    if (!ready) return;
    syncLayer(groupBuildings, ui.showBuildings);
    syncLayer(groupRoads, ui.showRoads);
    syncLayer(groupAddresses, ui.showAddresses);
    syncLayer(groupCarOSM, ui.showCarOSM);
    syncLayer(groupBikeDesign, ui.showBikeDesign);
    syncLayer(groupCarDesign, ui.showCarDesign);
    syncLayer(groupTrees, ui.showTrees);
  });

  $effect(() => {
    void results.bikeLoad; void results.carLoad;
    if (!ready) return;
    repaintDesignByLoad();
  });

  function repaintDesignByLoad() {
    if (!groupBikeDesign || !groupCarDesign) return;
    const bikeById = new Map(results.bikeLoad.map((r) => [r.spotId, r]));
    const carById = new Map(results.carLoad.map((r) => [r.spotId, r]));
    let i = 0;
    groupBikeDesign.eachLayer((lyr) => {
      const s = layers.bikeDesign[i++];
      const util = bikeById.get(s.id)?.utilization ?? 0;
      applyUtilStyle(lyr as any, util, 'bike', 6);
    });
    let j = 0;
    groupCarDesign.eachLayer((lyr) => {
      const s = layers.carDesign[j++];
      const util = carById.get(s.id)?.utilization ?? 0;
      applyUtilStyle(lyr as any, util, 'car', 5);
    });
  }

  function applyUtilStyle(marker: any, util: number, kind: 'bike' | 'car', baseRadius: number) {
    marker.setStyle({ fillColor: utilToColor(util), ...utilToStroke(util, kind) });
    marker.setRadius(utilToRadius(baseRadius, util));
  }

  // Continuous gradient: empty -> green -> yellow at capacity ->
  // orange -> deep red as overload grows. Saturation and darkness
  // both intensify past 100% so heavy overloads read as more severe.
  function utilToColor(util: number): string {
    if (util <= 0) return '#e6ecf2';
    let h: number, s: number, l: number;
    if (util <= 1) {
      const t = util;
      h = 145 - 95 * t;
      s = 55 + 25 * t;
      l = 60 - 5 * t;
    } else {
      const t = Math.min(util - 1, 1.5) / 1.5;
      h = 50 - 50 * t;
      s = 80 + 15 * t;
      l = 55 - 28 * t;
    }
    return `hsl(${h.toFixed(0)} ${s.toFixed(0)}% ${l.toFixed(0)}%)`;
  }

  function utilToRadius(base: number, util: number): number {
    if (util <= 1) return base;
    const over = Math.min(util - 1, 2);
    return base * (1 + over * 0.4);
  }

  function utilToStroke(util: number, kind: 'bike' | 'car') {
    if (util <= 1) {
      return kind === 'bike'
        ? { color: '#003e8c', weight: 1.5 }
        : { color: '#7a2900', weight: 1 };
    }
    if (util < 1.5) return { color: '#8b1a00', weight: 1.5 };
    if (util < 2.5) return { color: '#5a0000', weight: 2 };
    return { color: '#2a0000', weight: 2.5 };
  }

  onDestroy(() => { map?.remove(); });
</script>

<div bind:this={mapEl} class="map"></div>

<style>
  .map {
    position: absolute;
    inset: 0;
    background: #eef;
    touch-action: pan-x pan-y; /* allow Leaflet's own gestures, block browser nav */
  }
  :global(.leaflet-container) {
    font: inherit;
    background: #eef;
  }
  /* Push Leaflet's zoom controls clear of the iOS safe-area + sheet handle */
  :global(.leaflet-top.leaflet-left) {
    top: calc(env(safe-area-inset-top, 0) + 8px);
    left: calc(env(safe-area-inset-left, 0) + 8px);
  }
  :global(.leaflet-control-zoom a) {
    width: 36px !important;
    height: 36px !important;
    line-height: 36px !important;
    font-size: 20px !important;
  }
  @media (max-width: 767px) {
    /* Leave room for the collapsed bottom sheet (~72px) so the attribution
       doesn't disappear under it. Bottom sheet uses bottom inset already. */
    :global(.leaflet-bottom) {
      bottom: calc(72px + env(safe-area-inset-bottom, 0)) !important;
    }
  }
  @media (prefers-color-scheme: dark) {
    .map, :global(.leaflet-container) { background: #1a1c1e; }
  }

  :global(.leaflet-popup-content) {
    margin: 10px 14px;
    font: 13px/1.4 -apple-system, system-ui, sans-serif;
    min-width: 180px;
  }
  :global(.leaflet-popup-content .pp strong) {
    display: block;
    font-size: 14px;
    margin-bottom: 6px;
  }
  :global(.leaflet-popup-content table) {
    border-collapse: collapse;
    width: 100%;
    font-size: 12px;
  }
  :global(.leaflet-popup-content td) {
    padding: 2px 0;
    border-bottom: 1px solid #f0f0f0;
  }
  :global(.leaflet-popup-content td:last-child) {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  :global(.leaflet-popup-content td.over) {
    color: #c22;
    font-weight: 600;
  }
  :global(.leaflet-popup-content .pp-more) {
    appearance: none;
    border: 0;
    background: transparent;
    color: #0a64c8;
    font: inherit;
    font-size: 12px;
    padding: 8px 0 2px;
    cursor: pointer;
    text-align: left;
    width: 100%;
  }
  :global(.cal-marker > div) {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #dc1d3a;
    color: #fff;
    font: 700 14px/28px -apple-system, system-ui, sans-serif;
    text-align: center;
    border: 3px solid #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.4);
  }
  @media (prefers-color-scheme: dark) {
    :global(.leaflet-popup-content-wrapper),
    :global(.leaflet-popup-tip) {
      background: #222528;
      color: #e6e8eb;
    }
    :global(.leaflet-popup-content td) { border-color: #2a2d31; }
    :global(.leaflet-popup-close-button) { color: #aaa !important; }
  }
</style>
