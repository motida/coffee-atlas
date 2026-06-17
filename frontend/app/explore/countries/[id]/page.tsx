"use client";

import { useState } from "react";
import { getOrigin, graphTraverse } from "@/lib/api";
import {
  CardGrid,
  EntityCard,
  EntityDetailLoader,
  EntityPage,
  Field,
  Section,
} from "@/components/explore/EntityPage";
import { useEntityDetail } from "@/lib/hooks";
import { titleCase } from "@/lib/text";
import type { Country, GraphNode } from "@/lib/types";

export default function CountryPage({ params }: { params: { id: string } }) {
  const [regions, setRegions] = useState<GraphNode[]>([]);
  const { entity: country, error } = useEntityDetail<Country>(
    params.id,
    getOrigin,
    (id) => {
      graphTraverse(id, 1)
        .then((res) => setRegions(res.nodes.filter((n) => n.entity_type === "region")))
        .catch(() => setRegions([]));
    },
  );

  if (error || !country) {
    return <EntityDetailLoader type="Country" error={error} loadingLabel="Loading country…" />;
  }

  return (
    <EntityPage type="Country" title={country.name} subtitle={country.iso_code ?? undefined}>
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
        <CardGrid>
          {regions.map((r) => (
            <EntityCard key={r.id} href={`/explore/regions/${r.id}`} title={titleCase(r.label)} />
          ))}
        </CardGrid>
      </Section>
    </EntityPage>
  );
}
