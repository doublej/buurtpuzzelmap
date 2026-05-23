<script lang="ts">
  import { onMount } from 'svelte';
  import MapView from '$lib/MapView.svelte';
  import Sidebar from '$lib/Sidebar.svelte';
  import { loadAllLayers, type Layers } from '$lib/data/load';
  import { defaults, overrides, results, loadOverrides } from '$lib/state.svelte';
  import { assignAll, computeLoadGravity, defaultDemand } from '$lib/calc/assignment';

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
    // Gravity-weighted split across the 3 nearest spots within walking band.
    // Bikes: 150 m. Cars: 250 m (people walk further for a car).
    results.bikeLoad = computeLoadGravity(layers.addresses, bikeSpots, demands, 'bike', 150, 3);
    results.carLoad = computeLoadGravity(layers.addresses, carSpots, demands, 'car', 250, 3);
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
  :global(html) {
    margin: 0;
    padding: 0;
    height: 100%;
    touch-action: manipulation;
    overscroll-behavior: none;
    -webkit-text-size-adjust: 100%;
    color-scheme: light dark;
  }
  :global(body) {
    margin: 0;
    padding: 0;
    height: 100dvh;
    font: 14px/1.4 -apple-system, system-ui, sans-serif;
    background: #eef;
    overflow: hidden;
  }
  :global(*) { -webkit-tap-highlight-color: transparent; }

  .app {
    position: fixed;
    inset: 0;
    height: 100dvh;
  }
  .loading, .error {
    position: absolute; inset: 0;
    display: grid; place-items: center;
    color: #555;
    padding: 20px;
    text-align: center;
  }
  .error { color: #c22; }

  @media (prefers-color-scheme: dark) {
    :global(body) { background: #111315; color: #eee; }
    .loading { color: #ccc; }
  }

  @media (prefers-reduced-motion: reduce) {
    :global(*), :global(*::before), :global(*::after) {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
</style>
