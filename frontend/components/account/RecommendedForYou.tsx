"use client";

import { useEffect, useState } from "react";
import { CardGrid, EntityCard, Section } from "@/components/explore/EntityPage";
import { getRecommendationsForYou } from "@/lib/api";
import { entityHref } from "@/lib/entity-config";
import type { Recommendation } from "@/lib/types";

/** A personalized feed on the account page, built from the user's favorites and
 *  cupping notes (taste-centroid cosine over the catalog). Renders nothing when
 *  the user has no activity yet, so it self-hides for brand-new accounts. */
export function RecommendedForYou({ entityType = "product" }: { entityType?: string }) {
  const [recs, setRecs] = useState<Recommendation[]>([]);

  useEffect(() => {
    let active = true;
    getRecommendationsForYou(entityType)
      .then((r) => active && setRecs(r))
      .catch(() => active && setRecs([]));
    return () => {
      active = false;
    };
  }, [entityType]);

  const cards = recs
    .map((r) => ({ rec: r, href: entityHref(r.entity_type, r.id) }))
    .filter((c): c is { rec: Recommendation; href: string } => c.href !== null);
  if (cards.length === 0) return null;

  return (
    <Section title="Recommended for you">
      <CardGrid>
        {cards.map(({ rec, href }) => (
          <EntityCard
            key={`${rec.entity_type}:${rec.id}`}
            href={href}
            title={rec.label}
            subtitle={rec.reason ?? undefined}
          />
        ))}
      </CardGrid>
    </Section>
  );
}
