import type {
  Country,
  FlavorAttribute,
  FlavorWheelData,
  GeoJSONFeatureCollection,
  CountryGeoProperties,
  Region,
  RegionGeoProperties,
  Shop,
  ShopGeoProperties,
  TraversalResult,
  Variety,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
export const getVarieties = (limit = 20, offset = 0) =>
  fetchAPI(`/varieties?limit=${limit}&offset=${offset}`);

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

// --- Roasting ---
export const getRoastProfiles = (limit = 20, offset = 0) =>
  fetchAPI(`/roasting/profiles?limit=${limit}&offset=${offset}`);

export const getRoastProfile = (id: string) =>
  fetchAPI(`/roasting/profiles/${id}`);

// --- Flavor ---
export const getFlavorWheel = () => fetchAPI<FlavorWheelData>(`/flavor/wheel`);

export const getFlavorAttribute = (id: string) =>
  fetchAPI<FlavorAttribute>(`/flavor/attributes/${id}`);

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
  fetchAPI<(Shop & { distance_km: number })[]>(
    `/shops/nearby?lat=${lat}&lng=${lng}&radius_km=${radiusKm}`,
  );

// --- Graph ---
export const graphTraverse = (startId: string, maxDepth = 2) =>
  fetchAPI<TraversalResult>(
    `/graph/traverse?start_id=${startId}&max_depth=${maxDepth}`,
  );

export const graphPath = (startId: string, endId: string) =>
  fetchAPI(`/graph/path?start_id=${startId}&end_id=${endId}`);

// --- Search ---
export const searchSemantic = (query: string, limit = 20) =>
  fetchAPI(`/search/semantic?query=${encodeURIComponent(query)}&limit=${limit}`);

export const searchText = (query: string, limit = 20) =>
  fetchAPI(`/search/text?query=${encodeURIComponent(query)}&limit=${limit}`);
