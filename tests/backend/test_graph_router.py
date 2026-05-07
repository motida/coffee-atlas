"""Tests for /graph/traverse and /graph/path."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def graph_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """In-memory DB with a tiny graph: country c1 -> region r1 -> farm f1, plus
    variety v1 ↔ flavor flav1 via the variety_flavor edge table."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute("INSERT INTO org_countries (id, name) VALUES ('c1', 'Ethiopia')")
    conn.execute("INSERT INTO org_regions (id, name, country_id) VALUES ('r1', 'Yirg', 'c1')")
    conn.execute("INSERT INTO org_farms (id, name, region_id) VALUES ('f1', 'Konga', 'r1')")
    conn.execute("INSERT INTO var_varieties (id, name) VALUES ('v1', 'Geisha')")
    conn.execute("INSERT INTO flav_attributes (id, name) VALUES ('flav1', 'Jasmine')")

    conn.execute(
        "INSERT INTO edges_country_region (id, country_id, region_id) VALUES ('e1', 'c1', 'r1')"
    )
    conn.execute("INSERT INTO edges_region_farm (id, region_id, farm_id) VALUES ('e2', 'r1', 'f1')")
    conn.execute(
        "INSERT INTO edges_variety_flavor (id, variety_id, flavor_id, strength) "
        "VALUES ('e3', 'v1', 'flav1', 0.9)"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(graph_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: graph_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_traverse_walks_country_to_farms(client):
    r = client.get("/api/v1/graph/traverse", params={"start_id": "c1", "max_depth": 2})
    assert r.status_code == 200
    data = r.json()
    types = sorted(n["entity_type"] for n in data["nodes"])
    assert types == ["country", "farm", "region"]
    assert len(data["edges"]) == 2


def test_traverse_respects_depth(client):
    r = client.get("/api/v1/graph/traverse", params={"start_id": "c1", "max_depth": 1})
    types = sorted(n["entity_type"] for n in r.json()["nodes"])
    # depth 1 from country: country + region only, no farm.
    assert types == ["country", "region"]


def test_traverse_edge_types_filter(client):
    r = client.get(
        "/api/v1/graph/traverse",
        params={"start_id": "c1", "max_depth": 5, "edge_types": ["country_region"]},
    )
    edges = r.json()["edges"]
    assert {e["edge_type"] for e in edges} == {"country_region"}


def test_traverse_404_for_unknown_id(client):
    r = client.get("/api/v1/graph/traverse", params={"start_id": "nope"})
    assert r.status_code == 404


def test_traverse_variety_flavor_undirected(client):
    # Start from a flavor and walk back to the variety via the undirected edge.
    r = client.get("/api/v1/graph/traverse", params={"start_id": "flav1", "max_depth": 1})
    types = sorted(n["entity_type"] for n in r.json()["nodes"])
    assert types == ["flavor", "variety"]


def test_path_country_to_farm(client):
    r = client.get("/api/v1/graph/path", params={"start_id": "c1", "end_id": "f1"})
    assert r.status_code == 200
    data = r.json()
    assert [n["id"] for n in data["path"]] == ["c1", "r1", "f1"]
    assert data["total_weight"] == 2.0


def test_path_same_node_zero_weight(client):
    r = client.get("/api/v1/graph/path", params={"start_id": "c1", "end_id": "c1"})
    data = r.json()
    assert len(data["path"]) == 1
    assert data["edges"] == []
    assert data["total_weight"] == 0


def test_path_404_when_disconnected(client):
    # variety v1 lives in the flavor cluster, no path to a country.
    r = client.get("/api/v1/graph/path", params={"start_id": "v1", "end_id": "c1"})
    assert r.status_code == 404


def test_path_404_for_unknown_id(client):
    r = client.get("/api/v1/graph/path", params={"start_id": "c1", "end_id": "nope"})
    assert r.status_code == 404
