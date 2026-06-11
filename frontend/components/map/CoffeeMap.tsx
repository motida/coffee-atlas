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
import { getOriginsGeo, getRegionsGeo, getShopsGeo } from "@/lib/api";
import type {
  CountryGeoProperties,
  GeoJSONFeatureCollection,
  RegionGeoProperties,
  ShopGeoProperties,
} from "@/lib/types";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const COUNTRY_LAYER = "countries-layer";
const REGION_LAYER = "regions-layer";
const SHOP_CLUSTER_LAYER = "shops-clusters";
const SHOP_CLUSTER_COUNT_LAYER = "shops-cluster-count";
const SHOP_POINT_LAYER = "shops-points";

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
  CountryGeoProperties | RegionGeoProperties | ShopGeoProperties
>;

interface PopupState {
  longitude: number;
  latitude: number;
  title: string;
  subtitle?: string;
  link?: string;
  detailHref?: string;
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
    </Map>
  );
}
