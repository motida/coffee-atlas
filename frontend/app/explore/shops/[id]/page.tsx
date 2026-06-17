"use client";

import { useEffect, useState } from "react";
import { getNearbyShops, getShop, getShopProducts } from "@/lib/api";
import { EntityCard, EntityPage, Field, Section } from "@/components/explore/EntityPage";
import type { NearbyShop, Product, Shop } from "@/lib/types";

export default function ShopPage({ params }: { params: { id: string } }) {
  const [shop, setShop] = useState<Shop | null>(null);
  const [nearby, setNearby] = useState<NearbyShop[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getShop(params.id)
      .then((s) => {
        setShop(s);
        if (s.latitude !== null && s.longitude !== null) {
          getNearbyShops(s.latitude, s.longitude, 5)
            .then((all) =>
              setNearby(all.filter((x) => x.id !== s.id).slice(0, 12)),
            )
            .catch(() => setNearby([]));
        }
      })
      .catch((e) => setError(String(e)));
    getShopProducts(params.id).then(setProducts).catch(() => setProducts([]));
  }, [params.id]);

  if (error) {
    return (
      <EntityPage type="Shop" title="Not found">
        <p className="text-sm text-red-600">{error}</p>
      </EntityPage>
    );
  }

  if (!shop) {
    return (
      <EntityPage type="Shop" title="Loading…">
        <p className="text-sm text-gray-500">Loading shop…</p>
      </EntityPage>
    );
  }

  return (
    <EntityPage
      type="Shop"
      title={shop.name}
      subtitle={[shop.city, shop.country].filter(Boolean).join(", ") || undefined}
    >
      <Section title="Details">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Address" value={shop.address} />
          <Field label="City" value={shop.city} />
          <Field label="Country" value={shop.country} />
          <Field label="Rating" value={shop.rating} />
          <Field label="Roasts in-house" value={shop.roasts_in_house ? "Yes" : null} />
          {shop.website && (
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Website</dt>
              <dd className="mt-0.5 text-sm">
                <a
                  href={shop.website}
                  target="_blank"
                  rel="noreferrer"
                  className="text-amber-700 underline"
                >
                  {shop.website.replace(/^https?:\/\//, "")}
                </a>
              </dd>
            </div>
          )}
        </dl>
      </Section>

      {shop.description && (
        <Section title="About">
          <p className="text-sm leading-relaxed text-gray-800">{shop.description}</p>
        </Section>
      )}

      <Section
        title="Coffee served"
        count={products.length}
        empty="No products linked (this shop isn't matched to a roaster we've scraped)."
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {products.map((p) => (
            <EntityCard
              key={p.id}
              href={`/explore/products/${p.id}`}
              title={p.name}
              subtitle={
                [p.roaster_name, p.price !== null ? `$${p.price}` : null]
                  .filter(Boolean)
                  .join(" · ") || undefined
              }
            />
          ))}
        </div>
      </Section>

      <Section
        title="Nearby shops (within 5 km)"
        count={nearby.length}
        empty="No nearby shops within 5 km."
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {nearby.map((n) => (
            <EntityCard
              key={n.id}
              href={`/explore/shops/${n.id}`}
              title={n.name}
              subtitle={`${n.distance_km.toFixed(2)} km${n.city ? ` · ${n.city}` : ""}`}
            />
          ))}
        </div>
      </Section>
    </EntityPage>
  );
}
