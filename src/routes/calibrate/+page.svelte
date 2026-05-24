<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import type { Map as LMap, TileLayer, Marker } from 'leaflet';
  import { solveAffine2D, applyAffine } from '$lib/calc/affine';

  // Natural PDF pixel size (must match what align_to_osm.py uses).
  const PDF_W = 3580;
  const PDF_H = 1870;

  type Pair = {
    pdf: [number, number] | null;       // pixel coords in PDF (natural size)
    map: [number, number] | null;       // [lng, lat]
  };
  let pairs = $state<Pair[]>([{ pdf: null, map: null }]);
  let next = $derived(pairs[pairs.length - 1]);
  // Step: which side to click for the active pair (the last one).
  let step = $derived<'pdf' | 'map' | 'done'>(
    next?.pdf == null ? 'pdf' : next.map == null ? 'map' : 'done'
  );

  const complete = $derived(pairs.filter((p) => p.pdf && p.map));

  function addPair() {
    if (next?.pdf && next?.map) pairs = [...pairs, { pdf: null, map: null }];
  }

  function undo() {
    if (!next) return;
    if (next.map != null) { next.map = null; pairs = pairs; return; }
    if (next.pdf != null) { next.pdf = null; pairs = pairs; return; }
    if (pairs.length > 1) { pairs = pairs.slice(0, -1); }
  }

  function reset() { pairs = [{ pdf: null, map: null }]; refreshOverlays(); }

  // ── PDF pane ────────────────────────────────────────────────────────────
  let pdfImg: HTMLImageElement;
  let pdfWrap: HTMLDivElement;

  function onPdfClick(ev: MouseEvent) {
    if (step !== 'pdf') return;
    const r = pdfImg.getBoundingClientRect();
    const fx = (ev.clientX - r.left) / r.width;
    const fy = (ev.clientY - r.top) / r.height;
    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return;
    const idx = pairs.length - 1;
    pairs[idx] = { ...pairs[idx], pdf: [fx * PDF_W, fy * PDF_H] };
    pairs = pairs;
  }

  // ── Map pane ────────────────────────────────────────────────────────────
  let mapEl: HTMLDivElement;
  let map: LMap;
  let L: typeof import('leaflet');
  let tile: TileLayer | null = null;
  const mapMarkers: Marker[] = [];
  // Markers drawn on top of the PDF image (DOM dots).
  let pdfDots = $derived(
    pairs
      .map((p, i) => p.pdf ? { n: i + 1, x: p.pdf[0] / PDF_W, y: p.pdf[1] / PDF_H } : null)
      .filter((d): d is { n: number; x: number; y: number } => d != null)
  );

  onMount(async () => {
    L = await import('leaflet');
    await import('leaflet/dist/leaflet.css');
    map = L.map(mapEl, { zoomControl: true });
    map.setView([52.0747, 5.1178], 18);
    tile = L.tileLayer(
      'https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg',
      { attribution: '© Beeldmateriaal.nl / PDOK', maxZoom: 19 }
    ).addTo(map);
    tile.on('tileload', (e: any) => { e.tile.style.opacity = '1'; });

    map.on('click', (e: any) => {
      if (step !== 'map') return;
      const idx = pairs.length - 1;
      pairs[idx] = { ...pairs[idx], map: [e.latlng.lng, e.latlng.lat] };
      pairs = pairs;
      drawMapMarker(idx + 1, e.latlng);
    });
    requestAnimationFrame(() => map.invalidateSize());
  });

  function drawMapMarker(n: number, latlng: any) {
    const icon = L.divIcon({
      className: 'cal-pin',
      html: `<div>${n}</div>`,
      iconSize: [30, 30], iconAnchor: [15, 15]
    });
    mapMarkers.push(L.marker(latlng, { icon }).addTo(map));
  }

  function refreshOverlays() {
    for (const m of mapMarkers) m.remove();
    mapMarkers.length = 0;
  }

  onDestroy(() => map?.remove());

  // ── Transform output ────────────────────────────────────────────────────
  let transform = $derived.by(() => {
    if (complete.length < 3) return null;
    const src = complete.map((p) => p.pdf!);
    const dst = complete.map((p) => p.map!);
    const t = solveAffine2D(src, dst);
    // Per-point residual in meters (rough deg->m at this latitude).
    const resM = complete.map((p, i) => {
      const [fx, fy] = applyAffine(t, p.pdf![0], p.pdf![1]);
      const dx = (fx - p.map![0]) * 111_000 * Math.cos((p.map![1] * Math.PI) / 180);
      const dy = (fy - p.map![1]) * 111_000;
      return Math.sqrt(dx * dx + dy * dy);
    });
    return {
      coefficients: t,
      maxResidualM: Math.max(...resM),
      perPointM: resM
    };
  });

  let copied = $state(false);
  async function copyJson() {
    if (!transform) return;
    const blob = {
      pdf_natural_size: [PDF_W, PDF_H],
      pairs: complete.map((p, i) => ({
        n: i + 1,
        pdf_px: p.pdf,
        map_lnglat: p.map
      })),
      affine_pdfpx_to_lnglat: transform.coefficients,
      max_residual_m: transform.maxResidualM
    };
    await navigator.clipboard?.writeText(JSON.stringify(blob, null, 2));
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }
</script>

<main class="cal">
  <header>
    <h1>Calibrate</h1>
    <p>
      Pair {pairs.length} —
      {#if step === 'pdf'}<strong>click on the PDF</strong> first{/if}
      {#if step === 'map'}<strong>now click the same spot on the satellite</strong>{/if}
      {#if step === 'done'}pair captured — press “Add pair” for more, or copy the transform{/if}
      &nbsp;· {complete.length}/4+ pairs (need at least 3)
    </p>
    <div class="actions">
      <button type="button" onclick={addPair} disabled={step !== 'done'}>Add pair</button>
      <button type="button" onclick={undo} disabled={!next?.pdf && pairs.length === 1}>Undo</button>
      <button type="button" onclick={reset}>Reset</button>
      <button type="button" onclick={copyJson} disabled={!transform}>{copied ? 'Copied!' : 'Copy transform JSON'}</button>
    </div>
    {#if transform}
      <p class="muted">max residual: {transform.maxResidualM.toFixed(1)} m
        ({transform.perPointM.map((m) => m.toFixed(1)).join(', ')} m)
      </p>
    {/if}
  </header>

  <div class="pane pdf" bind:this={pdfWrap}>
    <img bind:this={pdfImg}
         src="{base}/data/design-plan-calibrate.jpg"
         alt="Design PDF"
         onclick={onPdfClick}
         class:armed={step === 'pdf'}
         draggable="false" />
    {#each pdfDots as d}
      <span class="pdf-dot" style="left:{d.x * 100}%; top:{d.y * 100}%">{d.n}</span>
    {/each}
  </div>

  <div class="pane map" bind:this={mapEl}></div>
</main>

<style>
  :global(html, body) { margin: 0; padding: 0; height: 100%; background: #111; color: #eee; font: 14px/1.4 -apple-system, system-ui, sans-serif; }
  .cal {
    display: grid;
    grid-template-rows: auto 1fr 1fr;
    height: 100dvh;
  }
  header {
    padding: 8px 14px;
    background: #181a1d;
    border-bottom: 1px solid #2a2d31;
  }
  header h1 { margin: 0 0 2px; font-size: 16px; }
  header p { margin: 2px 0; font-size: 13px; }
  header .actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  header button {
    padding: 6px 10px;
    background: #222528;
    color: #e6e8eb;
    border: 1px solid #3a3d41;
    border-radius: 5px;
    font: inherit;
    cursor: pointer;
  }
  header button:disabled { opacity: 0.4; cursor: not-allowed; }
  header .muted { color: #999; font-size: 12px; }
  .pane { position: relative; overflow: hidden; background: #000; }
  .pane.pdf { background: #fff; }
  .pane.pdf img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    user-select: none;
    -webkit-user-select: none;
    cursor: crosshair;
  }
  .pane.pdf img:not(.armed) { cursor: default; }
  .pdf-dot {
    position: absolute;
    transform: translate(-50%, -50%);
    width: 26px; height: 26px;
    border-radius: 50%;
    background: #dc1d3a;
    color: #fff;
    text-align: center;
    line-height: 26px;
    font-weight: 700;
    border: 3px solid #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.5);
    pointer-events: none;
  }
  :global(.cal-pin > div) {
    width: 30px; height: 30px;
    border-radius: 50%;
    background: #dc1d3a;
    color: #fff;
    text-align: center;
    line-height: 30px;
    font-weight: 700;
    border: 3px solid #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.5);
  }
  @media (min-width: 900px) {
    .cal { grid-template-rows: auto 1fr; grid-template-columns: 1fr 1fr; }
    header { grid-column: 1 / -1; }
  }
</style>
