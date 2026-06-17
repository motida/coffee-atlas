import type {
  CountryGeoProperties,
  GeoJSONFeatureCollection,
  RegionGeoProperties,
  ShopGeoProperties,
  TradeRouteGeoProperties,
} from "@/lib/types";

interface MapLegendProps {
  countries: GeoJSONFeatureCollection<CountryGeoProperties> | null;
  regions: GeoJSONFeatureCollection<RegionGeoProperties> | null;
  shops: GeoJSONFeatureCollection<ShopGeoProperties> | null;
  shopsLoading: boolean;
  shopsCapped: boolean;
  zoom: number;
  shopsMinZoom: number;
}

/** Top-left legend with live counts of producing countries, regions, and shops in view. */
export function MapLegend({
  countries,
  regions,
  shops,
  shopsLoading,
  shopsCapped,
  zoom,
  shopsMinZoom,
}: MapLegendProps) {
  return (
    <div className="pointer-events-none absolute left-3 top-3 rounded bg-white/90 px-3 py-2 text-xs shadow">
      {countries && regions ? (
        <>
          <div>
            <span className="inline-block h-2 w-2 rounded-full bg-coffee-800 align-middle" />{" "}
            {countries.features.length} producing countries
          </div>
          <div>
            <span className="inline-block h-2 w-2 rounded-full bg-amber-600 align-middle" />{" "}
            {regions.features.length} regions (zoom in)
          </div>
          <div className="mt-1 border-t pt-1">
            <span className="inline-block h-2 w-2 rounded-full bg-[#6f3d18] align-middle" />{" "}
            {zoom < shopsMinZoom
              ? `coffee shops (zoom ≥${shopsMinZoom})`
              : shopsLoading
                ? "loading shops…"
                : shops
                  ? `${shops.features.length}${shopsCapped ? "+" : ""} shops in view`
                  : "no shops loaded"}
          </div>
        </>
      ) : (
        <span className="text-gray-500">Loading origins…</span>
      )}
    </div>
  );
}

interface MapTradeRoutesToggleProps {
  showRoutes: boolean;
  onToggle: () => void;
  routesLoading: boolean;
  routes: GeoJSONFeatureCollection<TradeRouteGeoProperties> | null;
}

/** Top-right control toggling the animated green-coffee trade-route overlay. */
export function MapTradeRoutesToggle({
  showRoutes,
  onToggle,
  routesLoading,
  routes,
}: MapTradeRoutesToggleProps) {
  return (
    <div className="absolute right-3 top-3 rounded bg-white/90 px-3 py-2 text-xs shadow">
      <label className="flex cursor-pointer items-center gap-2">
        <input
          type="checkbox"
          checked={showRoutes}
          onChange={onToggle}
          className="accent-amber-600"
        />
        <span className="inline-block h-0.5 w-4 rounded bg-amber-500 align-middle" />
        Trade routes
      </label>
      {showRoutes && (
        <div className="mt-1 text-gray-500">
          {routesLoading ? "loading…" : routes ? `${routes.features.length} green-coffee flows` : ""}
        </div>
      )}
    </div>
  );
}
