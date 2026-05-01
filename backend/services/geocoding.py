"""Geocoding helpers — country centroid lookup + Nominatim region geocoder.

Countries: resolved against a static JSON dataset (data/raw/country_centroids.json).
Regions: resolved via OpenStreetMap Nominatim, with an on-disk JSON cache so
re-runs are free. The Nominatim usage policy requires a real User-Agent and
≤ 1 req/sec — both are honored here.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

DEFAULT_CENTROIDS = Path("data/raw/country_centroids.json")
DEFAULT_CACHE = Path("data/processed/nominatim_cache.json")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "coffee-atlas/0.1 (motida2@gmail.com)"

# CQI country names that don't match the ISO 3166 reference dataset verbatim.
COUNTRY_ALIASES: dict[str, str] = {
    "Vietnam": "Viet Nam",
    "Laos": "Lao People's Democratic Republic",
    "Taiwan": "Taiwan, Province of China",
    "Tanzania, United Republic Of": "Tanzania, United Republic of",
    "Cote d?Ivoire": "Côte d'Ivoire",
    "United States (Hawaii)": "United States",
    "United States (Puerto Rico)": "Puerto Rico",
}


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float
    iso_code: str | None = None


class Geocoder(Protocol):
    def lookup(self, query: str, country_iso: str | None = None) -> GeoPoint | None: ...


def load_country_centroids(path: Path = DEFAULT_CENTROIDS) -> dict[str, GeoPoint]:
    """Build a name → GeoPoint map from the bundled ISO 3166 reference file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, GeoPoint] = {}
    for entry in raw["ref_country_codes"]:
        out[entry["country"]] = GeoPoint(
            latitude=float(entry["latitude"]),
            longitude=float(entry["longitude"]),
            iso_code=entry.get("alpha2"),
        )
    return out


def resolve_country(name: str, table: dict[str, GeoPoint]) -> GeoPoint | None:
    """Look up a country by name, falling back to known CQI→ISO aliases."""
    if name in table:
        return table[name]
    canonical = COUNTRY_ALIASES.get(name)
    if canonical and canonical in table:
        return table[canonical]
    return None


class NominatimGeocoder:
    """Rate-limited Nominatim client with persistent JSON cache.

    Cache key is `(country_iso or '*') + '|' + query.lower()`. A miss is
    cached as `null` so we don't re-query unsuccessful lookups.
    """

    def __init__(
        self,
        cache_path: Path = DEFAULT_CACHE,
        min_interval: float = 1.05,
        client: httpx.Client | None = None,
    ) -> None:
        self.cache_path = cache_path
        self.min_interval = min_interval
        self._client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=10.0)
        self._last_call: float = 0.0
        self._cache: dict[str, dict[str, float] | None] = self._load_cache()

    def _load_cache(self) -> dict[str, dict[str, float] | None]:
        if not self.cache_path.exists():
            return {}
        return json.loads(self.cache_path.read_text(encoding="utf-8"))

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _key(self, query: str, country_iso: str | None) -> str:
        return f"{(country_iso or '*').lower()}|{query.lower()}"

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()

    def lookup(self, query: str, country_iso: str | None = None) -> GeoPoint | None:
        key = self._key(query, country_iso)
        if key in self._cache:
            cached = self._cache[key]
            return GeoPoint(cached["lat"], cached["lng"]) if cached else None

        self._throttle()
        params = {"q": query, "format": "json", "limit": "1"}
        if country_iso:
            params["countrycodes"] = country_iso.lower()
        resp = self._client.get(NOMINATIM_URL, params=params)
        resp.raise_for_status()
        results = resp.json()

        if results:
            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            self._cache[key] = {"lat": lat, "lng": lng}
            self._save_cache()
            return GeoPoint(lat, lng)

        self._cache[key] = None
        self._save_cache()
        return None

    def close(self) -> None:
        self._client.close()
