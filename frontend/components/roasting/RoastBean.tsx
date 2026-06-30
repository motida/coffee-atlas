"use client";

import * as d3 from "d3";

/**
 * A single coffee bean drawn in SVG. `fill` is the roast color (green seed ->
 * roasted) and `sheen` the oily-surface highlight opacity for dark roasts. Both
 * recolor with a short CSS transition so play and scrub look fluid — the same
 * trick FlavorWheel uses on its path styles.
 */
export function RoastBean({
  fill,
  sheen,
  size = 220,
}: {
  fill: string;
  sheen: number;
  size?: number;
}) {
  const creaseStroke = d3.color(fill)?.darker(1).formatHex() ?? "#3b2412";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 240"
      className="select-none"
      role="img"
      aria-label="Coffee bean"
    >
      <defs>
        <radialGradient id="roast-bean-sheen" cx="38%" cy="28%" r="55%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="roast-bean-shade" cx="50%" cy="40%" r="62%">
          <stop offset="58%" stopColor="#000000" stopOpacity="0" />
          <stop offset="100%" stopColor="#000000" stopOpacity="0.28" />
        </radialGradient>
      </defs>

      {/* Bean body */}
      <ellipse
        cx={100}
        cy={120}
        rx={66}
        ry={98}
        fill={fill}
        style={{ transition: "fill 90ms linear" }}
      />
      {/* Rounded shading for volume */}
      <ellipse cx={100} cy={120} rx={66} ry={98} fill="url(#roast-bean-shade)" />
      {/* Center crease — an S-curve down the long axis */}
      <path
        d="M100 28 C 80 70, 120 108, 100 150 C 84 184, 114 198, 100 212"
        fill="none"
        stroke={creaseStroke}
        strokeWidth={4}
        strokeLinecap="round"
        style={{ transition: "stroke 90ms linear" }}
      />
      {/* Oily sheen — fades in only on dark roasts */}
      <ellipse
        cx={100}
        cy={120}
        rx={66}
        ry={98}
        fill="url(#roast-bean-sheen)"
        opacity={sheen}
        style={{ transition: "opacity 150ms linear" }}
      />
    </svg>
  );
}
