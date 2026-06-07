"use client";

import * as d3 from "d3";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { graphTraverse, searchText } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

const ENTITY_COLORS: Record<string, string> = {
  variety: "#d4832d",
  country: "#10b981",
  region: "#14b8a6",
  farm: "#f59e0b",
  flavor: "#f43f5e",
  processing: "#8b5cf6",
};

const EDGE_TYPES: { id: string; label: string }[] = [
  { id: "country_region", label: "Country → Region" },
  { id: "region_farm", label: "Region → Farm" },
  { id: "country_variety", label: "Country → Variety" },
  { id: "region_variety", label: "Region → Variety" },
  { id: "farm_variety", label: "Farm → Variety" },
  { id: "variety_processing", label: "Variety → Processing" },
  { id: "variety_flavor", label: "Variety → Flavor" },
];

const ENTITY_DETAIL_URL: Record<string, (id: string) => string | null> = {
  variety: (id) => `/explore/varieties/${id}`,
  flavor: (id) => `/explore/flavors/${id}`,
  country: (id) => `/explore/countries/${id}`,
  region: (id) => `/explore/regions/${id}`,
  farm: () => null,
  processing: () => null,
};

const SEED_SEARCH_TYPES = ["variety", "country", "region", "flavor"];

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  entity_type: string;
  label: string;
}

interface SimEdge extends d3.SimulationLinkDatum<SimNode> {
  edge_type: string;
}

const edgeKey = (e: SimEdge) => {
  const s = typeof e.source === "string" ? e.source : (e.source as SimNode).id;
  const t = typeof e.target === "string" ? e.target : (e.target as SimNode).id;
  return `${s}|${t}|${e.edge_type}`;
};

export default function GraphViewer() {
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);
  const initializedRef = useRef(false);
  const inflightRef = useRef<AbortController | null>(null);

  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [edges, setEdges] = useState<SimEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null);
  const [enabledEdgeTypes, setEnabledEdgeTypes] = useState<Set<string>>(
    () => new Set(EDGE_TYPES.map((e) => e.id)),
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced search
  useEffect(() => {
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await searchText(q, 8, SEED_SEARCH_TYPES);
        if (!cancelled) setSearchResults(res);
      } catch {
        if (!cancelled) setSearchResults([]);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [searchQuery]);

  const isAbort = (err: unknown) =>
    err instanceof DOMException && err.name === "AbortError";

  const beginRequest = () => {
    inflightRef.current?.abort();
    const controller = new AbortController();
    inflightRef.current = controller;
    setIsLoading(true);
    setError(null);
    return controller;
  };

  const finishRequest = (controller: AbortController) => {
    if (inflightRef.current === controller) {
      inflightRef.current = null;
      setIsLoading(false);
    }
  };

  const seedFromNode = async (id: string) => {
    const controller = beginRequest();
    try {
      const result = await graphTraverse(id, 2, controller.signal);
      if (controller.signal.aborted) return;
      const newNodes: SimNode[] = result.nodes.map((n) => ({
        id: n.id,
        entity_type: n.entity_type,
        label: n.label,
      }));
      const newEdges: SimEdge[] = result.edges.map((e) => ({
        source: e.source_id,
        target: e.target_id,
        edge_type: e.edge_type,
      }));
      setNodes(newNodes);
      setEdges(newEdges);
      setSelectedNode(newNodes.find((n) => n.id === id) ?? null);
      setSearchQuery("");
      setSearchResults([]);
    } catch (err) {
      if (isAbort(err)) return;
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      finishRequest(controller);
    }
  };

  const expandNode = async (id: string) => {
    const controller = beginRequest();
    try {
      const result = await graphTraverse(id, 1, controller.signal);
      if (controller.signal.aborted) return;
      setNodes((existing) => {
        const byId = new Map(existing.map((n) => [n.id, n]));
        for (const n of result.nodes) {
          if (!byId.has(n.id)) {
            byId.set(n.id, {
              id: n.id,
              entity_type: n.entity_type,
              label: n.label,
            });
          }
        }
        return Array.from(byId.values());
      });
      setEdges((existing) => {
        const seen = new Set(existing.map(edgeKey));
        const merged = [...existing];
        for (const e of result.edges) {
          const candidate: SimEdge = {
            source: e.source_id,
            target: e.target_id,
            edge_type: e.edge_type,
          };
          if (!seen.has(edgeKey(candidate))) {
            merged.push(candidate);
          }
        }
        return merged;
      });
    } catch (err) {
      if (isAbort(err)) return;
      setError(err instanceof Error ? err.message : "Failed to expand node");
    } finally {
      finishRequest(controller);
    }
  };

  const visibleEdges = useMemo(
    () => edges.filter((e) => enabledEdgeTypes.has(e.edge_type)),
    [edges, enabledEdgeTypes],
  );

  // d3-force render
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const svg = d3.select(svgEl);
    const { width, height } = svgEl.getBoundingClientRect();

    let root = svg.select<SVGGElement>("g.root");
    if (root.empty()) {
      root = svg.append("g").attr("class", "root");
      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 8])
        .on("zoom", (event) => {
          root.attr("transform", event.transform.toString());
        });
      svg.call(zoom);

      // Deselect on canvas click — but ignore clicks that follow a pan.
      let mouseDownAt: { x: number; y: number } | null = null;
      svg.on("mousedown.deselect", (event: MouseEvent) => {
        mouseDownAt = { x: event.clientX, y: event.clientY };
      });
      svg.on("click.deselect", (event: MouseEvent) => {
        const start = mouseDownAt;
        mouseDownAt = null;
        if (start) {
          const dx = event.clientX - start.x;
          const dy = event.clientY - start.y;
          if (Math.hypot(dx, dy) > 5) return; // was a pan, not a click
        }
        const target = event.target as Element | null;
        if (target?.closest("g.node")) return; // bubbled from a node
        setSelectedNode(null);
      });
    }

    if (!simulationRef.current) {
      simulationRef.current = d3
        .forceSimulation<SimNode>()
        .force(
          "link",
          d3
            .forceLink<SimNode, SimEdge>()
            .id((d) => d.id)
            .distance(80)
            .strength(0.6),
        )
        .force("charge", d3.forceManyBody<SimNode>().strength(-220))
        .force("collide", d3.forceCollide<SimNode>(22))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("x", d3.forceX(width / 2).strength(0.04))
        .force("y", d3.forceY(height / 2).strength(0.04));
    }
    const simulation = simulationRef.current;

    if (!initializedRef.current && width > 0 && height > 0) {
      simulation
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("x", d3.forceX(width / 2).strength(0.04))
        .force("y", d3.forceY(height / 2).strength(0.04));
      initializedRef.current = true;
    }

    simulation.nodes(nodes);
    (simulation.force("link") as d3.ForceLink<SimNode, SimEdge>).links(
      visibleEdges,
    );
    simulation.alpha(0.4).restart();

    const edgeSel = root
      .selectAll<SVGLineElement, SimEdge>("line.edge")
      .data(visibleEdges, (d) => edgeKey(d));
    edgeSel.exit().remove();
    const edgeEnter = edgeSel
      .enter()
      .append("line")
      .attr("class", "edge")
      .attr("stroke", "#94a3b8")
      .attr("stroke-opacity", 0.5)
      .attr("stroke-width", 1.5);
    const allEdges = edgeEnter.merge(edgeSel);

    const nodeSel = root
      .selectAll<SVGGElement, SimNode>("g.node")
      .data(nodes, (d) => d.id);
    nodeSel.exit().remove();

    const nodeEnter = nodeSel
      .enter()
      .append("g")
      .attr("class", "node")
      .style("cursor", "pointer");

    nodeEnter
      .append("circle")
      .attr("r", 9)
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5);

    nodeEnter
      .append("text")
      .attr("x", 13)
      .attr("y", 4)
      .attr("font-size", 11)
      .attr("paint-order", "stroke")
      .attr("stroke", "#fff")
      .attr("stroke-width", 3)
      .attr("fill", "#1f2937");

    const allNodes = nodeEnter.merge(nodeSel);

    allNodes
      .select("circle")
      .attr("fill", (d) => ENTITY_COLORS[d.entity_type] ?? "#475569");

    allNodes
      .select("text")
      .text((d) =>
        d.label.length > 26 ? `${d.label.slice(0, 24)}…` : d.label,
      );

    allNodes.on("click", (event, d) => {
      event.stopPropagation();
      setSelectedNode(d);
    });

    allNodes.call(
      d3
        .drag<SVGGElement, SimNode>()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }),
    );

    simulation.on("tick", () => {
      allEdges
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);
      allNodes.attr(
        "transform",
        (d) => `translate(${d.x ?? 0},${d.y ?? 0})`,
      );
    });
  }, [nodes, visibleEdges]);

  // Highlight only — no simulation restart on selection change
  useEffect(() => {
    if (!svgRef.current) return;
    d3.select(svgRef.current)
      .selectAll<SVGGElement, SimNode>("g.node")
      .select<SVGCircleElement>("circle")
      .attr("stroke", (d) =>
        selectedNode && d.id === selectedNode.id ? "#1f2937" : "#fff",
      )
      .attr("stroke-width", (d) =>
        selectedNode && d.id === selectedNode.id ? 2.5 : 1.5,
      )
      .attr("r", (d) => (selectedNode && d.id === selectedNode.id ? 11 : 9));
  }, [selectedNode, nodes]);

  // Stop simulation + abort inflight on unmount
  useEffect(() => {
    return () => {
      simulationRef.current?.stop();
      inflightRef.current?.abort();
    };
  }, []);

  const detailHref = (() => {
    if (!selectedNode) return null;
    const builder = ENTITY_DETAIL_URL[selectedNode.entity_type];
    return builder ? builder(selectedNode.id) : null;
  })();

  return (
    <div className="relative h-full w-full">
      {/* Seed + filters panel */}
      <div className="absolute left-4 top-4 z-10 w-80 overflow-hidden rounded-lg border border-coffee-200 bg-white shadow-sm">
        <div className="border-b border-coffee-100 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-coffee-700">
            Seed
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search a variety, country, region, or flavor…"
            className="mt-2 w-full rounded border border-coffee-200 px-3 py-1.5 text-sm focus:border-coffee-500 focus:outline-none"
          />
          {searchResults.length > 0 && (
            <div className="mt-2 max-h-64 overflow-y-auto rounded border border-coffee-100">
              {searchResults.map((r) => (
                <button
                  key={`${r.entity_type}-${r.id}`}
                  onClick={() => seedFromNode(r.id)}
                  className="block w-full border-b border-coffee-100 px-2 py-1.5 text-left text-sm last:border-0 hover:bg-coffee-50"
                >
                  <span className="mr-2 inline-block w-14 text-[10px] uppercase tracking-wide text-coffee-600">
                    {r.entity_type}
                  </span>
                  <span className="text-coffee-900">{r.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="border-b border-coffee-100 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-coffee-700">
            Edges
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {EDGE_TYPES.map((et) => {
              const enabled = enabledEdgeTypes.has(et.id);
              return (
                <button
                  key={et.id}
                  onClick={() =>
                    setEnabledEdgeTypes((current) => {
                      const next = new Set(current);
                      if (next.has(et.id)) next.delete(et.id);
                      else next.add(et.id);
                      return next;
                    })
                  }
                  className={`rounded-full px-2 py-0.5 text-xs transition ${
                    enabled
                      ? "bg-coffee-200 text-coffee-900"
                      : "bg-gray-100 text-gray-400 hover:bg-gray-200"
                  }`}
                >
                  {et.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-coffee-700">
            Legend
          </div>
          <div className="mt-2 grid grid-cols-2 gap-1.5">
            {Object.entries(ENTITY_COLORS).map(([type, color]) => (
              <div
                key={type}
                className="flex items-center gap-1.5 text-xs text-gray-700"
              >
                <span
                  className="h-2.5 w-2.5 rounded-full ring-1 ring-white"
                  style={{ backgroundColor: color }}
                />
                <span className="capitalize">{type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Detail sidebar */}
      {selectedNode && (
        <div className="absolute right-4 top-4 z-10 w-72 rounded-lg border border-coffee-200 bg-white p-4 shadow-sm">
          <button
            onClick={() => setSelectedNode(null)}
            className="float-right text-xs text-gray-400 hover:text-gray-700"
            aria-label="Close"
          >
            ✕
          </button>
          <div className="text-xs uppercase tracking-wide text-coffee-600">
            {selectedNode.entity_type}
          </div>
          <div className="mt-1 text-base font-semibold text-coffee-900">
            {selectedNode.label}
          </div>
          <div className="mt-3 flex flex-col gap-2">
            <button
              onClick={() => expandNode(selectedNode.id)}
              disabled={isLoading}
              className="rounded bg-coffee-600 px-3 py-1.5 text-sm text-white hover:bg-coffee-700 disabled:opacity-50"
            >
              Expand neighbors
            </button>
            {detailHref && (
              <Link
                href={detailHref}
                className="rounded border border-coffee-300 px-3 py-1.5 text-center text-sm text-coffee-700 hover:bg-coffee-50"
              >
                View details →
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {nodes.length === 0 && !isLoading && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="rounded-lg bg-white px-6 py-6 text-center text-sm text-gray-600 shadow-sm">
            <p>Search a variety, country, region, or flavor to start.</p>
            <p className="mt-1 text-xs text-gray-400">
              Click any node to inspect. Drag to reposition. Scroll to zoom.
            </p>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="absolute bottom-4 right-4 z-10 rounded bg-white px-3 py-1.5 text-xs text-coffee-700 shadow">
          Loading…
        </div>
      )}

      {error && (
        <div className="absolute bottom-4 left-4 z-10 max-w-sm rounded bg-rose-50 px-3 py-1.5 text-xs text-rose-700 shadow">
          {error}
        </div>
      )}

      <svg ref={svgRef} className="h-full w-full bg-coffee-50" />
    </div>
  );
}
