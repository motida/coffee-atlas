"""Geocoding service — converts place names to (lat, lng) coordinates.

Provider is TBD. Candidates: Nominatim/OSM (free, rate-limited), Pelias/Photon
(self-hosted), or a paid API. Implement when the `geocode` ingest stage lands.
"""


class GeocodingService:
    async def geocode(self, query: str) -> tuple[float, float] | None:
        raise NotImplementedError("Geocoding provider not yet chosen")

    async def batch_geocode(self, queries: list[str]) -> list[tuple[float, float] | None]:
        raise NotImplementedError("Geocoding provider not yet chosen")
