"use client";

import { useEffect, useState } from "react";
import { getOrigin, graphTraverse } from "@/lib/api";
import { EntityCard, EntityPage, Field, Section } from "@/components/explore/EntityPage";
import { titleCase } from "@/lib/text";
import type { Country, GraphNode } from "@/lib/types";

export default function CountryPage({ params }: { params: { id: string } }) {
  const [country, setCountry] = useState<Country | null>(null);
  const [regions, setRegions] = useState<GraphNode[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOrigin(params.id)
      .then(setCountry)
      .catch((e) => setError(String(e)));
    graphTraverse(params.id, 1)
      .then((res) =>
        setRegions(res.nodes.filter((n) => n.entity_type === "region")),
      )
      .catch(() => setRegions([]));
  }, [params.id]);

  if (error) {
    return (
      <EntityPage type="Country" title="Not found">
        <p className="text-sm text-red-600">{error}</p>
      </EntityPage>
    );
  }

  if (!country) {
    return (
      <EntityPage type="Country" title="Loading…">
        <p className="text-sm text-gray-500">Loading country…</p>
      </EntityPage>
    );
  }

  return (
    <EntityPage
      type="Country"
      title={country.name}
      subtitle={country.iso_code ?? undefined}
    >
      <Section title="Production">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="ISO code" value={country.iso_code} />
          <Field label="Annual volume" value={country.production_volume} />
          <Field label="Latitude" value={country.latitude} />
          <Field label="Longitude" value={country.longitude} />
        </dl>
      </Section>

      <Section
        title="Regions"
        count={regions.length}
        empty="No regions recorded for this country."
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {regions.map((r) => (
            <EntityCard
              key={r.id}
              href={`/explore/regions/${r.id}`}
              title={titleCase(r.label)}
            />
          ))}
        </div>
      </Section>
    </EntityPage>
  );
}
