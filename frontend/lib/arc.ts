import type { GeoJSONFeatureCollection, TradeRouteGeoProperties } from "./types";

/**
 * Densify a straight exporter→importer segment into a quadratic-bezier arc so
 * trade flows read as sweeping curves rather than flat lines.
 *
 * The control point is offset perpendicular to the segment and always flipped
 * toward higher latitude, so arcs bow "up" from equatorial origins to consumer
 * markets. Endpoints are unwrapped across the antimeridian to take the shorter
 * path (MapLibre renders coordinates beyond ±180 into adjacent world copies).
 */
export function buildArc(
  start: [number, number],
  end: [number, number],
  segments = 48,
): [number, number][] {
  const [lon1, lat1] = start;
  let [lon2, lat2] = end;

  const dlonRaw = lon2 - lon1;
  if (dlonRaw > 180) lon2 -= 360;
  else if (dlonRaw < -180) lon2 += 360;

  const dx = lon2 - lon1;
  const dy = lat2 - lat1;
  const dist = Math.hypot(dx, dy) || 1e-6;

  // Unit perpendicular, flipped to always bow toward higher latitude.
  let nx = -dy / dist;
  let ny = dx / dist;
  if (ny < 0) {
    nx = -nx;
    ny = -ny;
  }

  const off = dist * 0.18;
  const cx = (lon1 + lon2) / 2 + nx * off;
  const cy = (lat1 + lat2) / 2 + ny * off;

  const pts: [number, number][] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const u = 1 - t;
    pts.push([
      u * u * lon1 + 2 * u * t * cx + t * t * lon2,
      u * u * lat1 + 2 * u * t * cy + t * t * lat2,
    ]);
  }
  return pts;
}

/**
 * Replace each trade-route LineString (a straight exporter→importer segment
 * from the API) with a bezier arc, preserving feature properties.
 */
export function toArcs(
  fc: GeoJSONFeatureCollection<TradeRouteGeoProperties>,
): GeoJSONFeatureCollection<TradeRouteGeoProperties> {
  return {
    type: "FeatureCollection",
    features: fc.features.map((f) => {
      const coords = f.geometry.coordinates as number[][];
      const start = coords[0] as [number, number];
      const end = coords[coords.length - 1] as [number, number];
      return {
        ...f,
        geometry: { type: "LineString", coordinates: buildArc(start, end) },
      };
    }),
  };
}
