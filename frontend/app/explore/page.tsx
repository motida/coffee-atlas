"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getVarieties, searchSemantic, searchText } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

type Mode = "text" | "semantic";

const ENTITY_TYPES = [
  { id: "variety", label: "Varieties" },
  { id: "flavor", label: "Flavors" },
  { id: "country", label: "Countries" },
  { id: "region", label: "Regions" },
  { id: "processing", label: "Processing" },
  { id: "shop", label: "Shops" },
  { id: "roast_profile", label: "Roasts" },
] as const;

const SEMANTIC_TYPES = new Set(["variety", "flavor", "shop", "roast_profile"]);

// Species is a variety-only structured field, not a free-text term — filtering
// by it scopes results to varieties of that species.
const SPECIES_OPTIONS = ["Arabica", "Robusta"] as const;

const TYPE_LINK: Record<string, (id: string) => string> = {
  variety: (id) => `/explore/varieties/${id}`,
  flavor: (id) => `/explore/flavors/${id}`,
  country: (id) => `/explore/countries/${id}`,
  region: (id) => `/explore/regions/${id}`,
  processing: (id) => `/explore/processing/${id}`,
  shop: (id) => `/explore/shops/${id}`,
};

const TYPE_BADGE: Record<string, string> = {
  variety: "bg-amber-100 text-amber-800",
  flavor: "bg-rose-100 text-rose-800",
  country: "bg-emerald-100 text-emerald-800",
  region: "bg-teal-100 text-teal-800",
  processing: "bg-sky-100 text-sky-800",
  shop: "bg-coffee-200 text-coffee-900",
  roast_profile: "bg-orange-100 text-orange-800",
};

const titleCase = (s: string) =>
  s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

const SEMANTIC_HINTS = [
  "fruity floral light roast",
  "chocolate nutty body",
  "high altitude rust resistant",
  "sweet citrus acidity",
];

export default function ExplorePage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("text");
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [species, setSpecies] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reqIdRef = useRef(0);

  // The species facet only makes sense while varieties are in the result set.
  const varietyInScope =
    selectedTypes.size === 0 || selectedTypes.has("variety");

  // Drop a stale species filter if the user narrows to non-variety types.
  useEffect(() => {
    if (!varietyInScope && species) setSpecies(null);
  }, [varietyInScope, species]);

  useEffect(() => {
    const trimmed = query.trim();
    // Nothing to do without either a query or a species filter to browse by.
    if (trimmed.length === 0 && !species) {
      setResults([]);
      setError(null);
      return;
    }

    const handle = setTimeout(() => {
      const myId = ++reqIdRef.current;
      setLoading(true);
      setError(null);

      const run = (): Promise<SearchResult[]> => {
        if (trimmed.length === 0) {
          // Species-only browse: list varieties of that species directly from
          // the structured endpoint rather than fuzzy-matching text.
          return getVarieties(30, 0, species ?? undefined).then((vs) =>
            vs.map((v) => ({
              id: v.id,
              entity_type: "variety",
              label: v.name,
              description: v.description,
              similarity: null,
            })),
          );
        }
        // A species filter scopes the search to varieties on the backend, so
        // don't also send entity_types (they'd be ignored anyway).
        const types = species
          ? undefined
          : selectedTypes.size > 0
            ? Array.from(selectedTypes)
            : mode === "semantic"
              ? Array.from(SEMANTIC_TYPES)
              : undefined;
        const fetcher = mode === "semantic" ? searchSemantic : searchText;
        return fetcher(trimmed, 30, types, species ?? undefined);
      };

      run()
        .then((rs) => {
          if (myId !== reqIdRef.current) return;
          setResults(rs);
        })
        .catch((e) => {
          if (myId !== reqIdRef.current) return;
          setError(String(e));
          setResults([]);
        })
        .finally(() => {
          if (myId !== reqIdRef.current) return;
          setLoading(false);
        });
    }, 250);

    return () => clearTimeout(handle);
  }, [query, mode, selectedTypes, species]);

  const toggleType = (id: string) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const visibleTypes = ENTITY_TYPES.filter(
    (t) => mode !== "semantic" || SEMANTIC_TYPES.has(t.id),
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-3xl font-bold text-coffee-900">Explore</h1>

      <div className="mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            mode === "semantic"
              ? "Describe what you're looking for: fruity floral light roast..."
              : "Search varieties, flavors, countries, regions, shops..."
          }
          className="w-full rounded-lg border border-coffee-200 bg-white px-4 py-3 text-sm focus:border-coffee-500 focus:outline-none focus:ring-1 focus:ring-coffee-500"
        />
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="inline-flex overflow-hidden rounded-md border border-coffee-200 text-xs">
          <button
            type="button"
            onClick={() => setMode("text")}
            className={`px-3 py-1.5 ${mode === "text" ? "bg-coffee-700 text-white" : "bg-white text-coffee-700 hover:bg-coffee-50"}`}
          >
            Text
          </button>
          <button
            type="button"
            onClick={() => setMode("semantic")}
            className={`px-3 py-1.5 ${mode === "semantic" ? "bg-coffee-700 text-white" : "bg-white text-coffee-700 hover:bg-coffee-50"}`}
          >
            Semantic
          </button>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {visibleTypes.map((t) => {
            const active = selectedTypes.has(t.id);
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => toggleType(t.id)}
                className={`rounded-full border px-3 py-1 text-xs ${
                  active
                    ? "border-coffee-700 bg-coffee-700 text-white"
                    : "border-coffee-200 bg-white text-coffee-700 hover:border-coffee-400"
                }`}
              >
                {t.label}
              </button>
            );
          })}
          {(selectedTypes.size > 0 || species) && (
            <button
              type="button"
              onClick={() => {
                setSelectedTypes(new Set());
                setSpecies(null);
              }}
              className="text-xs text-coffee-600 underline hover:text-coffee-800"
            >
              clear
            </button>
          )}
        </div>

        {varietyInScope && (
          <div className="inline-flex items-center gap-1.5">
            <span className="text-xs text-coffee-600">Species:</span>
            <div className="inline-flex overflow-hidden rounded-md border border-coffee-200 text-xs">
              <button
                type="button"
                onClick={() => setSpecies(null)}
                className={`px-2.5 py-1 ${species === null ? "bg-coffee-700 text-white" : "bg-white text-coffee-700 hover:bg-coffee-50"}`}
              >
                All
              </button>
              {SPECIES_OPTIONS.map((sp) => (
                <button
                  key={sp}
                  type="button"
                  onClick={() => setSpecies(sp)}
                  className={`border-l border-coffee-200 px-2.5 py-1 ${species === sp ? "bg-coffee-700 text-white" : "bg-white text-coffee-700 hover:bg-coffee-50"}`}
                >
                  {sp}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <span className="text-xs text-gray-500">Searching…</span>
        )}
      </div>

      {mode === "semantic" && query.length === 0 && !species && (
        <div className="mb-6 rounded-lg border border-coffee-200 bg-coffee-50 px-4 py-3 text-xs text-coffee-700">
          Semantic search uses Gemini embeddings over varieties + flavor
          attributes. Try:{" "}
          {SEMANTIC_HINTS.map((h, i) => (
            <span key={h}>
              <button
                type="button"
                onClick={() => setQuery(h)}
                className="underline hover:text-coffee-900"
              >
                {h}
              </button>
              {i < SEMANTIC_HINTS.length - 1 ? ", " : ""}
            </span>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && query.trim().length > 0 && results.length === 0 && !error && (
        <p className="text-sm text-gray-500">
          No results for &ldquo;{query}&rdquo;.
        </p>
      )}

      <ul className="grid grid-cols-1 gap-2">
        {results.map((r) => {
          const href = TYPE_LINK[r.entity_type]?.(r.id);
          const label =
            r.entity_type === "region" ? titleCase(r.label) : r.label;
          const card = (
            <div className="flex items-start gap-3 rounded-lg border border-coffee-200 bg-white px-4 py-3 transition hover:border-coffee-400 hover:bg-coffee-50">
              <span
                className={`mt-0.5 inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${TYPE_BADGE[r.entity_type] ?? "bg-gray-100 text-gray-700"}`}
              >
                {r.entity_type}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-sm font-medium text-coffee-900">
                    {label}
                  </span>
                  {r.similarity !== null && (
                    <span className="shrink-0 text-[10px] text-gray-500">
                      {r.similarity.toFixed(3)}
                    </span>
                  )}
                </div>
                {r.description && (
                  <p className="mt-0.5 line-clamp-2 text-xs text-gray-600">
                    {r.description}
                  </p>
                )}
              </div>
            </div>
          );
          return (
            <li key={`${r.entity_type}:${r.id}`}>
              {href ? (
                <Link href={href} className="block">
                  {card}
                </Link>
              ) : (
                card
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
