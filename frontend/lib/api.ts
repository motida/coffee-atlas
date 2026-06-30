import type {
  Country,
  CuppingNote,
  Favorite,
  FlavorAttribute,
  FlavorWheelData,
  GeoJSONFeatureCollection,
  CountryGeoProperties,
  LoginRequest,
  NearbyShop,
  ProcessingFlavorLink,
  ProcessingMethod,
  Product,
  ProductOrigin,
  Recommendation,
  RegisterRequest,
  Region,
  RegionGeoProperties,
  RoastProfile,
  Roaster,
  RoasterListItem,
  SearchResult,
  Shop,
  ShopGeoProperties,
  TradeRoute,
  TradeRouteGeoProperties,
  TraversalResult,
  User,
  Variety,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}/api/v1${endpoint}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    // Send/receive the httpOnly session cookie on every request. The JWT is
    // never JS-readable (no Authorization header), which is the point.
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  // 204 No Content (e.g. logout, delete) has no body to parse.
  if (res.status === 204) {
    return undefined as T;
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

// --- Roasting ---
export const getRoastProfiles = (limit = 50, offset = 0) =>
  fetchAPI<RoastProfile[]>(`/roasting/profiles?limit=${limit}&offset=${offset}`);

// --- Roasters ---
export const getRoasters = (
  limit = 100,
  offset = 0,
  opts?: { search?: string; sort?: "count" | "name" },
) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (opts?.search) params.set("search", opts.search);
  if (opts?.sort) params.set("sort", opts.sort);
  return fetchAPI<RoasterListItem[]>(`/roasting/roasters?${params.toString()}`);
};

export const getRoaster = (id: string) => fetchAPI<Roaster>(`/roasting/roasters/${id}`);

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

// --- Recommendations ---
export const getRecommendations = (entityType: string, id: string, limit = 6) =>
  fetchAPI<Recommendation[]>(
    `/recommend/${entityType}/${id}?limit=${limit}`,
  );

export const getRecommendationsForYou = (entityType = "product", limit = 10) =>
  fetchAPI<Recommendation[]>(
    `/recommend/for-you?entity_type=${entityType}&limit=${limit}`,
  );

// --- Auth ---
const jsonBody = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
});

export const register = (body: RegisterRequest) =>
  fetchAPI<User>("/auth/register", jsonBody(body));

export const login = (body: LoginRequest) => fetchAPI<User>("/auth/login", jsonBody(body));

export const logout = () => fetchAPI<void>("/auth/logout", { method: "POST" });

export const getMe = () => fetchAPI<User>("/auth/me");

// --- Account: favorites ---
export const getFavorites = (entityType?: string) => {
  const qs = entityType ? `?entity_type=${encodeURIComponent(entityType)}` : "";
  return fetchAPI<Favorite[]>(`/account/favorites${qs}`);
};

export const addFavorite = (entityType: string, entityId: string) =>
  fetchAPI<Favorite>("/account/favorites", jsonBody({ entity_type: entityType, entity_id: entityId }));

export const removeFavorite = (id: string) =>
  fetchAPI<void>(`/account/favorites/${id}`, { method: "DELETE" });

// --- Account: cupping notes ---
export const getNotes = (entityType?: string, entityId?: string) => {
  const params = new URLSearchParams();
  if (entityType) params.set("entity_type", entityType);
  if (entityId) params.set("entity_id", entityId);
  const qs = params.toString();
  return fetchAPI<CuppingNote[]>(`/account/notes${qs ? `?${qs}` : ""}`);
};

export interface NoteInput {
  entity_type: string;
  entity_id: string;
  notes: string;
  score?: number | null;
  brew_method?: string | null;
}

export const addNote = (body: NoteInput) => fetchAPI<CuppingNote>("/account/notes", jsonBody(body));

export const updateNote = (id: string, body: Partial<Omit<NoteInput, "entity_type" | "entity_id">>) =>
  fetchAPI<CuppingNote>(`/account/notes/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteNote = (id: string) =>
  fetchAPI<void>(`/account/notes/${id}`, { method: "DELETE" });

// --- Meta ---
export const getApiVersion = () => fetchAPI<{ version: string }>("/version");
