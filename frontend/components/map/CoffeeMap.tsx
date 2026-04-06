"use client";

import { useState } from "react";
import Map from "react-map-gl";
import "mapbox-gl/dist/mapbox-gl.css";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

export default function CoffeeMap() {
  const [viewState, setViewState] = useState({
    latitude: 5,
    longitude: 20,
    zoom: 2,
  });

  if (!MAPBOX_TOKEN || MAPBOX_TOKEN === "pk-...") {
    return (
      <div className="flex h-full items-center justify-center bg-coffee-100">
        <div className="text-center">
          <p className="text-lg font-medium text-coffee-800">
            Mapbox token not configured
          </p>
          <p className="mt-2 text-sm text-coffee-600">
            Set NEXT_PUBLIC_MAPBOX_TOKEN in .env.local to enable the map.
          </p>
        </div>
      </div>
    );
  }

  return (
    <Map
      {...viewState}
      onMove={(evt) => setViewState(evt.viewState)}
      mapboxAccessToken={MAPBOX_TOKEN}
      mapStyle="mapbox://styles/mapbox/light-v11"
      style={{ width: "100%", height: "100%" }}
    />
  );
}
