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
    const bikeSpots = layers.bikeDesign;
    const carSpots = layers.carDesign;
    const assignments = assignAll(layers.addresses, bikeSpots, carSpots);

    const demands = new Map(
      layers.addresses.map((a) => [a.id, defaultDemand(a, $state.snapshot(defaults), $state.snapshot(overrides))])
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
