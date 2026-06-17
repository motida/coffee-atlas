import type {
  Country,
  FlavorAttribute,
  FlavorWheelData,
  GeoJSONFeatureCollection,
  CountryGeoProperties,
  NearbyShop,
  ProcessingFlavorLink,
  ProcessingMethod,
  Product,
  ProductOrigin,
  Region,
  RegionGeoProperties,
  SearchResult,
  Shop,
  ShopGeoProperties,
  TradeRoute,
  TradeRouteGeoProperties,
  TraversalResult,
  Variety,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}/api/v1${endpoint}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// --- Varieties ---
export const getVarieties = (limit = 20, offset = 0, species?: string) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (species) params.set("species", species);
  return fetchAPI<Variety[]>(`/varieties?${params.toString()}`);
};

export const getVariety = (id: string) => fetchAPI<Variety>(`/varieties/${id}`);

export const getVarietyFlavor = (id: string) =>
  fetchAPI<FlavorAttribute[]>(`/varieties/${id}/flavor`);

// --- Origins ---
export const getOrigins = (limit = 20, offset = 0) =>
  fetchAPI(`/origins?limit=${limit}&offset=${offset}`);

export const getOrigin = (id: string) => fetchAPI<Country>(`/origins/${id}`);

export const getRegion = (id: string) => fetchAPI<Region>(`/origins/regions/${id}`);

export const getOriginsGeo = () =>
  fetchAPI<GeoJSONFeatureCollection<CountryGeoProperties>>(`/origins/geo`);

export const getRegionsGeo = () =>
  fetchAPI<GeoJSONFeatureCollection<RegionGeoProperties>>(`/origins/regions/geo`);

// --- Processing ---
export const getProcessingMethods = (limit = 20, offset = 0, category?: string) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (category) params.set("category", category);
  return fetchAPI<ProcessingMethod[]>(`/processing/methods?${params.toString()}`);
};

export const getProcessingMethod = (id: string) =>
  fetchAPI<ProcessingMethod>(`/processing/methods/${id}`);

export const getProcessingMethodVarieties = (id: string) =>
  fetchAPI<Variety[]>(`/processing/methods/${id}/varieties`);

export const getProcessingMethodFlavor = (id: string) =>
  fetchAPI<ProcessingFlavorLink[]>(`/processing/methods/${id}/flavor`);

// --- Flavor ---
export const getFlavorWheel = () => fetchAPI<FlavorWheelData>(`/flavor/wheel`);

export const getFlavorAttribute = (id: string) =>
  fetchAPI<FlavorAttribute>(`/flavor/attributes/${id}`);

// --- Distribution ---
export const getTradeRoutes = (limit = 100, offset = 0) =>
  fetchAPI<TradeRoute[]>(
    `/distribution/trade-routes?limit=${limit}&offset=${offset}`,
  );

export const getTradeRoutesGeo = () =>
  fetchAPI<GeoJSONFeatureCollection<TradeRouteGeoProperties>>(
    `/distribution/trade-routes/geo`,
  );

// --- Shops ---
export const getShops = (limit = 20, offset = 0) =>
  fetchAPI(`/shops?limit=${limit}&offset=${offset}`);

export const getShop = (id: string) => fetchAPI<Shop>(`/shops/${id}`);

export const getShopsGeo = (
  bbox?: [number, number, number, number],
  limit = 5000,
) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (bbox) params.set("bbox", bbox.join(","));
  return fetchAPI<GeoJSONFeatureCollection<ShopGeoProperties>>(
    `/shops/geo?${params.toString()}`,
  );
};

export const getNearbyShops = (lat: number, lng: number, radiusKm = 5) =>
  fetchAPI<NearbyShop[]>(
    `/shops/nearby?lat=${lat}&lng=${lng}&radius_km=${radiusKm}`,
  );

export const getShopProducts = (id: string) =>
  fetchAPI<Product[]>(`/shops/${id}/products`);

// --- Products ---
export const getProducts = (limit = 20, offset = 0, roasterId?: string) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (roasterId) params.set("roaster_id", roasterId);
  return fetchAPI<Product[]>(`/products?${params.toString()}`);
};

export const getProduct = (id: string) => fetchAPI<Product>(`/products/${id}`);

export const getProductVarieties = (id: string) =>
  fetchAPI<Variety[]>(`/products/${id}/varieties`);

export const getProductFlavors = (id: string) =>
  fetchAPI<FlavorAttribute[]>(`/products/${id}/flavors`);

export const getProductOrigin = (id: string) =>
  fetchAPI<ProductOrigin>(`/products/${id}/origin`);

// --- Graph ---
export const graphTraverse = (
  startId: string,
  maxDepth = 2,
  signal?: AbortSignal,
) =>
  fetchAPI<TraversalResult>(
    `/graph/traverse?start_id=${startId}&max_depth=${maxDepth}`,
    { signal },
  );

export const graphPath = (startId: string, endId: string) =>
  fetchAPI(`/graph/path?start_id=${startId}&end_id=${endId}`);

// --- Search ---
const buildSearchUrl = (
  base: string,
  query: string,
  limit: number,
  entityTypes?: string[],
  species?: string,
) => {
  const params = new URLSearchParams({
    query,
    limit: String(limit),
  });
  for (const t of entityTypes ?? []) params.append("entity_types", t);
  if (species) params.set("species", species);
  return `${base}?${params.toString()}`;
};

export const searchSemantic = (
  query: string,
  limit = 20,
  entityTypes?: string[],
  species?: string,
) =>
  fetchAPI<SearchResult[]>(
    buildSearchUrl("/search/semantic", query, limit, entityTypes, species),
  );

export const searchText = (
  query: string,
  limit = 20,
  entityTypes?: string[],
  species?: string,
) =>
  fetchAPI<SearchResult[]>(
    buildSearchUrl("/search/text", query, limit, entityTypes, species),
  );
