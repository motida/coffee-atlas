"use client";

import { useEffect, useState } from "react";
import {
  getProcessingMethod,
  getProcessingMethodFlavor,
  getProcessingMethodVarieties,
} from "@/lib/api";
import { EntityCard, EntityPage, Field, Section } from "@/components/explore/EntityPage";
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
    </div>
  );
}

export default function ProcessingPage({ params }: { params: { id: string } }) {
  const [method, setMethod] = useState<ProcessingMethod | null>(null);
  const [flavors, setFlavors] = useState<ProcessingFlavorLink[]>([]);
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProcessingMethod(params.id)
      .then(setMethod)
      .catch((e) => setError(String(e)));
    getProcessingMethodFlavor(params.id)
      .then(setFlavors)
      .catch(() => setFlavors([]));
    getProcessingMethodVarieties(params.id)
      .then(setVarieties)
      .catch(() => setVarieties([]));
  }, [params.id]);

  if (error) {
    return (
      <EntityPage type="Processing method" title="Not found">
        <p className="text-sm text-red-600">{error}</p>
      </EntityPage>
    );
  }

  if (!method) {
    return (
      <EntityPage type="Processing method" title="Loading…">
        <p className="text-sm text-gray-500">Loading processing method…</p>
      </EntityPage>
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
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {varieties.map((v) => (
            <EntityCard
              key={v.id}
              href={`/explore/varieties/${v.id}`}
              title={v.name}
              subtitle={[v.species, v.genetic_group].filter(Boolean).join(" · ") || undefined}
            />
          ))}
        </div>
      </Section>
    </EntityPage>
  );
}
