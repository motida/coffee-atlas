import Link from "next/link";
import { ENTITY_CONFIG, entityHref } from "@/lib/entity-config";
import { titleCase } from "@/lib/text";
import type { SearchResult } from "@/lib/types";

function ResultCard({ result }: { result: SearchResult }) {
  // Region labels arrive upper-cased from the cupping data; title-case them.
  const label = result.entity_type === "region" ? titleCase(result.label) : result.label;
  return (
    <div className="flex items-start gap-3 rounded-lg border border-coffee-200 bg-white px-4 py-3 transition hover:border-coffee-400 hover:bg-coffee-50">
      <span
        className={`mt-0.5 inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${ENTITY_CONFIG[result.entity_type]?.badge ?? "bg-gray-100 text-gray-700"}`}
      >
        {result.entity_type}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-medium text-coffee-900">{label}</span>
          {result.similarity !== null && (
            <span className="shrink-0 text-[10px] text-gray-500">
              {result.similarity.toFixed(3)}
            </span>
          )}
        </div>
        {result.description && (
          <p className="mt-0.5 line-clamp-2 text-xs text-gray-600">{result.description}</p>
        )}
      </div>
    </div>
  );
}

/** The search results list: each result links to its detail page when one exists. */
export function SearchResults({ results }: { results: SearchResult[] }) {
  return (
    <ul className="grid grid-cols-1 gap-2">
      {results.map((r) => {
        const href = entityHref(r.entity_type, r.id);
        return (
          <li key={`${r.entity_type}:${r.id}`}>
            {href ? (
              <Link href={href} className="block">
                <ResultCard result={r} />
              </Link>
            ) : (
              <ResultCard result={r} />
            )}
          </li>
        );
      })}
    </ul>
  );
}
