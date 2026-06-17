/** Per-entity-type display metadata, shared by the search-results list (type
 *  badge + detail link) and the graph viewer (node color + legend + detail
 *  link) so the two can no longer drift. Key order matches the graph legend's
 *  display order. */
export interface EntityConfig {
  /** Hex fill for graph nodes and legend swatches. */
  color: string;
  /** Tailwind classes for the search-result type chip (search types only). */
  badge?: string;
  /** Detail-page href builder; omitted for types with no detail page. */
  href?: (id: string) => string;
}

export const ENTITY_CONFIG: Record<string, EntityConfig> = {
  variety: {
    color: "#d4832d",
    badge: "bg-amber-100 text-amber-800",
    href: (id) => `/explore/varieties/${id}`,
  },
  country: {
    color: "#10b981",
    badge: "bg-emerald-100 text-emerald-800",
    href: (id) => `/explore/countries/${id}`,
  },
  region: {
    color: "#14b8a6",
    badge: "bg-teal-100 text-teal-800",
    href: (id) => `/explore/regions/${id}`,
  },
  farm: { color: "#f59e0b" },
  flavor: {
    color: "#f43f5e",
    badge: "bg-rose-100 text-rose-800",
    href: (id) => `/explore/flavors/${id}`,
  },
  processing: {
    color: "#8b5cf6",
    badge: "bg-sky-100 text-sky-800",
    href: (id) => `/explore/processing/${id}`,
  },
  roast_profile: { color: "#b45309", badge: "bg-orange-100 text-orange-800" },
  product: {
    color: "#6366f1",
    badge: "bg-indigo-100 text-indigo-800",
    href: (id) => `/explore/products/${id}`,
  },
  roaster: { color: "#c026d3" },
  shop: {
    color: "#0891b2",
    badge: "bg-coffee-200 text-coffee-900",
    href: (id) => `/explore/shops/${id}`,
  },
};

/** Graph node fill / legend swatch color, with the viewer's slate fallback. */
export const entityColor = (type: string): string =>
  ENTITY_CONFIG[type]?.color ?? "#475569";

/** Detail-page href for an entity, or null if its type has no detail page. */
export const entityHref = (type: string, id: string): string | null =>
  ENTITY_CONFIG[type]?.href?.(id) ?? null;
