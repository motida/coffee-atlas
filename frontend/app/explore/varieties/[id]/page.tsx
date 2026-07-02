"use client";

import { useState } from "react";
import { getVariety, getVarietyFlavor } from "@/lib/api";
import {
  CardGrid,
  EntityCard,
  EntityDetailLoader,
  EntityPage,
  Field,
  Section,
} from "@/components/explore/EntityPage";
import { AddCuppingNote } from "@/components/account/AddCuppingNote";
import { FavoriteButton } from "@/components/account/FavoriteButton";
import { Recommendations } from "@/components/explore/Recommendations";
import { useEntityDetail } from "@/lib/hooks";
import type { Variety, VarietyFlavorLink } from "@/lib/types";

export default function VarietyPage({ params }: { params: { id: string } }) {
  const [flavors, setFlavors] = useState<VarietyFlavorLink[]>([]);
  const { entity: variety, error } = useEntityDetail<Variety>(
    params.id,
    getVariety,
    (id) => {
      getVarietyFlavor(id)
        .then(setFlavors)
        .catch(() => setFlavors([]));
    },
  );

  if (error || !variety) {
    return <EntityDetailLoader type="Variety" error={error} loadingLabel="Loading variety…" />;
  }

  const altitude =
    variety.optimal_altitude_min || variety.optimal_altitude_max
      ? `${variety.optimal_altitude_min ?? "?"}–${variety.optimal_altitude_max ?? "?"} m`
      : null;

  return (
    <EntityPage
      type="Variety"
      title={variety.name}
      subtitle={[variety.species, variety.genetic_group].filter(Boolean).join(" · ") || undefined}
      actions={
        <>
          <FavoriteButton entityType="variety" entityId={params.id} />
          <AddCuppingNote entityType="variety" entityId={params.id} />
        </>
      }
    >
      <Section title="Agronomic profile">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Yield potential" value={variety.yield_potential} />
          <Field label="Optimal altitude" value={altitude} />
          <Field label="Bean size" value={variety.bean_size} />
          <Field label="Cherry color" value={variety.cherry_color} />
          <Field label="Stature" value={variety.stature} />
          <Field label="Disease resistance" value={variety.disease_resistance} />
        </dl>
      </Section>

      {variety.description && (
        <Section title="Description">
          <p className="whitespace-pre-line text-sm leading-relaxed text-gray-800">
            {variety.description}
          </p>
        </Section>
      )}

      <Section
        title="Flavor associations"
        count={flavors.length}
        empty="No flavor attributes linked yet."
      >
        <CardGrid>
          {flavors.map((f) => (
            <EntityCard
              key={f.id}
              href={`/explore/flavors/${f.id}`}
              title={f.name}
              subtitle={[f.category, f.subcategory].filter(Boolean).join(" · ") || undefined}
            />
          ))}
        </CardGrid>
      </Section>

      <Recommendations entityType="variety" entityId={params.id} />
    </EntityPage>
  );
}
