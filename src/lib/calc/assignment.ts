import type { Address, ParkingSpot, AddressAssignment, LoadResult, HouseholdDefaults, AddressOverrides } from '$lib/types';
import { walkingMetersApprox } from './distance';

export interface DemandPerAddress {
  addressId: string;
  households: number;
  persons: number;
  cars: number;
  bikes: number;
}

export function defaultDemand(
  addr: Address,
  defaults: HouseholdDefaults,
  overrides: AddressOverrides
): DemandPerAddress {
  const o = overrides[addr.id] ?? {};
  const households = o.households ?? 1;
  const persons = o.persons ?? households * defaults.persons_per_hh;
  const cars = o.cars ?? households * defaults.cars_per_hh;
  const bikes = o.bikes ?? persons * defaults.bikes_per_person;
  return { addressId: addr.id, households, persons, cars, bikes };
}

export function nearestSpot(
  addr: Address,
  spots: ParkingSpot[]
): { id: string | null; meters: number } {
  let best: { id: string | null; meters: number } = { id: null, meters: Infinity };
  for (const s of spots) {
    const d = walkingMetersApprox([addr.lng, addr.lat], [s.lng, s.lat]);
    if (d < best.meters) best = { id: s.id, meters: d };
  }
  return best;
}

export function assignAll(
  addresses: Address[],
  bikeSpots: ParkingSpot[],
  carSpots: ParkingSpot[]
): AddressAssignment[] {
  return addresses.map((a) => {
    const b = nearestSpot(a, bikeSpots);
    const c = nearestSpot(a, carSpots);
    return {
      addressId: a.id,
      nearestBikeSpotId: b.id,
      nearestBikeMeters: b.meters,
      nearestCarSpotId: c.id,
      nearestCarMeters: c.meters
    };
  });
}

export function computeLoad(
  spots: ParkingSpot[],
  assignments: AddressAssignment[],
  demands: Map<string, DemandPerAddress>,
  kind: 'bike' | 'car'
): LoadResult[] {
  const byId = new Map<string, LoadResult>();
  for (const s of spots) {
    byId.set(s.id, {
      spotId: s.id,
      kind: s.kind,
      capacity: s.capacity,
      assigned: 0,
      addresses: [],
      utilization: 0
    });
  }
  for (const a of assignments) {
    const spotId = kind === 'bike' ? a.nearestBikeSpotId : a.nearestCarSpotId;
    if (!spotId) continue;
    const r = byId.get(spotId);
    if (!r) continue;
    const d = demands.get(a.addressId);
    if (!d) continue;
    r.assigned += kind === 'bike' ? d.bikes : d.cars;
    r.addresses.push(a.addressId);
  }
  for (const r of byId.values()) {
    r.utilization = r.capacity > 0 ? r.assigned / r.capacity : Infinity;
  }
  return [...byId.values()];
}
