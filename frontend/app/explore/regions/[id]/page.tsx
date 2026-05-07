"use client";

import { useEffect, useState } from "react";
import { getOrigin, getRegion, graphTraverse } from "@/lib/api";
import { EntityPage, Field, Section } from "@/components/explore/EntityPage";
import type { Country, GraphNode, Region } from "@/lib/types";

const titleCase = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase());

export default function RegionPage({ params }: { params: { id: string } }) {
  const [region, setRegion] = useState<Region | null>(null);
  const [country, setCountry] = useState<Country | null>(null);
  const [farms, setFarms] = useState<GraphNode[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRegion(params.id)
      .then((r) => {
        setRegion(r);
        if (r.country_id) {
          getOrigin(r.country_id).then(setCountry).catch(() => setCountry(null));
        }
      })
      .catch((e) => setError(String(e)));
    graphTraverse(params.id, 1)
      .then((res) => setFarms(res.nodes.filter((n) => n.entity_type === "farm")))
      .catch(() => setFarms([]));
  }, [params.id]);

  if (error) {
    return (
      <EntityPage type="Region" title="Not found">
        <p className="text-sm text-red-600">{error}</p>
      </EntityPage>
    );
  }

  if (!region) {
    return (
      <EntityPage type="Region" title="Loading…">
        <p className="text-sm text-gray-500">Loading region…</p>
      </EntityPage>
    );
  }

  const altitude =
    region.altitude_min || region.altitude_max
      ? `${region.altitude_min ?? "?"}–${region.altitude_max ?? "?"} m`
      : null;

  return (
    <EntityPage
      type="Region"
      title={titleCase(region.name)}
      subtitle={country?.name}
    >
      <Section title="Geography">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Altitude" value={altitude} />
          <Field label="Latitude" value={region.latitude} />
          <Field label="Longitude" value={region.longitude} />
        </dl>
      </Section>

      <Section
        title="Farms"
        count={farms.length}
        empty="No farms recorded in this region."
      >
        <ul className="grid grid-cols-1 gap-2 text-sm text-gray-800 sm:grid-cols-2 md:grid-cols-3">
          {farms.map((f) => (
            <li
              key={f.id}
              className="rounded-lg border border-coffee-200 bg-white px-4 py-2"
            >
              {f.label}
            </li>
          ))}
        </ul>
      </Section>
    </EntityPage>
  );
}
