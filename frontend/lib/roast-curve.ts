import * as d3 from "d3";
import type { RoastProfile } from "./types";

/**
 * Synthesize a believable bean-probe temperature-vs-time curve from a roast
 * profile's four scalars. The content DB stores no time-series curve data — only
 * summary numbers (charge temp, first-crack temp, development-time ratio, total
 * time) — so the curve is reconstructed here, client-side, purely for the
 * "watch & learn" roast simulator. It is a visual approximation of a real roast,
 * not a captured roaster log.
 *
 * The curve reproduces the classic shape: a charge spike, a turning-point
 * minimum (~90-105°C as cold beans absorb heat), then a monotonic climb through
 * first crack to the drop. Anchors are interpolated with a monotone cubic
 * (Fritsch-Carlson) so the line passes through the data points exactly — the
 * first-crack marker must sit on its (t, temp) anchor — and never overshoots
 * below the turning point.
 */

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** Drop temperature (°C) by roast level — where the roaster ends the roast. */
const LEVEL_DROP: Record<string, number> = {
  light: 205,
  "medium-light": 210,
  medium: 214,
  "medium-dark": 219,
  dark: 225,
};

/** Beans reach second crack around here; only dark roasts get there. */
const SECOND_CRACK_TEMP = 224;
/** Yellowing / end of the drying phase. */
const DRYING_END_TEMP = 150;
const SAMPLE_COUNT = 200;

export interface RoastEvent {
  id: "turning_point" | "drying_end" | "first_crack" | "second_crack" | "drop";
  label: string;
  t: number;
  temp: number;
}

export interface RoastPhase {
  id: "drying" | "maillard" | "development";
  label: string;
  t0: number;
  t1: number;
  /** Base fill used by the chart (rendered at low opacity). */
  color: string;
}

export interface RoastCurve {
  durationSec: number;
  charge: number;
  /** Bean-probe temperature at time `t` (seconds), clamped to [0, durationSec]. */
  tempAt: (t: number) => number;
  /** Temperature that drives the bean's color — clamps out the pre-turning-point
   *  charge spike so the bean reads green at the start, not brown. */
  colorTempAt: (t: number) => number;
  samples: { t: number; temp: number }[];
  /** Ordered events; `second_crack` is omitted when the roast never reaches it. */
  events: RoastEvent[];
  phases: RoastPhase[];
  /** y-domain for a chart: spans the turning-point floor and the charge/drop top. */
  tempRange: [number, number];
}

const PHASE_COLORS = {
  drying: "#bcd6ea",
  maillard: "#e8c98c",
  development: "#cf9b67",
} as const;

/**
 * Fritsch-Carlson monotone cubic Hermite interpolation. Given strictly
 * increasing `xs` and matching `ys`, returns f(x) that passes through every
 * point and is monotonicity-preserving per interval (no overshoot at local
 * extrema — the tangent is zeroed where the secant slope changes sign). Clamps
 * to the endpoints outside the domain.
 */
function monotoneInterpolant(xs: number[], ys: number[]): (x: number) => number {
  const n = xs.length;
  const dx: number[] = [];
  const m: number[] = []; // secant slope of each interval
  for (let i = 0; i < n - 1; i++) {
    const h = xs[i + 1] - xs[i];
    dx.push(h);
    m.push((ys[i + 1] - ys[i]) / h);
  }

  const tangents = new Array<number>(n);
  tangents[0] = m[0];
  tangents[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) {
    if (m[i - 1] * m[i] <= 0) {
      tangents[i] = 0; // local extremum -> flat tangent, no overshoot
    } else {
      const w1 = 2 * dx[i] + dx[i - 1];
      const w2 = dx[i] + 2 * dx[i - 1];
      tangents[i] = (w1 + w2) / (w1 / m[i - 1] + w2 / m[i]);
    }
  }

  return (x: number) => {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    let i = n - 2;
    for (let j = 0; j < n - 1; j++) {
      if (x < xs[j + 1]) {
        i = j;
        break;
      }
    }
    const h = dx[i];
    const t = (x - xs[i]) / h;
    const t2 = t * t;
    const t3 = t2 * t;
    const h00 = 2 * t3 - 3 * t2 + 1;
    const h10 = t3 - 2 * t2 + t;
    const h01 = -2 * t3 + 3 * t2;
    const h11 = t3 - t2;
    return (
      h00 * ys[i] +
      h10 * h * tangents[i] +
      h01 * ys[i + 1] +
      h11 * h * tangents[i + 1]
    );
  };
}

export function makeRoastCurve(p: RoastProfile): RoastCurve | null {
  const charge = p.charge_temp;
  const firstCrackTemp = p.first_crack_temp;
  const dtrRaw = p.development_time_ratio;
  const total = p.total_roast_time;
  if (charge == null || firstCrackTemp == null || dtrRaw == null || total == null) {
    return null;
  }
  if (total <= 0) return null;

  const dtr = clamp(dtrRaw, 0.05, 0.5);

  // Anchor: first crack — given by the data.
  const tFc = total * (1 - dtr);

  // Anchor: turning point — probe minimum, ~1:00-1:30 regardless of batch length.
  let tTp = clamp(0.1 * total, 45, 90);
  tTp = Math.min(tTp, 0.5 * tFc); // always precede first crack
  const tempTp = clamp(90 + (charge - 180) * 0.2, 88, 105);

  // Anchor: drop — derived from roast level, nudged by development ratio so the
  // three same-level "dark" profiles separate (Italian ends hottest).
  const levelDrop = p.roast_level != null ? LEVEL_DROP[p.roast_level] : undefined;
  let tDrop =
    levelDrop != null
      ? clamp(levelDrop + (dtr - 0.2) * 25, firstCrackTemp + 6, 232)
      : firstCrackTemp + 12;
  tDrop = Math.max(tDrop, firstCrackTemp + 6); // keep anchors strictly ordered

  const xs = [0, tTp, tFc, total];
  const ys = [charge, tempTp, firstCrackTemp, tDrop];
  const tempAt = monotoneInterpolant(xs, ys);

  const samples: { t: number; temp: number }[] = [];
  for (let i = 0; i <= SAMPLE_COUNT; i++) {
    const t = (i / SAMPLE_COUNT) * total;
    samples.push({ t, temp: tempAt(t) });
  }

  // Invert temp -> time on the rising branch only (t >= tTp), where temperature
  // is monotonically increasing. Used to place markers exactly on the curve.
  const tAtTemp = (target: number): number => {
    for (let i = 1; i < samples.length; i++) {
      const a = samples[i - 1];
      const b = samples[i];
      if (b.t < tTp) continue; // skip the falling charge->turning-point branch
      if (a.temp <= target && b.temp >= target && b.temp > a.temp) {
        const f = (target - a.temp) / (b.temp - a.temp);
        return a.t + f * (b.t - a.t);
      }
    }
    return total;
  };

  const tDry = tAtTemp(DRYING_END_TEMP);

  const events: RoastEvent[] = [
    { id: "turning_point", label: "Turning point", t: tTp, temp: tempTp },
    { id: "drying_end", label: "Drying ends", t: tDry, temp: DRYING_END_TEMP },
    { id: "first_crack", label: "First crack", t: tFc, temp: firstCrackTemp },
  ];
  if (tDrop >= SECOND_CRACK_TEMP) {
    events.push({
      id: "second_crack",
      label: "Second crack",
      t: tAtTemp(SECOND_CRACK_TEMP),
      temp: SECOND_CRACK_TEMP,
    });
  }
  events.push({ id: "drop", label: "Drop", t: total, temp: tDrop });

  const phases: RoastPhase[] = [
    { id: "drying", label: "Drying", t0: 0, t1: tDry, color: PHASE_COLORS.drying },
    { id: "maillard", label: "Maillard", t0: tDry, t1: tFc, color: PHASE_COLORS.maillard },
    {
      id: "development",
      label: "Development",
      t0: tFc,
      t1: total,
      color: PHASE_COLORS.development,
    },
  ];

  const colorTempAt = (t: number): number => (t <= tTp ? tempTp : tempAt(t));

  return {
    durationSec: total,
    charge,
    tempAt,
    colorTempAt,
    samples,
    events,
    phases,
    tempRange: [80, Math.max(charge, tDrop) + 8],
  };
}

/**
 * Map a bean's color-temperature to a fill, green seed -> roasted bean. The
 * string range makes d3 interpolate in RGB. Clamped: green below 95°C, near
 * black above 230°C.
 */
const beanScale = d3
  .scaleLinear<string>()
  .domain([95, 150, 175, 196, 210, 222, 230])
  .range([
    "#6f7a45", // raw green seed
    "#c9a86a", // yellow-tan (drying end)
    "#a9743f", // cinnamon
    "#8a4f2a", // first-crack brown
    "#5e361f", // medium-dark
    "#3d2415", // dark
    "#241410", // near-black espresso
  ])
  .clamp(true);

export function beanColor(colorTemp: number): string {
  return beanScale(colorTemp);
}

/** Oily surface sheen (0-0.35 opacity) — appears only on dark roasts. */
export function beanSheen(colorTemp: number): number {
  return clamp((colorTemp - 218) / 12, 0, 0.35);
}
