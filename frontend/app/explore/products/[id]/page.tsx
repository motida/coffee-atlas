"use client";

import { useEffect, useState } from "react";
import {
  getProduct,
  getProductFlavors,
  getProductOrigin,
  getProductVarieties,
} from "@/lib/api";
import { EntityCard, EntityPage, Field, Section } from "@/components/explore/EntityPage";
import type { FlavorAttribute, Product, ProductOrigin, Variety } from "@/lib/types";

const titleCase = (s: string) => s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

export default function ProductPage({ params }: { params: { id: string } }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [flavors, setFlavors] = useState<FlavorAttribute[]>([]);
  const [origin, setOrigin] = useState<ProductOrigin>({ countries: [], regions: [] });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProduct(params.id)
      .then(setProduct)
      .catch((e) => setError(String(e)));
    getProductVarieties(params.id).then(setVarieties).catch(() => setVarieties([]));
    getProductFlavors(params.id).then(setFlavors).catch(() => setFlavors([]));
    getProductOrigin(params.id)
      .then(setOrigin)
      .catch(() => setOrigin({ countries: [], regions: [] }));
  }, [params.id]);

  if (error) {
    return (
      <EntityPage type="Product" title="Not found">
        <p className="text-sm text-red-600">{error}</p>
      </EntityPage>
    );
  }

  if (!product) {
    return (
      <EntityPage type="Product" title="Loading…">
        <p className="text-sm text-gray-500">Loading product…</p>
      </EntityPage>
    );
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
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {varieties.map((v) => (
            <EntityCard
              key={v.id}
              href={`/explore/varieties/${v.id}`}
              title={v.name}
              subtitle={v.species ?? undefined}
            />
          ))}
        </div>
      </Section>

      <Section title="Origin" count={originCount} empty="No origin matched from the listing.">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
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
        </div>
      </Section>

      <Section title="Flavor notes" count={flavors.length} empty="No flavor notes linked yet.">
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
