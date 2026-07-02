// --- Common ---
export interface Timestamped {
  id: string;
  created_at: string;
  updated_at: string;
}

// --- Varieties ---
export interface Variety extends Timestamped {
  name: string;
  species: string | null;
  genetic_group: string | null;
  description: string | null;
  yield_potential: string | null;
  optimal_altitude_min: number | null;
  optimal_altitude_max: number | null;
  bean_size: string | null;
  cherry_color: string | null;
  stature: string | null;
  disease_resistance: string | null;
}

// --- Origins ---
export interface Country extends Timestamped {
  name: string;
  iso_code: string | null;
  latitude: number | null;
  longitude: number | null;
  production_volume: number | null;
}

export interface Region extends Timestamped {
  name: string;
  country_id: string | null;
  latitude: number | null;
  longitude: number | null;
  altitude_min: number | null;
  altitude_max: number | null;
}

export interface Farm extends Timestamped {
  name: string;
  region_id: string | null;
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
  soil_type: string | null;
  owner: string | null;
}

// --- Processing ---
export interface ProcessingMethod extends Timestamped {
  name: string;
  category: string | null;
  description: string | null;
  fermentation_duration: number | null;
  drying_duration: number | null;
}

/** A flavor attribute linked to a processing method, with the method's effect on it.
 *  Shape returned by /processing/methods/{id}/flavor (flavor leaf + edge effect). */
export interface ProcessingFlavorLink {
  id: string;
  name: string;
  category: string | null;
  subcategory: string | null;
  description: string | null;
  intensity_reference: string | null;
  sensory_reference: string | null;
  parent_id: string | null;
  effect: string | null;
}

// --- Roasting ---
export interface RoastProfile extends Timestamped {
  name: string;
  roast_level: string | null;
  first_crack_temp: number | null;
  development_time_ratio: number | null;
  charge_temp: number | null;
  total_roast_time: number | null;
  description: string | null;
}

export interface Roaster extends Timestamped {
  name: string;
  location: string | null;
  website: string | null;
}

export interface RoasterListItem extends Roaster {
  product_count: number;
}

// --- Flavor ---
export interface FlavorAttribute extends Timestamped {
  name: string;
  category: string | null;
  subcategory: string | null;
  description: string | null;
  intensity_reference: string | null;
  sensory_reference: string | null;
  parent_id: string | null;
}

/** Leaf shape returned by /api/v1/flavor/wheel (omits created_at / updated_at / name_embedding). */
export interface FlavorWheelLeaf {
  id: string;
  name: string;
  category: string | null;
  subcategory: string | null;
  description: string | null;
  intensity_reference: string | null;
  sensory_reference: string | null;
  parent_id: string | null;
}

/** /api/v1/flavor/wheel response — Category → Subcategory → list of leaf attributes. */
export type FlavorWheelData = Record<string, Record<string, FlavorWheelLeaf[]>>;

// --- Distribution ---
export interface Importer extends Timestamped {
  name: string;
  country_id: string | null;
  country_name: string | null;
  website: string | null;
}

export interface TradeRoute extends Timestamped {
  exporter_country_id: string | null;
  importer_country_id: string | null;
  exporter_name: string | null;
  importer_name: string | null;
  annual_volume: number | null;
  year: number | null;
}

export interface Certification extends Timestamped {
  name: string;
  description: string | null;
}

// --- Shops ---
export interface Shop extends Timestamped {
  name: string;
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  city: string | null;
  country: string | null;
  website: string | null;
  rating: number | null;
  roasts_in_house: boolean | null;
  description: string | null;
}

/** A shop plus its Haversine distance — shape returned by /shops/nearby. */
export interface NearbyShop extends Shop {
  distance_km: number;
}

// --- Products ---
export interface Product extends Timestamped {
  name: string;
  roaster_id: string | null;
  roaster_name: string | null;
  roast_level: string | null;
  process: string | null;
  is_blend: boolean | null;
  price: number | null;
  net_weight_grams: number | null;
  url: string | null;
  description: string | null;
}

export interface ProductOrigin {
  countries: { id: string; name: string }[];
  regions: { id: string; name: string }[];
}

// --- Geo properties ---
export interface CountryGeoProperties {
  id: string;
  name: string;
  iso_code: string | null;
  latitude: number;
  longitude: number;
  production_volume: number | null;
}

export interface RegionGeoProperties {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  country_name: string;
  iso_code: string | null;
}

export interface ShopGeoProperties {
  id: string;
  name: string;
  address: string | null;
  city: string | null;
  country: string | null;
  website: string | null;
  rating: number | null;
  roasts_in_house: boolean | null;
  description: string | null;
}

export interface TradeRouteGeoProperties {
  id: string;
  exporter_id: string;
  exporter_name: string;
  importer_id: string;
  importer_name: string;
  annual_volume: number | null;
  year: number | null;
}

// --- GeoJSON ---
export interface GeoJSONFeature<P = Record<string, unknown>> {
  type: "Feature";
  geometry: {
    type: string;
    // Point: [lon, lat]; LineString: [[lon, lat], ...]
    coordinates: number[] | number[][];
  };
  properties: P;
}

export interface GeoJSONFeatureCollection<P = Record<string, unknown>> {
  type: "FeatureCollection";
  features: GeoJSONFeature<P>[];
}

// --- Graph ---
export interface GraphNode {
  id: string;
  entity_type: string;
  label: string;
  properties?: Record<string, unknown>;
}

export interface GraphEdge {
  source_id: string;
  target_id: string;
  edge_type: string;
  properties?: Record<string, unknown>;
}

export interface TraversalResult {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** True when the server-side node/edge budget stopped the traversal early. */
  truncated?: boolean;
}

export interface PathResult {
  path: GraphNode[];
  edges: GraphEdge[];
  total_weight: number | null;
}

// --- Search ---
export interface SearchResult {
  id: string;
  entity_type: string;
  label: string;
  description: string | null;
  similarity: number | null;
}

export interface Recommendation {
  id: string;
  entity_type: string;
  label: string;
  description: string | null;
  score: number;
  reason: string | null;
}

// --- Users & activity ---
export interface User extends Timestamped {
  email: string;
  display_name: string | null;
  is_active: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest extends LoginRequest {
  display_name?: string | null;
}

export interface Favorite {
  id: string;
  user_id: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
}

export interface CuppingNote extends Timestamped {
  user_id: string;
  entity_type: string;
  entity_id: string;
  notes: string;
  score: number | null;
  brew_method: string | null;
}
