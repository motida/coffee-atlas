"""Tests for /origins — the landing-page map's data source."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def origins_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """Two countries (one geocoded, one not) and two regions (ditto)."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO org_countries (id, name, iso_code, latitude, longitude, production_volume) "
        "VALUES ('c1', 'Ethiopia', 'ET', 9.145, 40.489, 471000), "
        "('c2', 'Atlantis', NULL, NULL, NULL, NULL)"
    )
    conn.execute(
        "INSERT INTO org_regions (id, name, country_id, latitude, longitude) VALUES "
        "('r1', 'Yirgacheffe', 'c1', 6.16, 38.2), "
        "('r2', 'Lost Region', 'c1', NULL, NULL)"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(origins_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: origins_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_origins(client):
    rows = client.get("/api/v1/origins").json()
    assert {r["id"] for r in rows} == {"c1", "c2"}


def test_list_origins_pagination(client):
    rows = client.get("/api/v1/origins", params={"limit": 1, "offset": 1}).json()
    assert len(rows) == 1


def test_origins_geo_skips_ungeocoded(client):
    fc = client.get("/api/v1/origins/geo").json()
    assert fc["type"] == "FeatureCollection"
    assert [f["properties"]["id"] for f in fc["features"]] == ["c1"]
    feature = fc["features"][0]
    assert feature["geometry"]["coordinates"] == [40.489, 9.145]  # [lng, lat]
    assert feature["properties"]["production_volume"] == 471000


def test_regions_geo_joins_country(client):
    fc = client.get("/api/v1/origins/regions/geo").json()
    assert [f["properties"]["id"] for f in fc["features"]] == ["r1"]
    assert fc["features"][0]["properties"]["country_name"] == "Ethiopia"
    assert fc["features"][0]["properties"]["iso_code"] == "ET"


def test_origin_detail_and_404(client):
    assert client.get("/api/v1/origins/c1").json()["name"] == "Ethiopia"
    assert client.get("/api/v1/origins/nope").status_code == 404


def test_region_detail_and_404(client):
    # /origins/regions/{id} must win over /origins/{origin_id} route matching.
    assert client.get("/api/v1/origins/regions/r1").json()["name"] == "Yirgacheffe"
    assert client.get("/api/v1/origins/regions/nope").status_code == 404
