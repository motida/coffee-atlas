"use client";

import * as d3 from "d3";
import { useEffect, useMemo, useState } from "react";
import { getFlavorWheel } from "@/lib/api";
import type { FlavorWheelLeaf, FlavorWheelData } from "@/lib/types";

const SIZE = 720;
const RADIUS = SIZE / 2 - 8;

const CATEGORY_COLORS: Record<string, string> = {
  Floral: "#e8a8c8",
  Fruity: "#e07b6b",
  "Sour/Fermented": "#e9c44a",
  "Green/Vegetative": "#7aa563",
  Other: "#9ca3af",
  Roasted: "#7a4320",
  Spices: "#b86a22",
  "Nutty/Cocoa": "#c89971",
  Sweet: "#df9c4b",
};

const FALLBACK_COLOR = "#9ca3af";

type Depth = 1 | 2 | 3;

interface WheelNode {
  name: string;
  depth: Depth;
  category: string;
  subcategory?: string;
  attribute?: FlavorWheelLeaf;
  children?: WheelNode[];
}

function buildHierarchy(data: FlavorWheelData): WheelNode {
  const categories: WheelNode[] = Object.entries(data).map(
    ([catName, subs]) => {
      const subNodes: WheelNode[] = Object.entries(subs).map(
        ([subName, leaves]) => ({
          name: subName,
          depth: 2,
          category: catName,
          subcategory: subName,
          children: leaves.map((leaf) => ({
            name: leaf.name,
            depth: 3,
            category: catName,
            subcategory: subName,
            attribute: leaf,
          })),
        }),
      );
      return {
        name: catName,
        depth: 1,
        category: catName,
        children: subNodes,
      };
    },
  );
  return {
    name: "root",
    depth: 1 as Depth,
    category: "",
    children: categories,
  };
}

function shade(hex: string, lightenBy: number): string {
  const c = d3.color(hex);
  if (!c) return hex;
  return c.brighter(lightenBy).formatHex();
}

export default function FlavorWheel() {
  const [data, setData] = useState<FlavorWheelData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<FlavorWheelLeaf | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    getFlavorWheel()
      .then(setData)
      .catch((e) => setError(e.message ?? String(e)));
  }, []);

  const segments = useMemo(() => {
    if (!data) return null;
    const root = d3
      .hierarchy<WheelNode>(buildHierarchy(data))
      .sum((d) => (d.children ? 0 : 1))
      .sort((a, b) => (a.data.name < b.data.name ? -1 : 1));

    const partitioned = d3
      .partition<WheelNode>()
      .size([2 * Math.PI, 3])(root);

    const arc = d3
      .arc<d3.HierarchyRectangularNode<WheelNode>>()
      .startAngle((d) => d.x0)
      .endAngle((d) => d.x1)
      .innerRadius((d) => (d.y0 / 3) * RADIUS)
      .outerRadius((d) => (d.y1 / 3) * RADIUS)
      .padAngle(0.003)
      .padRadius(RADIUS / 3);

    return partitioned
      .descendants()
      .filter((d) => d.depth >= 1 && d.depth <= 3)
      .map((d) => {
        const baseColor = CATEGORY_COLORS[d.data.category] ?? FALLBACK_COLOR;
        const color =
          d.depth === 1
            ? baseColor
            : d.depth === 2
              ? shade(baseColor, 0.5)
              : shade(baseColor, 0.9);
        return {
          node: d,
          path: arc(d) ?? "",
          color,
          midAngle: (d.x0 + d.x1) / 2,
          midRadius: ((d.y0 + d.y1) / 2 / 3) * RADIUS,
          arcAngle: d.x1 - d.x0,
        };
      });
  }, [data]);

  if (error) {
    return (
      <div className="flex h-[720px] items-center justify-center text-red-600">
        Failed to load flavor wheel: {error}
      </div>
    );
  }

  if (!segments) {
    return (
      <div className="flex h-[720px] items-center justify-center text-coffee-600">
        Loading flavor wheel…
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start gap-8 lg:flex-row">
      <div className="relative">
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`${-SIZE / 2} ${-SIZE / 2} ${SIZE} ${SIZE}`}
          className="select-none"
        >
          <g>
            {segments.map(({ node, path, color, midAngle, arcAngle }) => {
              const isLeaf = node.depth === 3;
              const id = node.data.attribute?.id ?? `${node.data.category}-${node.data.name}-${node.depth}`;
              const isHovered = hovered === id;
              const isSelected =
                isLeaf && selected?.id === node.data.attribute?.id;

              return (
                <path
                  key={id}
                  d={path}
                  fill={color}
                  stroke={isHovered || isSelected ? "#1f2937" : "#ffffff"}
                  strokeWidth={isHovered || isSelected ? 2 : 1}
                  style={{
                    cursor: isLeaf ? "pointer" : "default",
                    opacity: hovered && !isHovered ? 0.55 : 1,
                    transition: "opacity 120ms, stroke-width 120ms",
                  }}
                  onMouseEnter={() => setHovered(id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => {
                    if (isLeaf && node.data.attribute) {
                      setSelected(node.data.attribute);
                    }
                  }}
                >
                  <title>
                    {node.data.depth === 3
                      ? `${node.data.category} › ${node.data.subcategory} › ${node.data.name}`
                      : node.data.depth === 2
                        ? `${node.data.category} › ${node.data.name}`
                        : node.data.name}
                  </title>
                </path>
              );
            })}
          </g>
          <g pointerEvents="none">
            {segments
              .filter(({ node, arcAngle }) => node.depth === 1 && arcAngle > 0.05)
              .map(({ node, midAngle, midRadius }) => {
                const angle = midAngle - Math.PI / 2;
                const x = Math.cos(angle) * midRadius;
                const y = Math.sin(angle) * midRadius;
                return (
                  <text
                    key={`label-${node.data.name}`}
                    x={x}
                    y={y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={13}
                    fontWeight={600}
                    fill="#1f2937"
                  >
                    {node.data.name}
                  </text>
                );
              })}
          </g>
          <circle r={48} fill="#fdf8f0" stroke="#d4832d" strokeWidth={2} />
          <text
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={13}
            fontWeight={700}
            fill="#7a4320"
          >
            Coffee
          </text>
          <text
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={11}
            fill="#7a4320"
            y={16}
          >
            Flavor Wheel
          </text>
        </svg>
      </div>

      <aside className="w-full max-w-sm rounded-lg border border-coffee-200 bg-white p-6 shadow-sm lg:sticky lg:top-4">
        {selected ? (
          <div className="space-y-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-coffee-600">
                {selected.category} › {selected.subcategory}
              </p>
              <h2 className="text-2xl font-bold text-coffee-900">
                {selected.name}
              </h2>
            </div>
            {selected.description && (
              <p className="text-sm leading-relaxed text-gray-700">
                {selected.description}
              </p>
            )}
            {selected.sensory_reference && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-coffee-600">
                  Sensory reference
                </p>
                <p className="text-sm text-gray-700">
                  {selected.sensory_reference}
                </p>
              </div>
            )}
            {selected.intensity_reference && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-coffee-600">
                  Intensity reference
                </p>
                <p className="text-sm text-gray-700">
                  {selected.intensity_reference}
                </p>
              </div>
            )}
            <button
              type="button"
              className="text-xs text-coffee-600 underline hover:text-coffee-800"
              onClick={() => setSelected(null)}
            >
              Clear
            </button>
          </div>
        ) : (
          <div className="space-y-2 text-sm text-gray-600">
            <p className="font-medium text-coffee-900">
              SCAA / WCR Coffee Taster&apos;s Flavor Wheel
            </p>
            <p>
              110 attributes across 9 categories. Hover a slice to inspect, click an
              outer leaf to see its definition and sensory reference.
            </p>
          </div>
        )}
      </aside>
    </div>
  );
}
