// @vitest-environment node
import { describe, expect, it } from "vitest";
import { buildArc, toArcs } from "./arc";
import type { GeoJSONFeatureCollection, TradeRouteGeoProperties } from "./types";

describe("buildArc", () => {
  it("starts and ends exactly at the endpoints", () => {
    const arc = buildArc([-55, -10], [10, 51]);
    expect(arc[0]).toEqual([-55, -10]);
    expect(arc[arc.length - 1]).toEqual([10, 51]);
  });

  it("emits segments + 1 points", () => {
    expect(buildArc([0, 0], [10, 10], 48)).toHaveLength(49);
    expect(buildArc([0, 0], [10, 10], 12)).toHaveLength(13);
  });

  it("bows toward higher latitude at the midpoint", () => {
    // Equatorial west→east route: the apex should sit north of the chord.
    const arc = buildArc([-40, 0], [40, 0], 48);
    const mid = arc[24];
    expect(mid[1]).toBeGreaterThan(0);
  });

  it("takes the short way across the antimeridian", () => {
    // 170°E → -170°E is 20° apart the short way, not 340° the long way.
    const arc = buildArc([170, 0], [-170, 0], 48);
    // Unwrapped endpoint is drawn at 190 (a world-copy of -170), so the arc
    // sweeps forward through the dateline rather than backward across the map.
    expect(arc[arc.length - 1][0]).toBeCloseTo(190, 6);
    expect(arc.every((p) => p[0] >= 169)).toBe(true);
  });
});

describe("toArcs", () => {
  it("replaces straight segments with arcs and keeps properties", () => {
    const fc: GeoJSONFeatureCollection<TradeRouteGeoProperties> = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry: { type: "LineString", coordinates: [[-55, -10], [10, 51]] },
          properties: {
            id: "rt1",
            exporter_id: "c_br",
            exporter_name: "Brazil",
            importer_id: "c_de",
            importer_name: "Germany",
            annual_volume: null,
            year: null,
          },
        },
      ],
    };

    const arcs = toArcs(fc);
    const feat = arcs.features[0];
    expect((feat.geometry.coordinates as number[][]).length).toBeGreaterThan(2);
    expect(feat.geometry.coordinates[0]).toEqual([-55, -10]);
    expect(feat.properties.exporter_name).toBe("Brazil");
    expect(feat.properties.importer_name).toBe("Germany");
  });
});
