"use client";

import { useEffect, useRef, useState } from "react";
import { getRoasters } from "@/lib/api";
import { CardGrid, EntityCard } from "@/components/explore/EntityPage";
import type { RoasterListItem } from "@/lib/types";

type Sort = "count" | "name";

const SORTS: { id: Sort; label: string }[] = [
  { id: "count", label: "Most coffees" },
  { id: "name", label: "Name" },
];

function subtitle(r: RoasterListItem): string | undefined {
  const coffees = `${r.product_count} coffee${r.product_count === 1 ? "" : "s"}`;
  return [r.location, coffees].filter(Boolean).join(" · ") || undefined;
}

export default function RoastersPage() {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("count");
  const [roasters, setRoasters] = useState<RoasterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reqIdRef = useRef(0);

  useEffect(() => {
    const handle = setTimeout(() => {
      const myId = ++reqIdRef.current;
      setLoading(true);
      setError(null);

      getRoasters(100, 0, { search: search.trim() || undefined, sort })
        .then((rs) => {
          if (myId !== reqIdRef.current) return;
          setRoasters(rs);
        })
        .catch((e) => {
          if (myId !== reqIdRef.current) return;
          setError(String(e));
          setRoasters([]);
        })
        .finally(() => {
          if (myId !== reqIdRef.current) return;
          setLoading(false);
        });
    }, 250);

    return () => clearTimeout(handle);
  }, [search, sort]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-2 text-3xl font-bold text-coffee-900">Roasters</h1>
      <p className="mb-6 text-sm text-gray-600">
        Specialty coffee roasters and the coffees they offer.
      </p>

      <div className="mb-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search roasters by name..."
          className="w-full rounded-lg border border-coffee-200 bg-white px-4 py-3 text-sm focus:border-coffee-500 focus:outline-none focus:ring-1 focus:ring-coffee-500"
        />
      </div>

      <div className="mb-6 flex items-center gap-2 text-xs">
        <span className="text-gray-500">Sort by</span>
        {SORTS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSort(s.id)}
            className={
              sort === s.id
                ? "rounded-full bg-coffee-700 px-3 py-1 font-medium text-white"
                : "rounded-full border border-coffee-200 bg-white px-3 py-1 text-gray-600 hover:border-coffee-400"
            }
          >
            {s.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && roasters.length === 0 && (
        <p className="text-sm text-gray-500">
          {search.trim() ? `No roasters matching "${search}".` : "No roasters yet."}
        </p>
      )}

      <CardGrid>
        {roasters.map((r) => (
          <EntityCard
            key={r.id}
            href={`/explore/roasters/${r.id}`}
            title={r.name}
            subtitle={subtitle(r)}
          />
        ))}
      </CardGrid>
    </div>
  );
}
