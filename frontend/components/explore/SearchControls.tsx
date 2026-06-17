export type SearchMode = "text" | "semantic";

// Species is a variety-only structured field, not a free-text term — filtering
// by it scopes results to varieties of that species.
const SPECIES_OPTIONS = ["Arabica", "Robusta"] as const;

interface SearchControlsProps {
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  visibleTypes: readonly { id: string; label: string }[];
  selectedTypes: Set<string>;
  onToggleType: (id: string) => void;
  varietyInScope: boolean;
  species: string | null;
  onSpeciesChange: (species: string | null) => void;
  onClear: () => void;
  loading: boolean;
}

/** The mode toggle + entity-type filter chips + species facet + loading note. */
export function SearchControls({
  mode,
  onModeChange,
  visibleTypes,
  selectedTypes,
  onToggleType,
  varietyInScope,
  species,
  onSpeciesChange,
  onClear,
  loading,
}: SearchControlsProps) {
  const hasFilters = selectedTypes.size > 0 || species !== null;
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3">
      <div className="inline-flex overflow-hidden rounded-md border border-coffee-200 text-xs">
        <button
          type="button"
          onClick={() => onModeChange("text")}
          className={`px-3 py-1.5 ${mode === "text" ? "bg-coffee-700 text-white" : "bg-white text-coffee-700 hover:bg-coffee-50"}`}
        >
          Text
        </button>
        <button
          type="button"
          onClick={() => onModeChange("semantic")}
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
              onClick={() => onToggleType(t.id)}
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
        {hasFilters && (
          <button
            type="button"
            onClick={onClear}
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
              onClick={() => onSpeciesChange(null)}
              className={`px-2.5 py-1 ${species === null ? "bg-coffee-700 text-white" : "bg-white text-coffee-700 hover:bg-coffee-50"}`}
            >
              All
            </button>
            {SPECIES_OPTIONS.map((sp) => (
              <button
                key={sp}
                type="button"
                onClick={() => onSpeciesChange(sp)}
                className={`border-l border-coffee-200 px-2.5 py-1 ${species === sp ? "bg-coffee-700 text-white" : "bg-white text-coffee-700 hover:bg-coffee-50"}`}
              >
                {sp}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && <span className="text-xs text-gray-500">Searching…</span>}
    </div>
  );
}
