"use client";

import { useEffect, useState } from "react";
import { getVariety, getVarietyFlavor } from "@/lib/api";
import { EntityCard, EntityPage, Field, Section } from "@/components/explore/EntityPage";
import type { FlavorAttribute, Variety } from "@/lib/types";

export default function VarietyPage({ params }: { params: { id: string } }) {
  const [variety, setVariety] = useState<Variety | null>(null);
  const [flavors, setFlavors] = useState<FlavorAttribute[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getVariety(params.id)
      .then(setVariety)
      .catch((e) => setError(String(e)));
    getVarietyFlavor(params.id)
      .then(setFlavors)
      .catch(() => setFlavors([]));
  }, [params.id]);

  if (error) {
    return (
      <EntityPage type="Variety" title="Not found">
        <p className="text-sm text-red-600">{error}</p>
      </EntityPage>
    );
  }

  if (!variety) {
    return (
      <EntityPage type="Variety" title="Loading…">
        <p className="text-sm text-gray-500">Loading variety…</p>
      </EntityPage>
    );
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
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {flavors.map((f) => (
            <EntityCard
              key={f.id}
              href={`/explore/flavors/${f.id}`}
              title={f.name}
              subtitle={[f.category, f.subcategory].filter(Boolean).join(" · ") || undefined}
            />
          ))}
        </div>
      </Section>
    </EntityPage>
  );
}
