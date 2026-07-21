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
  VarietyFlavorLink,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

type QueryValue = string | number | boolean | string[] | undefined | null;

// Build a "?a=1&b=2" query string from defined params. undefined/null values
// are dropped, arrays append one entry per value, and an empty result yields ""
// so it can be concatenated onto any endpoint unconditionally.
function qs(params: Record<string, QueryValue>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const v of value) sp.append(key, v);
    } else {
      sp.set(key, String(value));
    }
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/** Thrown for non-2xx responses; carries the HTTP status so callers can
 *  distinguish e.g. an expired session (401) from other failures. */
export class APIError extends Error {
  constructor(
    public readonly status: number,
    statusText: string,
  ) {
    super(`API error: ${status} ${statusText}`);
    this.name = "APIError";
  }
}

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
    throw new APIError(res.status, res.statusText);
  }
  // 204 No Content (e.g. logout, delete) has no body to parse.
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

// --- Varieties ---
export const getVarieties = (limit = 20, offset = 0, species?: string) =>
  fetchAPI<Variety[]>(`/varieties${qs({ limit, offset, species })}`);

export const getVariety = (id: string) => fetchAPI<Variety>(`/varieties/${id}`);

export const getVarietyFlavor = (id: string) =>
  fetchAPI<VarietyFlavorLink[]>(`/varieties/${id}/flavor`);

// --- Origins ---
export const getOrigins = (limit = 20, offset = 0) =>
  fetchAPI(`/origins${qs({ limit, offset })}`);

export const getOrigin = (id: string) => fetchAPI<Country>(`/origins/${id}`);

export const getRegion = (id: string) => fetchAPI<Region>(`/origins/regions/${id}`);

export const getOriginsGeo = () =>
  fetchAPI<GeoJSONFeatureCollection<CountryGeoProperties>>(`/origins/geo`);

export const getRegionsGeo = () =>
  fetchAPI<GeoJSONFeatureCollection<RegionGeoProperties>>(`/origins/regions/geo`);

// --- Processing ---
export const getProcessingMethods = (limit = 20, offset = 0, category?: string) =>
  fetchAPI<ProcessingMethod[]>(`/processing/methods${qs({ limit, offset, category })}`);

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
  fetchAPI<TradeRoute[]>(`/distribution/trade-routes${qs({ limit, offset })}`);

export const getTradeRoutesGeo = () =>
  fetchAPI<GeoJSONFeatureCollection<TradeRouteGeoProperties>>(
    `/distribution/trade-routes/geo`,
  );

// --- Shops ---
export const getShops = (limit = 20, offset = 0) =>
  fetchAPI(`/shops${qs({ limit, offset })}`);

export const getShop = (id: string) => fetchAPI<Shop>(`/shops/${id}`);

export const getShopsGeo = (
  bbox?: [number, number, number, number],
  limit = 5000,
) =>
  fetchAPI<GeoJSONFeatureCollection<ShopGeoProperties>>(
    `/shops/geo${qs({ limit, bbox: bbox?.join(",") })}`,
  );

export const getNearbyShops = (lat: number, lng: number, radiusKm = 5) =>
  fetchAPI<NearbyShop[]>(`/shops/nearby${qs({ lat, lng, radius_km: radiusKm })}`);

export const getShopProducts = (id: string) =>
  fetchAPI<Product[]>(`/shops/${id}/products`);

// --- Products ---
export const getProducts = (limit = 20, offset = 0, roasterId?: string) =>
  fetchAPI<Product[]>(`/products${qs({ limit, offset, roaster_id: roasterId })}`);

export const getProduct = (id: string) => fetchAPI<Product>(`/products/${id}`);

export const getProductVarieties = (id: string) =>
  fetchAPI<Variety[]>(`/products/${id}/varieties`);

export const getProductFlavors = (id: string) =>
  fetchAPI<FlavorAttribute[]>(`/products/${id}/flavors`);

export const getProductOrigin = (id: string) =>
  fetchAPI<ProductOrigin>(`/products/${id}/origin`);

// --- Roasting ---
export const getRoastProfiles = (limit = 50, offset = 0) =>
  fetchAPI<RoastProfile[]>(`/roasting/profiles${qs({ limit, offset })}`);

// --- Roasters ---
export const getRoasters = (
  limit = 100,
  offset = 0,
  opts?: { search?: string; sort?: "count" | "name" },
) =>
  fetchAPI<RoasterListItem[]>(
    `/roasting/roasters${qs({ limit, offset, search: opts?.search, sort: opts?.sort })}`,
  );

export const getRoaster = (id: string) => fetchAPI<Roaster>(`/roasting/roasters/${id}`);

// --- Graph ---
export const graphTraverse = (
  startId: string,
  maxDepth = 2,
  signal?: AbortSignal,
) =>
  fetchAPI<TraversalResult>(
    `/graph/traverse${qs({ start_id: startId, max_depth: maxDepth })}`,
    { signal },
  );

export const graphPath = (startId: string, endId: string, edgeTypes?: string[]) =>
  fetchAPI(
    `/graph/path${qs({ start_id: startId, end_id: endId, edge_types: edgeTypes })}`,
  );

// --- Search ---
const searchUrl = (
  base: string,
  query: string,
  limit: number,
  entityTypes?: string[],
  species?: string,
) => `${base}${qs({ query, limit, entity_types: entityTypes, species })}`;

export const searchSemantic = (
  query: string,
  limit = 20,
  entityTypes?: string[],
  species?: string,
) =>
  fetchAPI<SearchResult[]>(
    searchUrl("/search/semantic", query, limit, entityTypes, species),
  );

export const searchText = (
  query: string,
  limit = 20,
  entityTypes?: string[],
  species?: string,
) =>
  fetchAPI<SearchResult[]>(
    searchUrl("/search/text", query, limit, entityTypes, species),
  );

// --- Recommendations ---
export const getRecommendations = (entityType: string, id: string, limit = 6) =>
  fetchAPI<Recommendation[]>(`/recommend/${entityType}/${id}${qs({ limit })}`);

export const getRecommendationsForYou = (entityType = "product", limit = 10) =>
  fetchAPI<Recommendation[]>(
    `/recommend/for-you${qs({ entity_type: entityType, limit })}`,
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
export const getFavorites = (entityType?: string) =>
  fetchAPI<Favorite[]>(`/account/favorites${qs({ entity_type: entityType })}`);

export const addFavorite = (entityType: string, entityId: string) =>
  fetchAPI<Favorite>("/account/favorites", jsonBody({ entity_type: entityType, entity_id: entityId }));

export const removeFavorite = (id: string) =>
  fetchAPI<void>(`/account/favorites/${id}`, { method: "DELETE" });

// --- Account: cupping notes ---
export const getNotes = (entityType?: string, entityId?: string) =>
  fetchAPI<CuppingNote[]>(
    `/account/notes${qs({ entity_type: entityType, entity_id: entityId })}`,
  );

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
