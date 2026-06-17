"use client";

import { useState } from "react";
import {
  getProcessingMethod,
  getProcessingMethodFlavor,
  getProcessingMethodVarieties,
} from "@/lib/api";
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
import type { ProcessingFlavorLink, ProcessingMethod, Variety } from "@/lib/types";

function FlavorGroup({
  label,
  tone,
  flavors,
}: {
  label: string;
  tone: "enhance" | "diminish";
  flavors: ProcessingFlavorLink[];
}) {
  const badge =
    tone === "enhance"
      ? "bg-emerald-100 text-emerald-800"
      : "bg-amber-100 text-amber-800";
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${badge}`}
        >
          {label}
        </span>
        <span className="text-xs text-gray-400">({flavors.length})</span>
      </div>
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
    </div>
  );
}

export default function ProcessingPage({ params }: { params: { id: string } }) {
  const [flavors, setFlavors] = useState<ProcessingFlavorLink[]>([]);
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const { entity: method, error } = useEntityDetail<ProcessingMethod>(
    params.id,
    getProcessingMethod,
    (id) => {
      getProcessingMethodFlavor(id)
        .then(setFlavors)
        .catch(() => setFlavors([]));
      getProcessingMethodVarieties(id)
        .then(setVarieties)
        .catch(() => setVarieties([]));
    },
  );

  if (error || !method) {
    return (
      <EntityDetailLoader
        type="Processing method"
        error={error}
        loadingLabel="Loading processing method…"
      />
    );
  }

  const enhances = flavors.filter((f) => f.effect === "enhances");
  const diminishes = flavors.filter((f) => f.effect === "diminishes");

  return (
    <EntityPage
      type="Processing method"
      title={method.name}
      subtitle={method.category ? titleCase(method.category) : undefined}
    >
      <Section title="Process characteristics">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field
            label="Category"
            value={method.category ? titleCase(method.category) : null}
          />
          <Field label="Fermentation duration" value={method.fermentation_duration} />
          <Field label="Drying duration" value={method.drying_duration} />
        </dl>
      </Section>

      {method.description && (
        <Section title="Description">
          <p className="whitespace-pre-line text-sm leading-relaxed text-gray-800">
            {method.description}
          </p>
        </Section>
      )}

      <Section
        title="Flavor impact"
        count={flavors.length}
        empty="No flavor associations linked yet."
      >
        <div className="space-y-5">
          {enhances.length > 0 && (
            <FlavorGroup label="Enhances" tone="enhance" flavors={enhances} />
          )}
          {diminishes.length > 0 && (
            <FlavorGroup label="Diminishes" tone="diminish" flavors={diminishes} />
          )}
        </div>
      </Section>

      <Section
        title="Varieties prepared this way"
        count={varieties.length}
        empty="No varieties linked to this method yet."
      >
        <CardGrid>
          {varieties.map((v) => (
            <EntityCard
              key={v.id}
              href={`/explore/varieties/${v.id}`}
              title={v.name}
              subtitle={[v.species, v.genetic_group].filter(Boolean).join(" · ") || undefined}
            />
          ))}
        </CardGrid>
      </Section>
    </EntityPage>
  );
}
