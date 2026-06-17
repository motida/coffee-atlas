"use client";

import { useState } from "react";
import { getFlavorAttribute, graphTraverse } from "@/lib/api";
import {
  CardGrid,
  EntityCard,
  EntityDetailLoader,
  EntityPage,
  Field,
  Section,
} from "@/components/explore/EntityPage";
import { useEntityDetail } from "@/lib/hooks";
import type { FlavorAttribute, GraphNode } from "@/lib/types";

export default function FlavorPage({ params }: { params: { id: string } }) {
  const [varieties, setVarieties] = useState<GraphNode[]>([]);
  const { entity: attribute, error } = useEntityDetail<FlavorAttribute>(
    params.id,
    getFlavorAttribute,
    (id) => {
      graphTraverse(id, 1)
        .then((res) => setVarieties(res.nodes.filter((n) => n.entity_type === "variety")))
        .catch(() => setVarieties([]));
    },
  );

  if (error || !attribute) {
    return (
      <EntityDetailLoader type="Flavor" error={error} loadingLabel="Loading flavor attribute…" />
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
        <CardGrid>
          {varieties.map((v) => (
            <EntityCard key={v.id} href={`/explore/varieties/${v.id}`} title={v.label} />
          ))}
        </CardGrid>
      </Section>
    </EntityPage>
  );
}
