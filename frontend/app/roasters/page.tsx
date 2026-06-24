"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getRoasters } from "@/lib/api";
import { CardGrid, EntityCard, Section } from "@/components/explore/EntityPage";
import type { RoasterListItem } from "@/lib/types";

type Sort = "count" | "name";

const SORTS: { id: Sort; label: string }[] = [
  { id: "count", label: "Most coffees" },
  { id: "name", label: "Name" },
];

/** Sentinel for the "show every location" choice in the location filter. */
const ALL_COUNTRIES = "All";

/** Shared pill styling for the sort and location filter chips. */
function chipClass(active: boolean): string {
  return active
    ? "rounded-full bg-coffee-700 px-3 py-1 font-medium text-white"
    : "rounded-full border border-coffee-200 bg-white px-3 py-1 text-gray-600 hover:border-coffee-400";
}

/** Roasters without a parseable country fall under this heading. */
const UNKNOWN_COUNTRY = "Other";

/** Split a free-text `location` ("Tel Aviv, Israel" / "Israel" / null) into a
 *  country (the last comma segment, used to group) and an optional city (the
 *  rest). The data has no structured location columns, so this is best-effort. */
function parseLocation(location: string | null): { country: string; city: string | null } {
  const parts = (location ?? "")
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  if (parts.length === 0) return { country: UNKNOWN_COUNTRY, city: null };
  const country = parts[parts.length - 1];
  const city = parts.length > 1 ? parts.slice(0, -1).join(", ") : null;
  return { country, city };
}

/** Within a country section the heading already names the country, so the card
 *  subtitle shows the city (when known) and the coffee count. */
function subtitle(r: RoasterListItem, city: string | null): string | undefined {
  const coffees = `${r.product_count} coffee${r.product_count === 1 ? "" : "s"}`;
  return [city, coffees].filter(Boolean).join(" · ") || undefined;
}

interface CountryGroup {
  country: string;
  roasters: RoasterListItem[];
  totalCoffees: number;
}

/** Bucket roasters by derived country, preserving the API's within-group order
 *  (already sorted by `sort`). Group order follows the same toggle: "Most
 *  coffees" orders countries by total coffees desc, "Name" alphabetically. The
 *  unknown-location bucket always sorts last. */
function groupByCountry(roasters: RoasterListItem[], sort: Sort): CountryGroup[] {
  const byCountry = new Map<string, CountryGroup>();
  for (const r of roasters) {
    const { country } = parseLocation(r.location);
    let group = byCountry.get(country);
    if (!group) {
      group = { country, roasters: [], totalCoffees: 0 };
      byCountry.set(country, group);
    }
    group.roasters.push(r);
    group.totalCoffees += r.product_count;
  }

  return Array.from(byCountry.values()).sort((a, b) => {
    const aUnknown = a.country === UNKNOWN_COUNTRY;
    const bUnknown = b.country === UNKNOWN_COUNTRY;
    if (aUnknown !== bUnknown) return aUnknown ? 1 : -1;
    if (sort === "count" && b.totalCoffees !== a.totalCoffees) {
      return b.totalCoffees - a.totalCoffees;
    }
    return a.country.localeCompare(b.country);
  });
}

export default function RoastersPage() {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("count");
  const [country, setCountry] = useState<string>(ALL_COUNTRIES);
  const [roasters, setRoasters] = useState<RoasterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reqIdRef = useRef(0);

  const groups = useMemo(() => groupByCountry(roasters, sort), [roasters, sort]);

  // Fall back to "All" when the selected country isn't among the current
  // results (e.g. a search narrowed it away) — keeps the selection coherent
  // without a stale chip highlighted on an empty list.
  const activeCountry =
    country !== ALL_COUNTRIES && groups.some((g) => g.country === country)
      ? country
      : ALL_COUNTRIES;
  const visibleGroups =
    activeCountry === ALL_COUNTRIES
      ? groups
      : groups.filter((g) => g.country === activeCountry);

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

      <div className="mb-3 flex items-center gap-2 text-xs">
        <span className="text-gray-500">Sort by</span>
        {SORTS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSort(s.id)}
            className={chipClass(sort === s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {groups.length > 1 && (
        <div className="mb-6 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-gray-500">Location</span>
          <button
            type="button"
            onClick={() => setCountry(ALL_COUNTRIES)}
            className={chipClass(activeCountry === ALL_COUNTRIES)}
          >
            All ({roasters.length})
          </button>
          {groups.map((g) => (
            <button
              key={g.country}
              type="button"
              onClick={() => setCountry(g.country)}
              className={chipClass(activeCountry === g.country)}
            >
              {g.country} ({g.roasters.length})
            </button>
          ))}
        </div>
      )}

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

      <div className="space-y-8">
        {visibleGroups.map((group) => (
          <Section key={group.country} title={group.country} count={group.roasters.length}>
            <CardGrid>
              {group.roasters.map((r) => (
                <EntityCard
                  key={r.id}
                  href={`/explore/roasters/${r.id}`}
                  title={r.name}
                  subtitle={subtitle(r, parseLocation(r.location).city)}
                />
              ))}
            </CardGrid>
          </Section>
        ))}
      </div>
    </div>
  );
}
