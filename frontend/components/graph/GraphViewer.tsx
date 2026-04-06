"use client";

import { useEffect, useRef } from "react";

export default function GraphViewer() {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    // TODO: Initialize d3-force simulation
    // - Fetch graph data from /api/v1/graph/traverse
    // - Create nodes and links
    // - Set up force simulation (charge, center, link forces)
    // - Render circles for nodes, lines for edges
    // - Add drag, zoom, and click-to-expand interactivity
  }, []);

  return (
    <div className="flex h-full items-center justify-center bg-gray-50">
      <svg
        ref={svgRef}
        className="h-full w-full"
        style={{ minHeight: "500px" }}
      >
        <text x="50%" y="50%" textAnchor="middle" fill="#7a4320" fontSize="16">
          Graph visualization — click a node to explore connections
        </text>
      </svg>
    </div>
  );
}
