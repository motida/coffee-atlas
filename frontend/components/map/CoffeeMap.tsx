"use client";

import { useState } from "react";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

export default function CoffeeMap() {
  const [viewState, setViewState] = useState({
    latitude: 5,
    longitude: 20,
    zoom: 2,
  });

  return (
    <Map
      {...viewState}
      onMove={(evt) => setViewState(evt.viewState)}
      mapStyle={MAP_STYLE}
      style={{ width: "100%", height: "100%" }}
    />
  );
}
