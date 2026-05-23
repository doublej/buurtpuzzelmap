<script lang="ts">
  import type { Layers } from '$lib/data/load';
  import { defaults, overrides, ui, results, basemaps, persistOverrides, persistUI, resetPDFBounds, type BasemapKey } from '$lib/state.svelte';

  interface Props {
    layers: Layers;
  }
  let { layers }: Props = $props();

  const selectedAddress = $derived(
    ui.selectedAddressId
      ? layers.addresses.find((a) => a.id === ui.selectedAddressId) ?? null
      : null
  );

  const selectedSpot = $derived.by(() => {
    if (!ui.selectedSpotId) return null;
    return (
      layers.bikeDesign.find((s) => s.id === ui.selectedSpotId) ??
      layers.carDesign.find((s) => s.id === ui.selectedSpotId) ??
      null
    );
  });

  const selectedAssignment = $derived(
    ui.selectedAddressId
      ? results.assignments.find((x) => x.addressId === ui.selectedAddressId) ?? null
      : null
  );

  const selectedLoad = $derived.by(() => {
    if (!ui.selectedSpotId) return null;
    return (
      results.bikeLoad.find((r) => r.spotId === ui.selectedSpotId) ??
      results.carLoad.find((r) => r.spotId === ui.selectedSpotId) ??
      null
    );
  });

  const totals = $derived.by(() => {
    let bikeCapacity = 0;
    let bikeAssigned = 0;
    for (const r of results.bikeLoad) {
      bikeCapacity += r.capacity;
      bikeAssigned += r.assigned;
    }
    let carCapacity = 0;
    let carAssigned = 0;
    for (const r of results.carLoad) {
      carCapacity += r.capacity;
      carAssigned += r.assigned;
    }
    const overBike = results.bikeLoad.filter((r) => r.utilization > 1).length;
    const overCar = results.carLoad.filter((r) => r.utilization > 1).length;
    return { bikeCapacity, bikeAssigned, carCapacity, carAssigned, overBike, overCar };
  });

  function updateOverride(field: 'households' | 'persons' | 'cars' | 'bikes', value: string) {
    if (!selectedAddress) return;
    const num = value.trim() === '' ? undefined : Number(value);
    const existing = overrides[selectedAddress.id] ?? {};
    if (num === undefined) {
      delete existing[field];
    } else {
      existing[field] = num;
    }
    overrides[selectedAddress.id] = existing;
    persistOverrides();
  }
</script>

<aside class="sidebar" class:open={ui.sheetOpen}>
  <button class="handle" type="button" onclick={() => (ui.sheetOpen = !ui.sheetOpen)} aria-label={ui.sheetOpen ? 'Collapse panel' : 'Expand panel'}>
    <span class="grip"></span>
    <span class="handle-summary">
      <strong>Buurtpuzzelmap</strong>
      <span class="muted">{layers.addresses.length} adressen · {Math.round(totals.bikeAssigned)} fietsen / {totals.bikeCapacity}</span>
    </span>
    <span class="caret" aria-hidden="true">{ui.sheetOpen ? '×' : '☰'}</span>
  </button>

  <div class="scroll">
  <header>
    <h1>Buurtpuzzelmap</h1>
    <p>Rivierenwijk Utrecht — design + parking-load model</p>
  </header>

  <section>
    <h2>Basemap</h2>
    <select bind:value={ui.basemap} onchange={persistUI}>
      {#each Object.entries(basemaps) as [key, cfg]}
        <option value={key as BasemapKey}>{cfg.name}</option>
      {/each}
    </select>
  </section>

  <section>
    <h2>Layers</h2>
    <label><input type="checkbox" bind:checked={ui.showRoads} /> Roads (OSM)</label>
    <label><input type="checkbox" bind:checked={ui.showBuildings} /> Buildings (OSM)</label>
    <label><input type="checkbox" bind:checked={ui.showAddresses} /> Addresses (OSM)</label>
    <label><input type="checkbox" bind:checked={ui.showBikeOSM} /> Bike parking (OSM)</label>
    <label><input type="checkbox" bind:checked={ui.showCarOSM} /> Car parking (OSM)</label>
    <label><input type="checkbox" bind:checked={ui.showBikeDesign} /> Bike racks (design)</label>
    <label><input type="checkbox" bind:checked={ui.showCarDesign} /> Car spots (design)</label>
    <label><input type="checkbox" bind:checked={ui.showTrees} /> Trees (detected from PDF)</label>
  </section>

  <section>
    <h2>PDF overlay</h2>
    <label><input type="checkbox" bind:checked={ui.showPDF} /> Show design PDF</label>
    <label class="range">
      Opacity {ui.pdfOpacity.toFixed(2)}
      <input type="range" min="0" max="1" step="0.05" bind:value={ui.pdfOpacity} onchange={persistUI} />
    </label>
    <label class="range">
      Rotation {ui.pdfRotation.toFixed(1)}°
      <input type="range" min="-15" max="15" step="0.1" bind:value={ui.pdfRotation} onchange={persistUI} />
    </label>
    <details>
      <summary>Align bounds</summary>
      <label class="num">N
        <input type="number" step="0.0001" bind:value={ui.pdfBounds.north} onchange={persistUI} />
      </label>
      <label class="num">S
        <input type="number" step="0.0001" bind:value={ui.pdfBounds.south} onchange={persistUI} />
      </label>
      <label class="num">W
        <input type="number" step="0.0001" bind:value={ui.pdfBounds.west} onchange={persistUI} />
      </label>
      <label class="num">E
        <input type="number" step="0.0001" bind:value={ui.pdfBounds.east} onchange={persistUI} />
      </label>
      <p class="hint">Tweak in steps of ~0.0001 (~10 m) to align the PDF with OSM streets. Saved to your browser.</p>
      <button type="button" onclick={resetPDFBounds}>Reset</button>
    </details>
  </section>

  <section>
    <h2>Household defaults</h2>
    <label class="num">
      Persons / household
      <input type="number" step="0.1" bind:value={defaults.persons_per_hh} />
    </label>
    <label class="num">
      Cars / household
      <input type="number" step="0.05" bind:value={defaults.cars_per_hh} />
    </label>
    <label class="num">
      Bikes / person
      <input type="number" step="0.1" bind:value={defaults.bikes_per_person} />
    </label>
    <p class="hint">CBS-ish defaults. Edit, then individual addresses can be overridden by clicking on the map.</p>
  </section>

  <section>
    <h2>Totals</h2>
    <table>
      <tbody>
        <tr><td>Addresses</td><td>{layers.addresses.length}</td></tr>
        <tr><td>Bike capacity (design)</td><td>{totals.bikeCapacity}</td></tr>
        <tr><td>Bike demand (assigned)</td><td>{Math.round(totals.bikeAssigned)}</td></tr>
        <tr><td>Bike spots over capacity</td><td>{totals.overBike}</td></tr>
        <tr><td>Car capacity (design)</td><td>{totals.carCapacity}</td></tr>
        <tr><td>Car demand (assigned)</td><td>{Math.round(totals.carAssigned)}</td></tr>
        <tr><td>Car spots over capacity</td><td>{totals.overCar}</td></tr>
      </tbody>
    </table>
  </section>

  {#if selectedAddress}
    <section class="detail">
      <h2>Address · {selectedAddress.street} {selectedAddress.housenumber}</h2>
      <p class="hint">{selectedAddress.postcode ?? ''} {selectedAddress.city ?? ''}</p>
      {#if selectedAssignment}
        <table>
          <tbody>
            <tr><td>Nearest bike rack</td><td>{Math.round(selectedAssignment.nearestBikeMeters)} m</td></tr>
            <tr><td>Nearest car spot</td><td>{Math.round(selectedAssignment.nearestCarMeters)} m</td></tr>
          </tbody>
        </table>
      {/if}
      <h3>Overrides</h3>
      <label class="num">
        Households
        <input type="number" min="0" placeholder="1"
          value={overrides[selectedAddress.id]?.households ?? ''}
          oninput={(e) => updateOverride('households', e.currentTarget.value)} />
      </label>
      <label class="num">
        Persons
        <input type="number" min="0" placeholder={String(((overrides[selectedAddress.id]?.households ?? 1) * defaults.persons_per_hh).toFixed(1))}
          value={overrides[selectedAddress.id]?.persons ?? ''}
          oninput={(e) => updateOverride('persons', e.currentTarget.value)} />
      </label>
      <label class="num">
        Cars
        <input type="number" min="0" step="0.1" placeholder={String(((overrides[selectedAddress.id]?.households ?? 1) * defaults.cars_per_hh).toFixed(2))}
          value={overrides[selectedAddress.id]?.cars ?? ''}
          oninput={(e) => updateOverride('cars', e.currentTarget.value)} />
      </label>
      <label class="num">
        Bikes
        <input type="number" min="0" step="0.5" placeholder={String((((overrides[selectedAddress.id]?.persons ?? (overrides[selectedAddress.id]?.households ?? 1) * defaults.persons_per_hh)) * defaults.bikes_per_person).toFixed(1))}
          value={overrides[selectedAddress.id]?.bikes ?? ''}
          oninput={(e) => updateOverride('bikes', e.currentTarget.value)} />
      </label>
    </section>
  {/if}

  {#if selectedSpot && selectedLoad}
    <section class="detail">
      <h2>{selectedSpot.kind === 'bike' ? 'Bike rack' : 'Car spot'} · {selectedSpot.street}</h2>
      <p class="hint">Side: {selectedSpot.side}</p>
      <table>
        <tbody>
          <tr><td>Capacity</td><td>{selectedLoad.capacity}</td></tr>
          <tr><td>Demand assigned</td><td>{selectedLoad.assigned.toFixed(1)}</td></tr>
          <tr><td>Utilization</td><td class:over={selectedLoad.utilization > 1}>{(selectedLoad.utilization * 100).toFixed(0)}%</td></tr>
          <tr><td>Addresses served</td><td>{selectedLoad.addresses.length}</td></tr>
        </tbody>
      </table>
    </section>
  {/if}

  <footer>
    <p>Roads, buildings, addresses, existing parking: OpenStreetMap via Overpass.</p>
    <p>Bike racks + trees: detected from the design PDF via color thresholding (blue dashes = fietsnietjes per legend).</p>
    <p>Car parking: still interpolated along centerlines — not yet detected.</p>
  </footer>
  </div>
</aside>

<style>
  /* ── shared layout ──────────────────────────────────────────────── */
  .sidebar {
    position: fixed;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    font: 14px/1.45 -apple-system, system-ui, sans-serif;
    color: #1a1a1a;
    z-index: 1000;
    display: flex;
    flex-direction: column;
  }
  .scroll {
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 4px 20px 20px;
    -webkit-overflow-scrolling: touch;
  }

  /* ── mobile: bottom sheet ──────────────────────────────────────── */
  @media (max-width: 767px) {
    .sidebar {
      left: 0;
      right: 0;
      bottom: 0;
      max-height: 88dvh;
      border-top: 1px solid #ddd;
      border-radius: 16px 16px 0 0;
      box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.12);
      padding-bottom: env(safe-area-inset-bottom);
      transform: translateY(calc(100% - 72px - env(safe-area-inset-bottom)));
      transition: transform 220ms cubic-bezier(0.32, 0.72, 0, 1);
    }
    .sidebar.open {
      transform: translateY(0);
    }
    .scroll {
      max-height: calc(88dvh - 72px - env(safe-area-inset-bottom));
    }
  }

  /* ── handle / sheet header ─────────────────────────────────────── */
  .handle {
    appearance: none;
    border: 0;
    background: transparent;
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    align-items: center;
    gap: 4px 12px;
    padding: 10px 20px 12px;
    width: 100%;
    cursor: pointer;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
    text-align: left;
    font: inherit;
    color: inherit;
    border-bottom: 1px solid #eee;
  }
  .grip {
    grid-column: 1 / -1;
    width: 40px;
    height: 5px;
    background: #c8c8c8;
    border-radius: 999px;
    margin: 0 auto 4px;
  }
  .handle-summary {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }
  .handle-summary strong {
    font-weight: 600;
    font-size: 15px;
  }
  .handle-summary .muted {
    color: #666;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .caret {
    font-size: 22px;
    color: #666;
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
    border-radius: 8px;
  }
  .handle:active .caret { background: #eee; }

  /* ── desktop: right rail (last, so it overrides general .handle/.scroll) ── */
  @media (min-width: 768px) {
    .sidebar {
      top: 0;
      right: 0;
      bottom: 0;
      width: 360px;
      border-left: 1px solid #ddd;
      padding-top: env(safe-area-inset-top);
      padding-right: env(safe-area-inset-right);
    }
    .handle { display: none; }
    .scroll { padding-top: 16px; }
  }

  /* ── content ────────────────────────────────────────────────────── */
  h1 { font-size: 18px; margin: 12px 0 2px; }
  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #555;
    margin: 18px 0 8px;
    font-weight: 600;
  }
  h3 {
    font-size: 11px;
    color: #555;
    margin: 12px 0 6px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  header p { color: #666; margin: 0 0 8px; font-size: 13px; }
  section { border-top: 1px solid #eee; padding-top: 4px; }
  label {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    min-height: 32px;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  label.num { justify-content: space-between; }
  label.range { flex-direction: column; align-items: stretch; gap: 4px; }
  input[type="checkbox"] {
    width: 20px;
    height: 20px;
    accent-color: #0a64c8;
    flex-shrink: 0;
  }
  input[type="number"] {
    width: 90px;
    padding: 8px 10px;
    font: inherit;
    font-size: 16px;   /* >=16px prevents iOS auto-zoom */
    border: 1px solid #ccc;
    border-radius: 6px;
    background: #fff;
    text-align: right;
    font-variant-numeric: tabular-nums;
    min-height: 36px;
  }
  input[type="range"] { width: 100%; height: 28px; }
  select {
    width: 100%;
    padding: 8px 10px;
    font: inherit;
    font-size: 16px;
    border: 1px solid #ccc;
    border-radius: 6px;
    background: #fff;
    min-height: 40px;
  }
  button[type="button"]:not(.handle) {
    appearance: none;
    border: 1px solid #ccc;
    background: #fff;
    padding: 8px 12px;
    border-radius: 6px;
    font: inherit;
    cursor: pointer;
    min-height: 36px;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  td { padding: 5px 0; border-bottom: 1px solid #f0f0f0; }
  td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
  .over { color: #c22; font-weight: 600; }
  .hint { color: #888; font-size: 12px; margin: 4px 0 8px; }
  footer {
    margin-top: 24px;
    padding-top: 12px;
    border-top: 1px solid #eee;
    color: #888;
    font-size: 11px;
  }
  footer p { margin: 0 0 4px; }
  .detail {
    background: #f6f7f9;
    margin: 12px -20px 0;
    padding: 12px 20px;
    border-top: 2px solid #ddd;
  }
  details > summary {
    cursor: pointer;
    padding: 6px 0;
    list-style: none;
    color: #444;
    -webkit-tap-highlight-color: transparent;
  }
  details > summary::-webkit-details-marker { display: none; }
  details[open] > summary { font-weight: 500; }

  @media (prefers-color-scheme: dark) {
    .sidebar {
      background: rgba(28, 30, 33, 0.96);
      color: #e6e8eb;
      border-left-color: #333;
      border-top-color: #333;
    }
    h2, h3, header p, .hint, footer, .caret { color: #aaa; }
    .handle-summary .muted { color: #999; }
    .grip { background: #444; }
    section, label, td { border-color: #2a2d31; }
    input[type="number"], select, button[type="button"]:not(.handle) {
      background: #222528;
      border-color: #3a3d41;
      color: #e6e8eb;
    }
    .detail { background: #1f2226; border-top-color: #3a3d41; }
    .handle { border-bottom-color: #2a2d31; }
  }
</style>
