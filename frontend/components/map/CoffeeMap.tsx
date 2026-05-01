"use client";

import { useEffect, useState } from "react";
import Map, {
  Layer,
  Popup,
  Source,
  type MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { getOriginsGeo, getRegionsGeo } from "@/lib/api";
import type {
  CountryGeoProperties,
  GeoJSONFeatureCollection,
  RegionGeoProperties,
} from "@/lib/types";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const COUNTRY_LAYER = "countries-layer";
const REGION_LAYER = "regions-layer";

type AnyGeo = GeoJSONFeatureCollection<CountryGeoProperties | RegionGeoProperties>;

interface PopupState {
  longitude: number;
  latitude: number;
  title: string;
  subtitle?: string;
}

export default function CoffeeMap() {
  const [viewState, setViewState] = useState({
    latitude: 5,
    longitude: 20,
    zoom: 2,
  });
  const [countries, setCountries] =
    useState<GeoJSONFeatureCollection<CountryGeoProperties> | null>(null);
  const [regions, setRegions] =
    useState<GeoJSONFeatureCollection<RegionGeoProperties> | null>(null);
  const [popup, setPopup] = useState<PopupState | null>(null);

  useEffect(() => {
    getOriginsGeo()
      .then(setCountries)
      .catch((e) => console.error("Failed to load countries:", e));
    getRegionsGeo()
      .then(setRegions)
      .catch((e) => console.error("Failed to load regions:", e));
  }, []);

  const onClick = (e: MapLayerMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature) {
      setPopup(null);
      return;
    }
    const props = feature.properties as
      | CountryGeoProperties
      | RegionGeoProperties;
    const [lng, lat] = (feature.geometry as GeoJSON.Point).coordinates;
    if (feature.layer.id === COUNTRY_LAYER) {
      setPopup({
        longitude: lng,
        latitude: lat,
        title: props.name,
        subtitle: (props as CountryGeoProperties).iso_code ?? undefined,
      });
    } else {
      const region = props as RegionGeoProperties;
      setPopup({
        longitude: lng,
        latitude: lat,
        title: region.name.replace(/\b\w/g, (c) => c.toUpperCase()),
        subtitle: region.country_name,
      });
    }
  };

  return (
    <Map
      {...viewState}
      onMove={(evt) => setViewState(evt.viewState)}
      mapStyle={MAP_STYLE}
      style={{ width: "100%", height: "100%" }}
      interactiveLayerIds={[COUNTRY_LAYER, REGION_LAYER]}
      onClick={onClick}
      cursor={popup ? "pointer" : "grab"}
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
          </>
        ) : (
          <span className="text-gray-500">Loading origins…</span>
        )}
      </div>
    </Map>
  );
}
