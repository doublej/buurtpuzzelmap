import type { HouseholdDefaults, AddressOverrides, LoadResult, AddressAssignment } from '$lib/types';

export const defaults = $state<HouseholdDefaults>({
  persons_per_hh: 2.1,
  cars_per_hh: 0.8,
  bikes_per_person: 1.3
});

export const overrides = $state<AddressOverrides>({});

export type BasemapKey = 'cartoLight' | 'cartoDark' | 'osm' | 'esriSat' | 'pdokBRT' | 'pdokLuchtfoto';

export const basemaps: Record<BasemapKey, { name: string; url: string; attribution: string; maxZoom: number; subdomains?: string }> = {
  cartoLight: {
    name: 'Carto Light',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap, © CARTO',
    maxZoom: 20,
    subdomains: 'abcd'
  },
  cartoDark: {
    name: 'Carto Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap, © CARTO',
    maxZoom: 20,
    subdomains: 'abcd'
  },
  osm: {
    name: 'OSM Standard',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
  },
  esriSat: {
    name: 'Esri Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles © Esri',
    maxZoom: 19
  },
  pdokBRT: {
    name: 'PDOK BRT (NL)',
    url: 'https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png',
    attribution: '© Kadaster / PDOK',
    maxZoom: 19
  },
  pdokLuchtfoto: {
    name: 'PDOK Luchtfoto',
    url: 'https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg',
    attribution: '© Beeldmateriaal.nl / PDOK',
    maxZoom: 19
  }
};

export const ui = $state({
  showAddresses: true,
  showCarOSM: true,
  showBikeDesign: true,
  showCarDesign: true,
  showTrees: true,
  showBuildings: false,
  showRoads: false,
  sheetOpen: false,
  basemap: 'pdokLuchtfoto' as BasemapKey,
  selectedAddressId: null as string | null,
  selectedSpotId: null as string | null,
  loadMode: 'bike' as 'bike' | 'car',
  calibrate: { active: false, points: [] as Array<{ n: number; lat: number; lng: number }> }
});

export const results = $state<{
  assignments: AddressAssignment[];
  bikeLoad: LoadResult[];
  carLoad: LoadResult[];
}>({
  assignments: [],
  bikeLoad: [],
  carLoad: []
});

const OV_KEY = 'buurtpuzzel.overrides.v1';
const UI_KEY = 'buurtpuzzel.ui.v1';

export function loadOverrides() {
  if (typeof localStorage === 'undefined') return;
  try {
    const raw = localStorage.getItem(OV_KEY);
    if (raw) Object.assign(overrides, JSON.parse(raw));
  } catch { /* */ }
  try {
    const raw = localStorage.getItem(UI_KEY);
    if (raw) {
      const saved = JSON.parse(raw);
      if (typeof saved.basemap === 'string') ui.basemap = saved.basemap;
    }
  } catch { /* */ }
}

export function persistOverrides() {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(OV_KEY, JSON.stringify(overrides));
}

export function persistUI() {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(UI_KEY, JSON.stringify({
    basemap: ui.basemap
  }));
}
