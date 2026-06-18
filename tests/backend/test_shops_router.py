"""Tests for /shops — specialty filtering on the discovery endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def shops_db() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    # s1 specialty, s2 not — both near (0,0) so /nearby sees them.
    conn.execute(
        "INSERT INTO shop_shops (id, name, latitude, longitude, is_specialty) VALUES "
        "('s1', 'Specialty Bar', 0.01, 0.01, true), "
        "('s2', 'Gas Station Coffee', 0.02, 0.02, false)"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(shops_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: shops_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_returns_only_specialty(client):
    ids = {row["id"] for row in client.get("/api/v1/shops").json()}
    assert ids == {"s1"}


def test_list_include_non_specialty(client):
    ids = {row["id"] for row in client.get("/api/v1/shops?include_non_specialty=true").json()}
    assert ids == {"s1", "s2"}


def test_geo_returns_only_specialty(client):
    fc = client.get("/api/v1/shops/geo").json()
    ids = {f["properties"]["id"] for f in fc["features"]}
    assert ids == {"s1"}


def test_nearby_returns_only_specialty(client):
    r = client.get("/api/v1/shops/nearby", params={"lat": 0.0, "lng": 0.0, "radius_km": 50})
    assert {row["id"] for row in r.json()} == {"s1"}


def test_detail_still_resolves_non_specialty(client):
    # Detail stays permissive so saved favorites / deep links don't break.
    r = client.get("/api/v1/shops/s2")
    assert r.status_code == 200
    assert r.json()["id"] == "s2"
