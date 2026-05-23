<script lang="ts">
  import { onMount } from 'svelte';
  import MapView from '$lib/MapView.svelte';
  import Sidebar from '$lib/Sidebar.svelte';
  import { loadAllLayers, type Layers } from '$lib/data/load';
  import { defaults, overrides, results, loadOverrides } from '$lib/state.svelte';
  import { assignAll, computeLoad, defaultDemand } from '$lib/calc/assignment';

  let layers = $state<Layers | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    loadOverrides();
    try {
      layers = await loadAllLayers();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  });

  $effect(() => {
    if (!layers) return;
    // Read individual properties so this effect subscribes to each one;
    // $state.snapshot() does not always register fine-grained deps in builds.
    const p = defaults.persons_per_hh;
    const c = defaults.cars_per_hh;
    const b = defaults.bikes_per_person;
    // Touch each override so this effect re-runs when any value within them changes.
    let overrideFingerprint = '';
    for (const k of Object.keys(overrides)) {
      const v = overrides[k];
      overrideFingerprint += `${k}:${v?.households ?? ''},${v?.persons ?? ''},${v?.cars ?? ''},${v?.bikes ?? ''};`;
    }
    void overrideFingerprint;

    const bikeSpots = layers.bikeDesign;
    const carSpots = layers.carDesign;
    const assignments = assignAll(layers.addresses, bikeSpots, carSpots);

    const demands = new Map(
      layers.addresses.map((a) => [
        a.id,
        defaultDemand(a, { persons_per_hh: p, cars_per_hh: c, bikes_per_person: b }, overrides)
      ])
    );

    results.assignments = assignments;
    results.bikeLoad = computeLoad(bikeSpots, assignments, demands, 'bike');
    results.carLoad = computeLoad(carSpots, assignments, demands, 'car');
  });
</script>

<main class="app">
  {#if error}
    <div class="error">Failed to load: {error}</div>
  {:else if layers}
    <MapView {layers} />
    <Sidebar {layers} />
  {:else}
    <div class="loading">Loading neighborhood data…</div>
  {/if}
</main>

<style>
  :global(html, body) { margin: 0; padding: 0; height: 100%; }
  :global(body) { font: 14px/1.4 -apple-system, system-ui, sans-serif; }
  .app { position: fixed; inset: 0; }
  .loading, .error {
    position: absolute; inset: 0;
    display: grid; place-items: center;
    color: #555;
  }
  .error { color: #c22; }
</style>
