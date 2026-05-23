export type LngLat = [number, number];

export interface Address {
  id: string;
  street: string;
  housenumber: string;
  postcode?: string;
  city?: string;
  lng: number;
  lat: number;
}

export interface ParkingSpot {
  id: string;
  kind: 'bike' | 'car';
  street: string;
  side: string;
  segment_id?: string;
  capacity: number;
  source: 'osm' | 'pdf_design';
  lng: number;
  lat: number;
}

export interface HouseholdDefaults {
  persons_per_hh: number;
  cars_per_hh: number;
  bikes_per_person: number;
}

export type AddressOverrides = Record<string, Partial<{
  households: number;
  persons: number;
  cars: number;
  bikes: number;
}>>;

export interface LoadResult {
  spotId: string;
  kind: 'bike' | 'car';
  capacity: number;
  assigned: number;          // sum of demand (bikes or cars)
  addresses: string[];        // ids
  utilization: number;        // assigned / capacity
}

export interface AddressAssignment {
  addressId: string;
  nearestBikeSpotId: string | null;
  nearestBikeMeters: number;
  nearestCarSpotId: string | null;
  nearestCarMeters: number;
}
