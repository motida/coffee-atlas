// @vitest-environment node
import { describe, expect, it } from "vitest";
import { beanColor, beanSheen, makeRoastCurve } from "./roast-curve";
import type { RoastProfile } from "./types";

function profile(over: Partial<RoastProfile>): RoastProfile {
  return {
    id: "p",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    name: "Test",
    roast_level: "medium",
    first_crack_temp: 198,
    development_time_ratio: 0.2,
    charge_temp: 195,
    total_roast_time: 630,
    description: null,
    ...over,
  };
}

// The 11 seeded profiles (the simulator's real inputs).
const SEED: Pick<
  RoastProfile,
  | "name"
  | "roast_level"
  | "first_crack_temp"
  | "development_time_ratio"
  | "charge_temp"
  | "total_roast_time"
>[] = [
  { name: "Nordic Light", roast_level: "light", first_crack_temp: 196, development_time_ratio: 0.15, charge_temp: 180, total_roast_time: 510 },
  { name: "Cinnamon Roast", roast_level: "light", first_crack_temp: 196, development_time_ratio: 0.12, charge_temp: 175, total_roast_time: 480 },
  { name: "City Roast", roast_level: "medium-light", first_crack_temp: 197, development_time_ratio: 0.17, charge_temp: 190, total_roast_time: 570 },
  { name: "City+ Roast", roast_level: "medium", first_crack_temp: 198, development_time_ratio: 0.2, charge_temp: 195, total_roast_time: 630 },
  { name: "Omni Roast", roast_level: "medium-light", first_crack_temp: 197, development_time_ratio: 0.19, charge_temp: 190, total_roast_time: 600 },
  { name: "Full City Roast", roast_level: "medium-dark", first_crack_temp: 199, development_time_ratio: 0.22, charge_temp: 200, total_roast_time: 690 },
  { name: "Full City+ Roast", roast_level: "medium-dark", first_crack_temp: 200, development_time_ratio: 0.24, charge_temp: 205, total_roast_time: 720 },
  { name: "Classic Espresso", roast_level: "medium-dark", first_crack_temp: 200, development_time_ratio: 0.25, charge_temp: 200, total_roast_time: 750 },
  { name: "Vienna Roast", roast_level: "dark", first_crack_temp: 201, development_time_ratio: 0.25, charge_temp: 210, total_roast_time: 780 },
  { name: "French Roast", roast_level: "dark", first_crack_temp: 202, development_time_ratio: 0.27, charge_temp: 215, total_roast_time: 810 },
  { name: "Italian Roast", roast_level: "dark", first_crack_temp: 203, development_time_ratio: 0.28, charge_temp: 220, total_roast_time: 840 },
];

describe("makeRoastCurve", () => {
  it("returns null when a required scalar is missing", () => {
    expect(makeRoastCurve(profile({ charge_temp: null }))).toBeNull();
    expect(makeRoastCurve(profile({ first_crack_temp: null }))).toBeNull();
    expect(makeRoastCurve(profile({ development_time_ratio: null }))).toBeNull();
    expect(makeRoastCurve(profile({ total_roast_time: null }))).toBeNull();
    expect(makeRoastCurve(profile({ total_roast_time: 0 }))).toBeNull();
  });

  it("places first crack at total·(1−DTR) with the data temperature", () => {
    const c = makeRoastCurve(profile({}))!;
    const fc = c.events.find((e) => e.id === "first_crack")!;
    expect(fc.t).toBeCloseTo(630 * (1 - 0.2), 6); // 504s
    expect(fc.temp).toBe(198);
    // The interpolated curve passes through the anchor exactly.
    expect(c.tempAt(fc.t)).toBeCloseTo(198, 6);
  });

  it("anchors the samples at charge (t=0) and drop (t=total)", () => {
    const c = makeRoastCurve(profile({}))!;
    const drop = c.events.find((e) => e.id === "drop")!;
    expect(c.samples[0].t).toBe(0);
    expect(c.samples[0].temp).toBeCloseTo(c.charge, 6);
    expect(c.samples[c.samples.length - 1].t).toBeCloseTo(c.durationSec, 6);
    expect(c.samples[c.samples.length - 1].temp).toBeCloseTo(drop.temp, 6);
  });

  it("has a turning point that is the curve minimum, in 45–90s", () => {
    const c = makeRoastCurve(profile({}))!;
    const tp = c.events.find((e) => e.id === "turning_point")!;
    expect(tp.t).toBeGreaterThanOrEqual(45);
    expect(tp.t).toBeLessThanOrEqual(90);
    const minTemp = Math.min(...c.samples.map((s) => s.temp));
    // The turning point is (within sampling tolerance) the coldest moment.
    expect(tp.temp).toBeLessThanOrEqual(minTemp + 1);
    expect(tp.temp).toBeLessThan(c.charge);
  });

  it("rises monotonically from the turning point to the drop", () => {
    const c = makeRoastCurve(profile({}))!;
    const tp = c.events.find((e) => e.id === "turning_point")!;
    const rising = c.samples.filter((s) => s.t >= tp.t);
    for (let i = 1; i < rising.length; i++) {
      expect(rising[i].temp).toBeGreaterThanOrEqual(rising[i - 1].temp - 1e-6);
    }
  });

  it("drops hotter than first crack for every seeded profile", () => {
    for (const s of SEED) {
      const c = makeRoastCurve(profile(s))!;
      const drop = c.events.find((e) => e.id === "drop")!;
      expect(drop.temp).toBeGreaterThan(s.first_crack_temp!);
    }
  });

  it("shows second crack only for dark roasts", () => {
    const has = (over: Partial<RoastProfile>) =>
      makeRoastCurve(profile(over))!.events.some((e) => e.id === "second_crack");
    // Dark profiles reach second crack; lighter ones never do.
    for (const s of SEED) {
      expect(has(s)).toBe(s.roast_level === "dark");
    }
  });

  it("orders phases drying → maillard → development without gaps", () => {
    const c = makeRoastCurve(profile({}))!;
    const [dry, mai, dev] = c.phases;
    expect(dry.t0).toBe(0);
    expect(dry.t1).toBeCloseTo(mai.t0, 6);
    expect(mai.t1).toBeCloseTo(dev.t0, 6);
    expect(dev.t1).toBeCloseTo(c.durationSec, 6);
    expect(dry.t1).toBeLessThan(mai.t1); // 150°C crossing precedes first crack
  });

  it("falls back safely when roast_level is null (no second crack)", () => {
    const c = makeRoastCurve(profile({ roast_level: null }))!;
    const drop = c.events.find((e) => e.id === "drop")!;
    expect(drop.temp).toBeCloseTo(198 + 12, 6);
    expect(c.events.some((e) => e.id === "second_crack")).toBe(false);
  });
});

describe("beanColor / beanSheen", () => {
  it("reads green when cold and near-black when fully roasted", () => {
    expect(beanColor(90).toLowerCase()).toMatch(/^#?(6f7a45|rgb)/);
    // Below the domain floor it clamps to green; above the ceiling to near-black.
    expect(beanColor(60)).toBe(beanColor(95));
    expect(beanColor(260)).toBe(beanColor(230));
  });

  it("shows oily sheen only at high color-temperatures", () => {
    expect(beanSheen(180)).toBe(0);
    expect(beanSheen(215)).toBe(0);
    expect(beanSheen(230)).toBeGreaterThan(0);
    expect(beanSheen(260)).toBeLessThanOrEqual(0.35);
  });
});
