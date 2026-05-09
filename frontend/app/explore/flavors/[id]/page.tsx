"use client";

import { useEffect, useState } from "react";
import { getFlavorAttribute, graphTraverse } from "@/lib/api";
import { EntityCard, EntityPage, Field, Section } from "@/components/explore/EntityPage";
import type { FlavorAttribute, GraphNode } from "@/lib/types";

export default function FlavorPage({ params }: { params: { id: string } }) {
  const [attribute, setAttribute] = useState<FlavorAttribute | null>(null);
  const [varieties, setVarieties] = useState<GraphNode[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFlavorAttribute(params.id)
      .then(setAttribute)
      .catch((e) => setError(String(e)));
    graphTraverse(params.id, 1)
      .then((res) =>
        setVarieties(res.nodes.filter((n) => n.entity_type === "variety")),
      )
      .catch(() => setVarieties([]));
  }, [params.id]);

  if (error) {
    return (
      <EntityPage type="Flavor" title="Not found">
        <p className="text-sm text-red-600">{error}</p>
      </EntityPage>
    );
  }

  if (!attribute) {
    return (
      <EntityPage type="Flavor" title="Loading…">
        <p className="text-sm text-gray-500">Loading flavor attribute…</p>
      </EntityPage>
    );
  }

  return (
    <EntityPage
      type="Flavor"
      title={attribute.name}
      subtitle={[attribute.category, attribute.subcategory].filter(Boolean).join(" · ") || undefined}
    >
      <Section title="Reference">
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Category" value={attribute.category} />
          <Field label="Subcategory" value={attribute.subcategory} />
          <Field label="Intensity reference" value={attribute.intensity_reference} />
          <Field label="Sensory reference" value={attribute.sensory_reference} />
        </dl>
      </Section>

      {attribute.description && (
        <Section title="Definition">
          <p className="text-sm leading-relaxed text-gray-800">{attribute.description}</p>
        </Section>
      )}

      <Section
        title="Varieties exhibiting this flavor"
        count={varieties.length}
        empty="No varieties linked to this flavor yet."
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {varieties.map((v) => (
            <EntityCard key={v.id} href={`/explore/varieties/${v.id}`} title={v.label} />
          ))}
        </div>
      </Section>
    </EntityPage>
  );
}
