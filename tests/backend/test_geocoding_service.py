"""Tests for backend.services.geocoding — country lookup + Nominatim cache."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from backend.services.geocoding import (
    NominatimGeocoder,
    load_country_centroids,
    resolve_country,
)


def test_load_country_centroids_smoke():
    table = load_country_centroids()
    assert "Ethiopia" in table
    eth = table["Ethiopia"]
    assert eth.iso_code == "ET"
    assert -90 <= eth.latitude <= 90
    assert -180 <= eth.longitude <= 180


def test_resolve_country_alias():
    table = load_country_centroids()
    assert resolve_country("Vietnam", table) is not None
    assert resolve_country("Tanzania, United Republic Of", table) is not None
    assert resolve_country("Atlantis", table) is None


def _client_returning(payload: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


class CountingClient(httpx.Client):
    def __init__(self, payload: list[dict]) -> None:
        self.calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            self.calls += 1
            return httpx.Response(200, json=payload)

        super().__init__(transport=httpx.MockTransport(handler))


def test_nominatim_returns_geopoint(tmp_path: Path):
    cache = tmp_path / "cache.json"
    client = _client_returning([{"lat": "6.16", "lon": "38.21"}])
    geocoder = NominatimGeocoder(cache_path=cache, min_interval=0, client=client)
    pt = geocoder.lookup("Yirgacheffe, Ethiopia", country_iso="ET")
    assert pt is not None
    assert pt.latitude == pytest.approx(6.16)
    assert pt.longitude == pytest.approx(38.21)


def test_nominatim_cache_hit_skips_http(tmp_path: Path):
    cache = tmp_path / "cache.json"
    client = CountingClient([{"lat": "6.16", "lon": "38.21"}])
    geocoder = NominatimGeocoder(cache_path=cache, min_interval=0, client=client)
    geocoder.lookup("Yirgacheffe, Ethiopia", country_iso="ET")
    geocoder.lookup("Yirgacheffe, Ethiopia", country_iso="ET")
    assert client.calls == 1


def test_nominatim_negative_result_cached(tmp_path: Path):
    cache = tmp_path / "cache.json"
    client = CountingClient([])
    geocoder = NominatimGeocoder(cache_path=cache, min_interval=0, client=client)
    assert geocoder.lookup("Nowhere", country_iso="ZZ") is None
    assert geocoder.lookup("Nowhere", country_iso="ZZ") is None
    assert client.calls == 1
    payload = json.loads(cache.read_text())
    assert payload["zz|nowhere"] is None


def test_nominatim_persists_cache_between_instances(tmp_path: Path):
    cache = tmp_path / "cache.json"
    client_a = CountingClient([{"lat": "1.0", "lon": "2.0"}])
    NominatimGeocoder(cache_path=cache, min_interval=0, client=client_a).lookup(
        "Foo", country_iso="XX"
    )
    client_b = CountingClient([{"lat": "9.9", "lon": "9.9"}])
    pt = NominatimGeocoder(cache_path=cache, min_interval=0, client=client_b).lookup(
        "Foo", country_iso="XX"
    )
    assert pt is not None
    assert pt.latitude == pytest.approx(1.0)
    assert client_b.calls == 0
