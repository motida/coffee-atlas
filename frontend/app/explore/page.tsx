"use client";

import { useEffect, useRef, useState } from "react";
import { getVarieties, searchSemantic, searchText } from "@/lib/api";
import { SearchControls, type SearchMode } from "@/components/explore/SearchControls";
import { SearchResults } from "@/components/explore/SearchResults";
import type { SearchResult } from "@/lib/types";

const ENTITY_TYPES = [
  { id: "variety", label: "Varieties" },
  { id: "flavor", label: "Flavors" },
  { id: "country", label: "Countries" },
  { id: "region", label: "Regions" },
  { id: "processing", label: "Processing" },
  { id: "shop", label: "Shops" },
  { id: "roast_profile", label: "Roasts" },
  { id: "roaster", label: "Roasters" },
  { id: "product", label: "Products" },
] as const;

const SEMANTIC_TYPES = new Set(["variety", "flavor", "shop", "roast_profile", "product"]);

const SEMANTIC_HINTS = [
  "fruity floral light roast",
  "chocolate nutty body",
  "high altitude rust resistant",
  "sweet citrus acidity",
];

export default function ExplorePage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("text");
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [species, setSpecies] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reqIdRef = useRef(0);

  // The species facet only makes sense while varieties are in the result set.
  const varietyInScope = selectedTypes.size === 0 || selectedTypes.has("variety");

  // Drop a stale species filter if the user narrows to non-variety types.
  useEffect(() => {
    if (!varietyInScope && species) setSpecies(null);
  }, [varietyInScope, species]);

  useEffect(() => {
    const trimmed = query.trim();
    // Nothing to do without either a query or a species filter to browse by.
    if (trimmed.length === 0 && !species) {
      // Invalidate any in-flight request, or its late response would
      // repopulate results under the now-empty search box.
      reqIdRef.current++;
      setResults([]);
      setError(null);
      setLoading(false);
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

      <SearchControls
        mode={mode}
        onModeChange={setMode}
        visibleTypes={visibleTypes}
        selectedTypes={selectedTypes}
        onToggleType={toggleType}
        varietyInScope={varietyInScope}
        species={species}
        onSpeciesChange={setSpecies}
        onClear={() => {
          setSelectedTypes(new Set());
          setSpecies(null);
        }}
        loading={loading}
      />

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
        <p className="text-sm text-gray-500">No results for &ldquo;{query}&rdquo;.</p>
      )}

      <SearchResults results={results} />
    </div>
  );
}
