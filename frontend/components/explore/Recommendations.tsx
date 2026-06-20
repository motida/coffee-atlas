"use client";

import { useEffect, useState } from "react";
import { CardGrid, EntityCard, Section } from "@/components/explore/EntityPage";
import { getRecommendations } from "@/lib/api";
import { entityHref } from "@/lib/entity-config";
import { titleCase } from "@/lib/text";
import type { Recommendation } from "@/lib/types";

interface RecommendationsProps {
  entityType: string;
  entityId: string;
  /** Section heading; defaults to a friendly "You might also like". */
  title?: string;
}

/** "You might also like" — same-type peers ranked by the hybrid embedding +
 *  graph recommender. Renders nothing until results arrive (and nothing at all
 *  if there are none), so it's a safe drop-in on any detail page. */
export function Recommendations({ entityType, entityId, title }: RecommendationsProps) {
  const [recs, setRecs] = useState<Recommendation[]>([]);

  useEffect(() => {
    let active = true;
    getRecommendations(entityType, entityId)
      .then((r) => active && setRecs(r))
      .catch(() => active && setRecs([]));
    return () => {
      active = false;
    };
  }, [entityType, entityId]);

  // Only render once we have something — keeps the page clean when a sparsely
  // connected entity has no peers to suggest.
  const cards = recs
    .map((r) => ({ rec: r, href: entityHref(r.entity_type, r.id) }))
    .filter((c): c is { rec: Recommendation; href: string } => c.href !== null);
  if (cards.length === 0) return null;

  return (
    <Section title={title ?? "You might also like"}>
      <CardGrid>
        {cards.map(({ rec, href }) => (
          <EntityCard
            key={`${rec.entity_type}:${rec.id}`}
            href={href}
            title={rec.entity_type === "region" ? titleCase(rec.label) : rec.label}
            subtitle={rec.reason ?? undefined}
          />
        ))}
      </CardGrid>
    </Section>
  );
}
