"use client";

import { useState } from "react";
import {
  getProduct,
  getProductFlavors,
  getProductOrigin,
  getProductVarieties,
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
import type { FlavorAttribute, Product, ProductOrigin, Variety } from "@/lib/types";

export default function ProductPage({ params }: { params: { id: string } }) {
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [flavors, setFlavors] = useState<FlavorAttribute[]>([]);
  const [origin, setOrigin] = useState<ProductOrigin>({ countries: [], regions: [] });
  const { entity: product, error } = useEntityDetail<Product>(
    params.id,
    getProduct,
    (id) => {
      getProductVarieties(id)
        .then(setVarieties)
        .catch(() => setVarieties([]));
      getProductFlavors(id)
        .then(setFlavors)
        .catch(() => setFlavors([]));
      getProductOrigin(id)
        .then(setOrigin)
        .catch(() => setOrigin({ countries: [], regions: [] }));
    },
  );

  if (error || !product) {
    return <EntityDetailLoader type="Product" error={error} loadingLabel="Loading product…" />;
  }

  const kind = product.is_blend ? "Blend" : "Single origin";
  const originCount = origin.countries.length + origin.regions.length;

  return (
    <EntityPage
      type="Product"
      title={product.name}
      subtitle={[product.roaster_name, kind].filter(Boolean).join(" · ") || undefined}
    >
      <Section title="Details">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Roaster" value={product.roaster_name} />
          <Field label="Roast level" value={product.roast_level} />
          <Field label="Process" value={product.process} />
          <Field label="Type" value={kind} />
          <Field label="Price" value={product.price !== null ? `$${product.price}` : null} />
          <Field
            label="Net weight"
            value={product.net_weight_grams !== null ? `${product.net_weight_grams} g` : null}
          />
          {product.url && (
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Product page</dt>
              <dd className="mt-0.5 text-sm">
                <a
                  href={product.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-amber-700 underline"
                >
                  Visit roaster ↗
                </a>
              </dd>
            </div>
          )}
        </dl>
      </Section>

      {product.description && (
        <Section title="Description">
          <p className="whitespace-pre-line text-sm leading-relaxed text-gray-800">
            {product.description}
          </p>
        </Section>
      )}

      <Section title="Varieties" count={varieties.length} empty="No varieties linked yet.">
        <CardGrid>
          {varieties.map((v) => (
            <EntityCard
              key={v.id}
              href={`/explore/varieties/${v.id}`}
              title={v.name}
              subtitle={v.species ?? undefined}
            />
          ))}
        </CardGrid>
      </Section>

      <Section title="Origin" count={originCount} empty="No origin matched from the listing.">
        <CardGrid>
          {origin.countries.map((c) => (
            <EntityCard
              key={c.id}
              href={`/explore/countries/${c.id}`}
              title={c.name}
              subtitle="Country"
            />
          ))}
          {origin.regions.map((r) => (
            <EntityCard
              key={r.id}
              href={`/explore/regions/${r.id}`}
              title={titleCase(r.name)}
              subtitle="Region"
            />
          ))}
        </CardGrid>
      </Section>

      <Section title="Flavor notes" count={flavors.length} empty="No flavor notes linked yet.">
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
    </EntityPage>
  );
}
