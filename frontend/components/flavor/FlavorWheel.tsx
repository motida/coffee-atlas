"use client";

import { useEffect, useRef } from "react";

export default function FlavorWheel() {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    // TODO: Build interactive flavor wheel
    // - Fetch hierarchy from /api/v1/flavor/wheel
    // - Create concentric ring layout (category → subcategory → attribute)
    // - Use d3.arc() for each segment
    // - Add click handlers to filter by flavor
    // - Highlight segments when a variety or origin is selected
  }, []);

  return (
    <div className="flex items-center justify-center p-8">
      <svg ref={svgRef} width={500} height={500} viewBox="0 0 500 500">
        <circle
          cx={250}
          cy={250}
          r={200}
          fill="none"
          stroke="#d4832d"
          strokeWidth={2}
        />
        <circle
          cx={250}
          cy={250}
          r={140}
          fill="none"
          stroke="#e9bd7e"
          strokeWidth={1}
        />
        <circle
          cx={250}
          cy={250}
          r={80}
          fill="none"
          stroke="#f2d8b0"
          strokeWidth={1}
        />
        <text x={250} y={250} textAnchor="middle" fill="#7a4320" fontSize="14">
          Flavor Wheel
        </text>
      </svg>
    </div>
  );
}
