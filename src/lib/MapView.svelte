<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type { Map as LMap, TileLayer, Layer, LayerGroup, ImageOverlay } from 'leaflet';
  import type { Layers } from '$lib/data/load';
  import { ui, basemaps, results } from '$lib/state.svelte';
  import { base } from '$app/paths';

  interface Props { layers: Layers; }
  let { layers }: Props = $props();

  let mapEl: HTMLDivElement;
  let map: LMap;
  let L: typeof import('leaflet');

  let tileLayer: TileLayer | null = null;
  let pdfOverlay: ImageOverlay | null = null;

  let groupBuildings: LayerGroup;
  let groupRoads: LayerGroup;
  let groupAddresses: LayerGroup;
  let groupBikeOSM: LayerGroup;
  let groupCarOSM: LayerGroup;
  let groupBikeDesign: LayerGroup;
  let groupCarDesign: LayerGroup;
  let ready = $state(false);

  onMount(async () => {
    L = await import('leaflet');
    await import('leaflet/dist/leaflet.css');

    const [w, s, e, n] = layers.meta.bbox;
    const cLat = (s + n) / 2;
    const cLng = (w + e) / 2;

    map = L.map(mapEl, { zoomControl: true, preferCanvas: true });
    map.setView([cLat, cLng], 18);
    map.on('moveend zoomend viewreset', () => applyPDFRotation());

    applyBasemap();
    buildLayers();
    applyPDF();
    bindToggles();
    repaintDesignByLoad();

    // Ensure the container has its real size before final zoom
    requestAnimationFrame(() => {
      map.invalidateSize();
      map.fitBounds([[s, w], [n, e]], { padding: [40, 380] });
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

  function applyPDF() {
    if (pdfOverlay) { pdfOverlay.remove(); pdfOverlay = null; }
    if (!ui.showPDF) return;
    const b = ui.pdfBounds;
    pdfOverlay = L.imageOverlay(`${base}/data/design-plan-cropped.png`, [
      [b.south, b.west],
      [b.north, b.east]
    ], { opacity: ui.pdfOpacity, interactive: false }).addTo(map);
    if (tileLayer) tileLayer.bringToBack();
    pdfOverlay.bringToBack();
    if (tileLayer) tileLayer.bringToBack();
    applyPDFRotation();
  }

  function applyPDFRotation() {
    if (!pdfOverlay) return;
    const el = pdfOverlay.getElement() as HTMLImageElement | undefined;
    if (!el) return;
    const r = ui.pdfRotation || 0;
    // Strip any rotation we previously added; only append if non-zero so we
    // don't fight Leaflet's own transform updates during pan/zoom.
    const existing = el.style.transform.replace(/\s*rotate\([^)]*\)/g, '').trim();
    if (r === 0) {
      el.style.transform = existing;
      return;
    }
    el.style.transformOrigin = 'center center';
    el.style.transform = `${existing} rotate(${r}deg)`.trim();
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
          .bindTooltip(`${a.street} ${a.housenumber}`, { direction: 'top' })
          .on('click', () => { ui.selectedAddressId = a.id; ui.selectedSpotId = null; })
      )
    );

    groupBikeOSM = L.geoJSON(layers.bikeOSM as any, {
      pointToLayer: (_f: any, ll: any) =>
        L.circleMarker(ll, { radius: 4, color: '#04c', fillColor: '#7af', fillOpacity: 0.9 })
    });
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
          .bindTooltip(`bike rack · ${s.street} (${s.side})`, { direction: 'top' })
          .on('click', () => { ui.selectedSpotId = s.id; ui.selectedAddressId = null; })
      )
    );

    groupCarDesign = L.layerGroup(
      layers.carDesign.map((s) =>
        L.circleMarker([s.lat, s.lng], {
          radius: 5, color: '#7a2900', weight: 1, fillColor: '#f96', fillOpacity: 0.95
        })
          .bindTooltip(`car spot · ${s.street} (${s.side})`, { direction: 'top' })
          .on('click', () => { ui.selectedSpotId = s.id; ui.selectedAddressId = null; })
      )
    );
  }

  function bindToggles() {
    syncLayer(groupBuildings, ui.showBuildings);
    syncLayer(groupRoads, ui.showRoads);
    syncLayer(groupAddresses, ui.showAddresses);
    syncLayer(groupBikeOSM, ui.showBikeOSM);
    syncLayer(groupCarOSM, ui.showCarOSM);
    syncLayer(groupBikeDesign, ui.showBikeDesign);
    syncLayer(groupCarDesign, ui.showCarDesign);
  }

  function syncLayer(layer: Layer | null, visible: boolean) {
    if (!layer || !map) return;
    if (visible && !map.hasLayer(layer)) layer.addTo(map);
    if (!visible && map.hasLayer(layer)) map.removeLayer(layer);
  }

  $effect(() => { if (ready) applyBasemap(); });
  $effect(() => {
    if (!ready) return;
    void ui.pdfBounds.north; void ui.pdfBounds.south; void ui.pdfBounds.east; void ui.pdfBounds.west;
    void ui.pdfOpacity; void ui.showPDF;
    applyPDF();
  });

  $effect(() => {
    if (!ready) return;
    void ui.pdfRotation;
    applyPDFRotation();
  });
  $effect(() => {
    if (!ready) return;
    syncLayer(groupBuildings, ui.showBuildings);
    syncLayer(groupRoads, ui.showRoads);
    syncLayer(groupAddresses, ui.showAddresses);
    syncLayer(groupBikeOSM, ui.showBikeOSM);
    syncLayer(groupCarOSM, ui.showCarOSM);
    syncLayer(groupBikeDesign, ui.showBikeDesign);
    syncLayer(groupCarDesign, ui.showCarDesign);
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
      (lyr as any).setStyle({ fillColor: utilToColor(util) });
    });
    let j = 0;
    groupCarDesign.eachLayer((lyr) => {
      const s = layers.carDesign[j++];
      const util = carById.get(s.id)?.utilization ?? 0;
      (lyr as any).setStyle({ fillColor: utilToColor(util) });
    });
  }

  function utilToColor(util: number): string {
    if (util === 0) return '#cde';
    if (util < 0.5) return '#3c9';
    if (util < 1) return '#fc3';
    if (util < 1.5) return '#f73';
    return '#c22';
  }

  onDestroy(() => { map?.remove(); });
</script>

<div bind:this={mapEl} class="map"></div>

<style>
  .map {
    position: absolute;
    inset: 0;
    background: #eef;
  }
  :global(.leaflet-container) { font: inherit; }
</style>
