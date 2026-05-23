import type { FeatureCollection, Point, LineString, Polygon } from 'geojson';
import type { Address, ParkingSpot } from '$lib/types';
import { base } from '$app/paths';

async function fetchJson<T>(path: string): Promise<T> {
  const r = await fetch(`${base}${path}`);
  if (!r.ok) throw new Error(`fetch ${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

export interface Layers {
  roads: FeatureCollection<LineString>;
  buildings: FeatureCollection<Polygon>;
  addresses: Address[];
  bikeOSM: FeatureCollection<Point>;
  carOSM: FeatureCollection;
  bikeDesign: ParkingSpot[];
  carDesign: ParkingSpot[];
  meta: {
    bbox: [number, number, number, number];
    center: [number, number];
    counts: Record<string, number>;
  };
}

export async function loadAllLayers(): Promise<Layers> {
  const [roads, buildings, addrFc, bikeOSM, carOSM, bikeFc, carFc, meta] = await Promise.all([
    fetchJson<FeatureCollection<LineString>>('/data/roads.geojson'),
    fetchJson<FeatureCollection<Polygon>>('/data/buildings.geojson'),
    fetchJson<FeatureCollection<Point>>('/data/addresses.geojson'),
    fetchJson<FeatureCollection<Point>>('/data/bike_parking.geojson'),
    fetchJson<FeatureCollection>('/data/car_parking.geojson'),
    fetchJson<FeatureCollection<Point>>('/data/bike_parking_design.geojson'),
    fetchJson<FeatureCollection<Point>>('/data/car_parking_design.geojson'),
    fetchJson<Layers['meta']>('/data/meta.json')
  ]);

  const addresses: Address[] = addrFc.features.map((f) => ({
    id: String(f.id),
    street: f.properties?.street ?? '',
    housenumber: String(f.properties?.housenumber ?? ''),
    postcode: f.properties?.postcode,
    city: f.properties?.city,
    lng: f.geometry.coordinates[0],
    lat: f.geometry.coordinates[1]
  }));

  const bikeDesign: ParkingSpot[] = bikeFc.features.map((f) => ({
    id: String(f.id),
    kind: 'bike',
    street: f.properties?.street ?? '',
    side: f.properties?.side ?? '',
    segment_id: f.properties?.segment_id,
    capacity: Number(f.properties?.capacity ?? 2),
    source: 'pdf_design',
    lng: f.geometry.coordinates[0],
    lat: f.geometry.coordinates[1]
  }));

  const carDesign: ParkingSpot[] = carFc.features.map((f) => ({
    id: String(f.id),
    kind: 'car',
    street: f.properties?.street ?? '',
    side: f.properties?.side ?? '',
    segment_id: f.properties?.segment_id,
    capacity: Number(f.properties?.capacity ?? 1),
    source: 'pdf_design',
    lng: f.geometry.coordinates[0],
    lat: f.geometry.coordinates[1]
  }));

  return { roads, buildings, addresses, bikeOSM, carOSM, bikeDesign, carDesign, meta };
}
