"use client";

import * as d3 from "d3";
import { useMemo } from "react";
import type { RoastCurve } from "@/lib/roast-curve";

const W = 680;
const H = 380;
const M = { top: 18, right: 18, bottom: 34, left: 44 };

function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * Bean-temperature-vs-time chart, pure SVG (d3 for scales/line only — the
 * FlavorWheel convention). Draws phase bands, a faint full target curve, the
 * filled-in progress curve up to `currentT`, event markers, and a playhead.
 */
export function RoastChart({
  curve,
  currentT,
}: {
  curve: RoastCurve;
  currentT: number;
}) {
  const x = useMemo(
    () => d3.scaleLinear().domain([0, curve.durationSec]).range([M.left, W - M.right]),
    [curve.durationSec],
  );
  const y = useMemo(
    () => d3.scaleLinear().domain(curve.tempRange).range([H - M.bottom, M.top]),
    [curve.tempRange],
  );

  const line = useMemo(
    () =>
      d3
        .line<{ t: number; temp: number }>()
        .x((d) => x(d.t))
        .y((d) => y(d.temp)),
    [x, y],
  );

  const fullPath = useMemo(() => line(curve.samples) ?? "", [line, curve.samples]);
  const progressPath = useMemo(
    () => line(curve.samples.filter((s) => s.t <= currentT)) ?? "",
    [line, curve.samples, currentT],
  );

  const xTicks = useMemo(() => x.ticks(6), [x]);
  const yTicks = useMemo(() => y.ticks(5), [y]);

  // Lay out event labels so they clear the chart edges, the top phase labels,
  // and each other. Markers high on the curve (near the top) put their label
  // below; low ones put it above. Temporally-adjacent markers that sit close
  // together horizontally (e.g. second crack and drop on dark roasts) are
  // staggered onto separate rows.
  const midY = (M.top + (H - M.bottom)) / 2;
  const eventLabels = useMemo(() => {
    let prevX = -Infinity;
    let stagger = 0;
    return curve.events.map((e) => {
      const px = x(e.t);
      const py = y(e.temp);
      const high = py < midY;
      const nearRight = px > W - M.right - 64;
      const nearLeft = px < M.left + 8;
      const anchor = nearRight ? "end" : nearLeft ? "start" : "middle";
      const lx = nearRight ? W - M.right : nearLeft ? M.left : px;
      stagger = Math.abs(px - prevX) < 72 ? stagger + 1 : 0;
      prevX = px;
      const ly = high ? py + 14 + stagger * 13 : py - 8 - stagger * 13;
      return { e, px, py, lx, ly, anchor: anchor as "start" | "middle" | "end" };
    });
  }, [curve.events, x, y, midY]);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full select-none"
      role="img"
      aria-label="Roast temperature curve"
    >
      {/* Phase bands */}
      {curve.phases.map((ph) => {
        const x0 = x(ph.t0);
        const x1 = x(ph.t1);
        return (
          <g key={ph.id}>
            <rect
              x={x0}
              y={M.top}
              width={Math.max(0, x1 - x0)}
              height={H - M.bottom - M.top}
              fill={ph.color}
              opacity={0.3}
            />
            <text
              x={(x0 + x1) / 2}
              y={M.top + 13}
              textAnchor="middle"
              fontSize={11}
              fontWeight={600}
              fill="#7a4320"
            >
              {ph.label}
            </text>
          </g>
        );
      })}

      {/* Gridlines + axis labels */}
      {yTicks.map((t) => (
        <g key={`y${t}`}>
          <line
            x1={M.left}
            x2={W - M.right}
            y1={y(t)}
            y2={y(t)}
            stroke="#eadfce"
            strokeWidth={1}
          />
          <text
            x={M.left - 6}
            y={y(t)}
            textAnchor="end"
            dominantBaseline="middle"
            fontSize={10}
            fill="#9b8a73"
          >
            {t}°
          </text>
        </g>
      ))}
      {xTicks.map((t) => (
        <text
          key={`x${t}`}
          x={x(t)}
          y={H - M.bottom + 16}
          textAnchor="middle"
          fontSize={10}
          fill="#9b8a73"
        >
          {fmtTime(t)}
        </text>
      ))}

      {/* Faint full target curve */}
      <path
        d={fullPath}
        fill="none"
        stroke="#cbb89c"
        strokeWidth={1.5}
        strokeDasharray="3 3"
      />
      {/* Progress curve */}
      <path
        d={progressPath}
        fill="none"
        stroke="#95521f"
        strokeWidth={3}
        strokeLinecap="round"
      />

      {/* Event markers */}
      {eventLabels.map(({ e, px, py, lx, ly, anchor }) => {
        const past = e.t <= currentT;
        const emphasized = e.id === "first_crack" || e.id === "second_crack";
        return (
          <g key={e.id} opacity={past ? 1 : 0.4}>
            <line
              x1={px}
              x2={px}
              y1={py}
              y2={H - M.bottom}
              stroke="#b86a22"
              strokeWidth={1}
              strokeDasharray="2 3"
            />
            <circle
              cx={px}
              cy={py}
              r={emphasized ? 5 : 3.5}
              fill={emphasized ? "#b86a22" : "#ffffff"}
              stroke="#b86a22"
              strokeWidth={1.5}
            />
            <text
              x={lx}
              y={ly}
              textAnchor={anchor}
              fontSize={10}
              fontWeight={emphasized ? 700 : 500}
              fill="#7a4320"
            >
              {e.label}
            </text>
          </g>
        );
      })}

      {/* Playhead */}
      <line
        x1={x(currentT)}
        x2={x(currentT)}
        y1={M.top}
        y2={H - M.bottom}
        stroke="#d4832d"
        strokeWidth={1.5}
      />
      <circle
        cx={x(currentT)}
        cy={y(curve.tempAt(currentT))}
        r={5}
        fill="#d4832d"
        stroke="#ffffff"
        strokeWidth={1.5}
      />
    </svg>
  );
}
