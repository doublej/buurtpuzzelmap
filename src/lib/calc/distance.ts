/** Haversine distance in metres between two lon/lat points. */
export function haversineMeters(a: [number, number], b: [number, number]): number {
  const R = 6_371_000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b[1] - a[1]);
  const dLon = toRad(b[0] - a[0]);
  const lat1 = toRad(a[1]);
  const lat2 = toRad(b[1]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Manhattan-on-graph approximation: 1.3 × haversine — a rough urban detour factor. */
export function walkingMetersApprox(a: [number, number], b: [number, number]): number {
  return haversineMeters(a, b) * 1.3;
}
