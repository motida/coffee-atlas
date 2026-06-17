"""Helpers for assembling GeoJSON from query rows.

The geo endpoints (origins, shops, trade routes) all turn DuckDB rows into a
GeoJSON ``FeatureCollection``; these keep the feature/collection shape in one
place so every layer emits identical structure.
"""

from typing import Any


def point_feature(longitude: Any, latitude: Any, properties: dict[str, Any]) -> dict[str, Any]:
    """A GeoJSON Point Feature at ``[longitude, latitude]`` (lng/lat order)."""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }


def linestring_feature(coordinates: list[list[Any]], properties: dict[str, Any]) -> dict[str, Any]:
    """A GeoJSON LineString Feature through the given ``[lng, lat]`` coordinates."""
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": properties,
    }


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap features in a GeoJSON FeatureCollection."""
    return {"type": "FeatureCollection", "features": features}
