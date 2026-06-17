"use client";

import { useEffect, useState } from "react";
import { getOrigin, getRegion, graphTraverse } from "@/lib/api";
import { EntityDetailLoader, EntityPage, Field, Section } from "@/components/explore/EntityPage";
import { useEntityDetail } from "@/lib/hooks";
import { titleCase } from "@/lib/text";
import type { Country, GraphNode, Region } from "@/lib/types";

export default function RegionPage({ params }: { params: { id: string } }) {
  const [country, setCountry] = useState<Country | null>(null);
  const [farms, setFarms] = useState<GraphNode[]>([]);
  const { entity: region, error } = useEntityDetail<Region>(
    params.id,
    getRegion,
    (id) => {
      graphTraverse(id, 1)
        .then((res) => setFarms(res.nodes.filter((n) => n.entity_type === "farm")))
        .catch(() => setFarms([]));
    },
  );

  // The parent country is derived from the loaded region's country_id.
  useEffect(() => {
    if (region?.country_id) {
      getOrigin(region.country_id)
        .then(setCountry)
        .catch(() => setCountry(null));
    }
  }, [region]);

  if (error || !region) {
    return <EntityDetailLoader type="Region" error={error} loadingLabel="Loading region…" />;
  }

  const altitude =
    region.altitude_min || region.altitude_max
      ? `${region.altitude_min ?? "?"}–${region.altitude_max ?? "?"} m`
      : null;

  return (
    <EntityPage type="Region" title={titleCase(region.name)} subtitle={country?.name}>
      <Section title="Geography">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Altitude" value={altitude} />
          <Field label="Latitude" value={region.latitude} />
          <Field label="Longitude" value={region.longitude} />
        </dl>
      </Section>

      <Section title="Farms" count={farms.length} empty="No farms recorded in this region.">
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
