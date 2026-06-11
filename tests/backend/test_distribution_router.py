"""Tests for /distribution endpoints: importers, certifications, trade routes."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def dist_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """In-memory DB with two routes (one geocoded, one missing coords)."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO org_countries (id, name, latitude, longitude) VALUES "
        "('c_br', 'Brazil', -10.0, -55.0), "
        "('c_de', 'Germany', 51.0, 10.0), "
        "('c_xx', 'Nowhere', NULL, NULL)"
    )
    conn.execute(
        "INSERT INTO dist_importers (id, name, country_id, website) VALUES "
        "('imp1', 'Acme Beans', 'c_de', 'https://acme.example'), "
        "('imp2', 'Orphan Imports', NULL, NULL)"
    )
    conn.execute(
        "INSERT INTO dist_certifications (id, name, description) VALUES "
        "('cert1', 'Organic', 'No synthetic inputs')"
    )
    conn.execute(
        "INSERT INTO dist_trade_routes (id, exporter_country_id, importer_country_id) VALUES "
        "('rt1', 'c_br', 'c_de'), "
        "('rt2', 'c_br', 'c_xx')"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(dist_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: dist_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_importers_joins_country_name(client):
    r = client.get("/api/v1/distribution/importers")
    assert r.status_code == 200
    by_name = {row["name"]: row for row in r.json()}
    assert by_name["Acme Beans"]["country_name"] == "Germany"
    assert by_name["Orphan Imports"]["country_name"] is None


def test_list_certifications(client):
    r = client.get("/api/v1/distribution/certifications")
    assert r.status_code == 200
    assert [row["name"] for row in r.json()] == ["Organic"]


def test_list_trade_routes_joins_country_names(client):
    r = client.get("/api/v1/distribution/trade-routes")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert all(row["exporter_name"] == "Brazil" for row in rows)


def test_trade_routes_geo_linestrings(client):
    r = client.get("/api/v1/distribution/trade-routes/geo")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    # Only the fully geocoded route appears.
    assert len(fc["features"]) == 1
    feat = fc["features"][0]
    assert feat["geometry"]["type"] == "LineString"
    assert feat["geometry"]["coordinates"] == [[-55.0, -10.0], [10.0, 51.0]]
    assert feat["properties"]["exporter_name"] == "Brazil"
    assert feat["properties"]["importer_name"] == "Germany"


def test_pagination(client):
    r = client.get("/api/v1/distribution/trade-routes", params={"limit": 1, "offset": 1})
    assert len(r.json()) == 1
