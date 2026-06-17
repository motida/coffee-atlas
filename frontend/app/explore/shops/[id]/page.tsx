"use client";

import { useEffect, useState } from "react";
import { getNearbyShops, getShop, getShopProducts } from "@/lib/api";
import {
  CardGrid,
  EntityCard,
  EntityDetailLoader,
  EntityPage,
  Field,
  ProductCard,
  Section,
} from "@/components/explore/EntityPage";
import { useEntityDetail } from "@/lib/hooks";
import type { NearbyShop, Product, Shop } from "@/lib/types";

export default function ShopPage({ params }: { params: { id: string } }) {
  const [nearby, setNearby] = useState<NearbyShop[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const { entity: shop, error } = useEntityDetail<Shop>(
    params.id,
    getShop,
    (id) => {
      getShopProducts(id)
        .then(setProducts)
        .catch(() => setProducts([]));
    },
  );

  // Nearby shops depend on the loaded shop's coordinates.
  useEffect(() => {
    if (shop && shop.latitude !== null && shop.longitude !== null) {
      getNearbyShops(shop.latitude, shop.longitude, 5)
        .then((all) => setNearby(all.filter((x) => x.id !== shop.id).slice(0, 12)))
        .catch(() => setNearby([]));
    }
  }, [shop]);

  if (error || !shop) {
    return <EntityDetailLoader type="Shop" error={error} loadingLabel="Loading shop…" />;
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
        <CardGrid>
          {products.map((p) => (
            <ProductCard
              key={p.id}
              href={`/explore/products/${p.id}`}
              title={p.name}
              roasterName={p.roaster_name}
              roasterId={p.roaster_id}
              price={p.price}
            />
          ))}
        </CardGrid>
      </Section>

      <Section
        title="Nearby shops (within 5 km)"
        count={nearby.length}
        empty="No nearby shops within 5 km."
      >
        <CardGrid>
          {nearby.map((n) => (
            <EntityCard
              key={n.id}
              href={`/explore/shops/${n.id}`}
              title={n.name}
              subtitle={`${n.distance_km.toFixed(2)} km${n.city ? ` · ${n.city}` : ""}`}
            />
          ))}
        </CardGrid>
      </Section>
    </EntityPage>
  );
}
