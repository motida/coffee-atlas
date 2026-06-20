import { ENTITY_CONFIG } from "@/lib/entity-config";
import type { SearchResult } from "@/lib/types";

export const EDGE_TYPES: { id: string; label: string }[] = [
  { id: "country_region", label: "Country → Region" },
  { id: "region_farm", label: "Region → Farm" },
  { id: "country_variety", label: "Country → Variety" },
  { id: "region_variety", label: "Region → Variety" },
  { id: "farm_variety", label: "Farm → Variety" },
  { id: "variety_processing", label: "Variety → Processing" },
  { id: "variety_flavor", label: "Variety → Flavor" },
  { id: "roast_variety", label: "Roast → Variety" },
  { id: "product_variety", label: "Product → Variety" },
  { id: "product_country", label: "Product → Country" },
  { id: "product_region", label: "Product → Region" },
  { id: "product_flavor", label: "Product → Flavor" },
  { id: "product_roast", label: "Product → Roast" },
  { id: "roaster_product", label: "Roaster → Product" },
  { id: "shop_roaster", label: "Shop → Roaster" },
  { id: "shop_product", label: "Shop → Product" },
  { id: "shop_variety", label: "Shop → Variety" },
];

/** Display caps for the graph; `null` means "show all". */
const NODE_LIMIT_OPTIONS: (number | null)[] = [25, 50, 100, 250, null];

interface GraphControlsProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchResults: SearchResult[];
  onSeed: (id: string) => void;
  enabledEdgeTypes: Set<string>;
  onToggleEdge: (id: string) => void;
  nodeLimit: number | null;
  onNodeLimitChange: (limit: number | null) => void;
  displayedCount: number;
  totalCount: number;
}

/** The graph's left panel: seed search, edge-type toggles, and the color legend. */
export function GraphControls({
  searchQuery,
  onSearchChange,
  searchResults,
  onSeed,
  enabledEdgeTypes,
  onToggleEdge,
  nodeLimit,
  onNodeLimitChange,
  displayedCount,
  totalCount,
}: GraphControlsProps) {
  return (
    <div className="absolute left-4 top-4 z-10 w-80 overflow-hidden rounded-lg border border-coffee-200 bg-white shadow-sm">
      <div className="border-b border-coffee-100 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-coffee-700">
          Seed
        </div>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search a variety, country, region, flavor, or product…"
          className="mt-2 w-full rounded border border-coffee-200 px-3 py-1.5 text-sm focus:border-coffee-500 focus:outline-none"
        />
        {searchResults.length > 0 && (
          <div className="mt-2 max-h-64 overflow-y-auto rounded border border-coffee-100">
            {searchResults.map((r) => (
              <button
                key={`${r.entity_type}-${r.id}`}
                onClick={() => onSeed(r.id)}
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
                onClick={() => onToggleEdge(et.id)}
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

      <div className="border-b border-coffee-100 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-coffee-700">
          Max nodes
        </div>
        <select
          value={nodeLimit ?? "all"}
          onChange={(e) =>
            onNodeLimitChange(e.target.value === "all" ? null : Number(e.target.value))
          }
          className="mt-2 w-full rounded border border-coffee-200 px-3 py-1.5 text-sm focus:border-coffee-500 focus:outline-none"
        >
          {NODE_LIMIT_OPTIONS.map((opt) => (
            <option key={opt ?? "all"} value={opt ?? "all"}>
              {opt ?? "All"}
            </option>
          ))}
        </select>
        <div className="mt-1.5 text-xs text-coffee-600">
          {totalCount > displayedCount
            ? `Showing ${displayedCount} of ${totalCount} nodes`
            : `${totalCount} ${totalCount === 1 ? "node" : "nodes"}`}
        </div>
      </div>

      <div className="p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-coffee-700">
          Legend
        </div>
        <div className="mt-2 grid grid-cols-2 gap-1.5">
          {Object.entries(ENTITY_CONFIG).map(([type, { color }]) => (
            <div key={type} className="flex items-center gap-1.5 text-xs text-gray-700">
              <span
                className="h-2.5 w-2.5 rounded-full ring-1 ring-white"
                style={{ backgroundColor: color }}
              />
              <span className="capitalize">{type.replace("_", " ")}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
