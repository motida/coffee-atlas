"""Mapbox geocoding service for converting place names to coordinates."""

import httpx

from backend.config import settings


class GeocodingService:
    BASE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"

    async def geocode(self, query: str) -> tuple[float, float] | None:
        """Geocode a place name to (latitude, longitude). Returns None if not found."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/{query}.json",
                params={"access_token": settings.MAPBOX_ACCESS_TOKEN, "limit": 1},
            )
            response.raise_for_status()
            data = response.json()

        features = data.get("features", [])
        if not features:
            return None

        lng, lat = features[0]["center"]
        return (lat, lng)

    async def batch_geocode(self, queries: list[str]) -> list[tuple[float, float] | None]:
        """Geocode multiple place names."""
        results = []
        for query in queries:
            results.append(await self.geocode(query))
        return results
