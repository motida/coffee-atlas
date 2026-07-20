"use client";

import { useState } from "react";
import { getProducts, getRoaster } from "@/lib/api";
import {
  CardGrid,
  EntityCard,
  EntityDetailLoader,
  EntityPage,
  Field,
  Section,
} from "@/components/explore/EntityPage";
import { FavoriteButton } from "@/components/account/FavoriteButton";
import { useEntityDetail } from "@/lib/hooks";
import { formatPrice } from "@/lib/text";
import type { Product, Roaster } from "@/lib/types";

export default function RoasterPage({ params }: { params: { id: string } }) {
  const [products, setProducts] = useState<Product[]>([]);
  const { entity: roaster, error } = useEntityDetail<Roaster>(
    params.id,
    getRoaster,
    (id) => {
      getProducts(100, 0, id)
        .then(setProducts)
        .catch(() => setProducts([]));
    },
  );

  if (error || !roaster) {
    return <EntityDetailLoader type="Roaster" error={error} loadingLabel="Loading roaster…" />;
  }

  return (
    <EntityPage
      type="Roaster"
      title={roaster.name}
      subtitle={roaster.location ?? undefined}
      actions={<FavoriteButton entityType="roaster" entityId={params.id} />}
    >
      <Section title="Details">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Location" value={roaster.location} />
          {roaster.website && (
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Website</dt>
              <dd className="mt-0.5 text-sm">
                <a
                  href={roaster.website}
                  target="_blank"
                  rel="noreferrer"
                  className="text-amber-700 underline"
                >
                  {roaster.website.replace(/^https?:\/\//, "")}
                </a>
              </dd>
            </div>
          )}
        </dl>
      </Section>

      <Section
        title="Coffees"
        count={products.length}
        empty="No products scraped for this roaster yet."
      >
        <CardGrid>
          {products.map((p) => (
            <EntityCard
              key={p.id}
              href={`/explore/products/${p.id}`}
              title={p.name}
              subtitle={
                [p.is_blend ? "Blend" : "Single origin", formatPrice(p.price, p.currency)]
                  .filter(Boolean)
                  .join(" · ") || undefined
              }
            />
          ))}
        </CardGrid>
      </Section>
    </EntityPage>
  );
}
