"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Map, {
  Layer,
  Popup,
  Source,
  type MapLayerMouseEvent,
  type MapRef,
  type ViewStateChangeEvent,
} from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  getOriginsGeo,
  getRegionsGeo,
  getShopsGeo,
  getTradeRoutesGeo,
} from "@/lib/api";
import { toArcs } from "@/lib/arc";
import type {
  CountryGeoProperties,
  GeoJSONFeatureCollection,
  RegionGeoProperties,
  ShopGeoProperties,
  TradeRouteGeoProperties,
} from "@/lib/types";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const COUNTRY_LAYER = "countries-layer";
const REGION_LAYER = "regions-layer";
const SHOP_CLUSTER_LAYER = "shops-clusters";
const SHOP_CLUSTER_COUNT_LAYER = "shops-cluster-count";
const SHOP_POINT_LAYER = "shops-points";
const TRADE_ROUTE_HIT_LAYER = "trade-routes-hit";
const TRADE_ROUTE_BG_LAYER = "trade-routes-bg";
const TRADE_ROUTE_DASH_LAYER = "trade-routes-dash";

// Flowing-dash sequence for the trade-route animation (the Mapbox GL "animate a
// line" technique): cycling these dash patterns makes the dashes appear to
// travel from exporter to importer. Applied imperatively, frame by frame.
const DASH_SEQUENCE: number[][] = [
  [0, 4, 3],
  [0.5, 4, 2.5],
  [1, 4, 2],
  [1.5, 4, 1.5],
  [2, 4, 1],
  [2.5, 4, 0.5],
  [3, 4, 0],
  [0, 0.5, 4, 2.5],
  [0, 1, 4, 2],
  [0, 1.5, 4, 1.5],
  [0, 2, 4, 1],
  [0, 2.5, 4, 0.5],
  [0, 3, 4, 0],
];

const SHOPS_MIN_ZOOM = 6;
const SHOPS_FETCH_LIMIT = 5000;

const VIEW_STORAGE_KEY = "coffee-atlas:map-view";

const DEFAULT_VIEW = {
  latitude: 39.5,
  longitude: -98.35,
  zoom: 4,
};

// Restore the last map position (persisted in sessionStorage) so drilling into
// an entity and navigating back doesn't reset the view. Falls back to the
// default US-centered view when nothing is stored or storage is unavailable.
function loadInitialView() {
  if (typeof window === "undefined") return DEFAULT_VIEW;
  try {
    const raw = window.sessionStorage.getItem(VIEW_STORAGE_KEY);
    if (raw) {
      const v = JSON.parse(raw);
      if (
        typeof v?.latitude === "number" &&
        typeof v?.longitude === "number" &&
        typeof v?.zoom === "number"
      ) {
        return { latitude: v.latitude, longitude: v.longitude, zoom: v.zoom };
      }
    }
  } catch {
    // ignore malformed JSON / unavailable storage (private mode, quota)
  }
  return DEFAULT_VIEW;
}

type AnyGeo = GeoJSONFeatureCollection<
  | CountryGeoProperties
  | RegionGeoProperties
  | ShopGeoProperties
  | TradeRouteGeoProperties
>;

interface PopupState {
  longitude: number;
  latitude: number;
  title: string;
  subtitle?: string;
  link?: string;
  detailHref?: string;
  links?: { label: string; href: string }[];
}

export default function CoffeeMap() {
  const mapRef = useRef<MapRef | null>(null);
  const [viewState, setViewState] = useState(loadInitialView);
  const [countries, setCountries] =
    useState<GeoJSONFeatureCollection<CountryGeoProperties> | null>(null);
  const [regions, setRegions] =
    useState<GeoJSONFeatureCollection<RegionGeoProperties> | null>(null);
  const [shops, setShops] =
    useState<GeoJSONFeatureCollection<ShopGeoProperties> | null>(null);
  const [shopsLoading, setShopsLoading] = useState(false);
  const [shopsCapped, setShopsCapped] = useState(false);
  const [popup, setPopup] = useState<PopupState | null>(null);
  const [hovering, setHovering] = useState(false);
  const [showRoutes, setShowRoutes] = useState(false);
  const [routes, setRoutes] =
    useState<GeoJSONFeatureCollection<TradeRouteGeoProperties> | null>(null);
  const [routesLoading, setRoutesLoading] = useState(false);

  useEffect(() => {
    getOriginsGeo()
      .then(setCountries)
      .catch((e) => console.error("Failed to load countries:", e));
    getRegionsGeo()
      .then(setRegions)
      .catch((e) => console.error("Failed to load regions:", e));
  }, []);

  const fetchShops = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const zoom = map.getZoom();
    if (zoom < SHOPS_MIN_ZOOM) {
      setShops(null);
      setShopsCapped(false);
      return;
    }
    const b = map.getBounds();
    const bbox: [number, number, number, number] = [
      b.getWest(),
      b.getSouth(),
      b.getEast(),
      b.getNorth(),
    ];
    setShopsLoading(true);
    getShopsGeo(bbox, SHOPS_FETCH_LIMIT)
      .then((fc) => {
        setShops(fc);
        setShopsCapped(fc.features.length >= SHOPS_FETCH_LIMIT);
      })
      .catch((e) => console.error("Failed to load shops:", e))
      .finally(() => setShopsLoading(false));
  }, []);

  const handleMoveEnd = useCallback(
    (evt: ViewStateChangeEvent) => {
      if (typeof window !== "undefined") {
        try {
          const { latitude, longitude, zoom } = evt.viewState;
          window.sessionStorage.setItem(
            VIEW_STORAGE_KEY,
            JSON.stringify({ latitude, longitude, zoom }),
          );
        } catch {
          // ignore storage write failures (quota / private mode)
        }
      }
      fetchShops();
    },
    [fetchShops],
  );

  // Lazy-load trade routes the first time the layer is enabled, converting the
  // straight exporter→importer segments from the API into bezier arcs.
  const toggleRoutes = useCallback(() => {
    setShowRoutes((prev) => {
      const next = !prev;
      if (next && !routes && !routesLoading) {
        setRoutesLoading(true);
        getTradeRoutesGeo()
          .then((fc) => setRoutes(toArcs(fc)))
          .catch((err) => console.error("Failed to load trade routes:", err))
          .finally(() => setRoutesLoading(false));
      }
      return next;
    });
  }, [routes, routesLoading]);

  // Drive the dashed overlay so flows appear to move exporter→importer. The
  // dasharray is set imperatively (kept out of the declarative paint) so
  // react-map-gl's prop reconciliation on pan/zoom doesn't fight the animation.
  useEffect(() => {
    if (!showRoutes || !routes) return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    let raf = 0;
    let step = -1;
    const animate = (ts: number) => {
      const next = Math.floor(ts / 60) % DASH_SEQUENCE.length;
      if (next !== step) {
        step = next;
        if (map.getLayer(TRADE_ROUTE_DASH_LAYER)) {
          map.setPaintProperty(
            TRADE_ROUTE_DASH_LAYER,
            "line-dasharray",
            DASH_SEQUENCE[step],
          );
        }
      }
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [showRoutes, routes]);

  const onClick = (e: MapLayerMouseEvent) => {
    const map = mapRef.current;
    const feature = e.features?.[0];
    if (!feature) {
      setPopup(null);
      return;
    }
    const layerId = feature.layer.id;

    if (layerId === SHOP_CLUSTER_LAYER && map) {
      const clusterId = feature.properties?.cluster_id as number | undefined;
      const src = map.getSource("shops") as
        | { getClusterExpansionZoom: (id: number) => Promise<number> }
        | undefined;
      if (clusterId !== undefined && src?.getClusterExpansionZoom) {
        src.getClusterExpansionZoom(clusterId).then((zoom) => {
          const [lng, lat] = (feature.geometry as GeoJSON.Point).coordinates;
          map.easeTo({ center: [lng, lat], zoom });
        });
      }
      return;
    }

    if (layerId === TRADE_ROUTE_HIT_LAYER) {
      const props = feature.properties as TradeRouteGeoProperties;
      setPopup({
        longitude: e.lngLat.lng,
        latitude: e.lngLat.lat,
        title: `${props.exporter_name} → ${props.importer_name}`,
        subtitle:
          props.annual_volume != null
            ? `${props.annual_volume.toLocaleString()} t${props.year ? ` (${props.year})` : ""}`
            : "green-coffee trade route",
        links: [
          {
            label: props.exporter_name,
            href: `/explore/countries/${props.exporter_id}`,
          },
          {
            label: props.importer_name,
            href: `/explore/countries/${props.importer_id}`,
          },
        ],
      });
      return;
    }

    const [lng, lat] = (feature.geometry as GeoJSON.Point).coordinates;

    if (layerId === SHOP_POINT_LAYER) {
      const props = feature.properties as ShopGeoProperties;
      setPopup({
        longitude: lng,
        latitude: lat,
        title: props.name,
        subtitle: [props.city, props.country].filter(Boolean).join(", ") || undefined,
        link: props.website ?? undefined,
        detailHref: `/explore/shops/${props.id}`,
      });
      return;
    }

    if (layerId === COUNTRY_LAYER) {
      const props = feature.properties as CountryGeoProperties;
      setPopup({
        longitude: lng,
        latitude: lat,
        title: props.name,
        subtitle: props.iso_code ?? undefined,
        detailHref: `/explore/countries/${props.id}`,
      });
      return;
    }

    if (layerId === REGION_LAYER) {
      const props = feature.properties as RegionGeoProperties;
      setPopup({
        longitude: lng,
        latitude: lat,
        title: props.name.replace(/\b\w/g, (c) => c.toUpperCase()),
        subtitle: props.country_name,
        detailHref: `/explore/regions/${props.id}`,
      });
    }
  };

  return (
    <Map
      ref={mapRef}
      {...viewState}
      onMove={(evt) => setViewState(evt.viewState)}
      onMoveEnd={handleMoveEnd}
      onLoad={fetchShops}
      mapStyle={MAP_STYLE}
      style={{ width: "100%", height: "100%" }}
      interactiveLayerIds={[
        TRADE_ROUTE_HIT_LAYER,
        COUNTRY_LAYER,
        REGION_LAYER,
        SHOP_CLUSTER_LAYER,
        SHOP_POINT_LAYER,
      ]}
      onClick={onClick}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      cursor={hovering ? "pointer" : "grab"}
    >
      {showRoutes && routes && (
        <Source id="trade-routes" type="geojson" data={routes as AnyGeo}>
          {/* Transparent wide line: a generous click/hover target for the
              otherwise thin arcs. Rendered first so it sits beneath markers. */}
          <Layer
            id={TRADE_ROUTE_HIT_LAYER}
            type="line"
            layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{ "line-color": "#000000", "line-opacity": 0, "line-width": 12 }}
          />
          <Layer
            id={TRADE_ROUTE_BG_LAYER}
            type="line"
            layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{
              "line-color": "#92400e",
              "line-opacity": 0.3,
              "line-width": 1.5,
            }}
          />
          {/* Animated dashes (dasharray driven imperatively by the effect). */}
          <Layer
            id={TRADE_ROUTE_DASH_LAYER}
            type="line"
            paint={{ "line-color": "#f59e0b", "line-width": 2.5 }}
          />
        </Source>
      )}

      {countries && (
        <Source id="countries" type="geojson" data={countries as AnyGeo}>
          <Layer
            id={COUNTRY_LAYER}
            type="circle"
            paint={{
              "circle-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                0,
                4,
                4,
                10,
                8,
                14,
              ],
              "circle-color": "#7a4320",
              "circle-stroke-color": "#fdf8f0",
              "circle-stroke-width": 2,
              "circle-opacity": 0.85,
            }}
          />
        </Source>
      )}

      {regions && (
        <Source id="regions" type="geojson" data={regions as AnyGeo}>
          <Layer
            id={REGION_LAYER}
            type="circle"
            minzoom={4}
            paint={{
              "circle-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                4,
                3,
                8,
                6,
                12,
                10,
              ],
              "circle-color": "#d4832d",
              "circle-stroke-color": "#fdf8f0",
              "circle-stroke-width": 1,
              "circle-opacity": 0.9,
            }}
          />
        </Source>
      )}

      {shops && (
        <Source
          id="shops"
          type="geojson"
          data={shops as AnyGeo}
          cluster
          clusterMaxZoom={14}
          clusterRadius={50}
        >
          <Layer
            id={SHOP_CLUSTER_LAYER}
            type="circle"
            filter={["has", "point_count"]}
            paint={{
              "circle-color": [
                "step",
                ["get", "point_count"],
                "#c79b6c",
                25,
                "#a36a3a",
                100,
                "#6f3d18",
              ],
              "circle-radius": [
                "step",
                ["get", "point_count"],
                14,
                25,
                18,
                100,
                24,
              ],
              "circle-stroke-color": "#fdf8f0",
              "circle-stroke-width": 1.5,
              "circle-opacity": 0.92,
            }}
          />
          <Layer
            id={SHOP_CLUSTER_COUNT_LAYER}
            type="symbol"
            filter={["has", "point_count"]}
            layout={{
              "text-field": ["get", "point_count_abbreviated"],
              "text-size": 12,
              "text-allow-overlap": true,
            }}
            paint={{ "text-color": "#fdf8f0" }}
          />
          <Layer
            id={SHOP_POINT_LAYER}
            type="circle"
            filter={["!", ["has", "point_count"]]}
            paint={{
              "circle-color": "#6f3d18",
              "circle-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                6,
                6,
                12,
                8,
                16,
                11,
              ],
              "circle-stroke-color": "#fdf8f0",
              "circle-stroke-width": 2.5,
              "circle-opacity": 1,
            }}
          />
        </Source>
      )}

      {popup && (
        <Popup
          longitude={popup.longitude}
          latitude={popup.latitude}
          anchor="top"
          closeOnClick={false}
          onClose={() => setPopup(null)}
        >
          <div className="px-1 py-0.5">
            <div className="font-semibold text-coffee-900">{popup.title}</div>
            {popup.subtitle && (
              <div className="text-xs text-gray-600">{popup.subtitle}</div>
            )}
            <div className="mt-1 flex gap-3 text-xs">
              {popup.detailHref && (
                <Link
                  href={popup.detailHref}
                  className="text-coffee-700 underline"
                >
                  details →
                </Link>
              )}
              {popup.link && (
                <a
                  href={popup.link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-amber-700 underline"
                >
                  website
                </a>
              )}
            </div>
            {popup.links && (
              <div className="mt-1 flex flex-wrap gap-3 text-xs">
                {popup.links.map((l) => (
                  <Link
                    key={l.href}
                    href={l.href}
                    className="text-coffee-700 underline"
                  >
                    {l.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </Popup>
      )}

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
              {viewState.zoom < SHOPS_MIN_ZOOM
                ? `coffee shops (zoom ≥${SHOPS_MIN_ZOOM})`
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

      <div className="absolute right-3 top-3 rounded bg-white/90 px-3 py-2 text-xs shadow">
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={showRoutes}
            onChange={toggleRoutes}
            className="accent-amber-600"
          />
          <span className="inline-block h-0.5 w-4 rounded bg-amber-500 align-middle" />
          Trade routes
        </label>
        {showRoutes && (
          <div className="mt-1 text-gray-500">
            {routesLoading
              ? "loading…"
              : routes
                ? `${routes.features.length} green-coffee flows`
                : ""}
          </div>
        )}
      </div>
    </Map>
  );
}
