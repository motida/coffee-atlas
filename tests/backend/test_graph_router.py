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
    """In-memory DB with a connected graph:

        country c1 -> region r1 -> farm f1 -> variety v1 -> {flavor flav1, method p1}

    The farm_variety edge bridges the geographic hierarchy to the
    variety/flavor/processing cluster, so the whole thing is one connected
    component. An isolated country c2 (no edges) exists for negative tests.
    """
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute("INSERT INTO org_countries (id, name) VALUES ('c1', 'Ethiopia')")
    conn.execute("INSERT INTO org_countries (id, name) VALUES ('c2', 'Brazil')")
    conn.execute("INSERT INTO org_regions (id, name, country_id) VALUES ('r1', 'Yirg', 'c1')")
    conn.execute("INSERT INTO org_farms (id, name, region_id) VALUES ('f1', 'Konga', 'r1')")
    conn.execute("INSERT INTO var_varieties (id, name) VALUES ('v1', 'Geisha')")
    conn.execute("INSERT INTO flav_attributes (id, name) VALUES ('flav1', 'Jasmine')")
    conn.execute("INSERT INTO proc_methods (id, name) VALUES ('p1', 'Washed')")

    conn.execute(
        "INSERT INTO edges_country_region (id, country_id, region_id) VALUES ('e1', 'c1', 'r1')"
    )
    conn.execute("INSERT INTO edges_region_farm (id, region_id, farm_id) VALUES ('e2', 'r1', 'f1')")
    conn.execute(
        "INSERT INTO edges_variety_flavor (id, variety_id, flavor_id, strength) "
        "VALUES ('e3', 'v1', 'flav1', 0.9)"
    )
    conn.execute(
        "INSERT INTO edges_farm_variety (id, farm_id, variety_id) VALUES ('e4', 'f1', 'v1')"
    )
    conn.execute(
        "INSERT INTO edges_variety_processing (id, variety_id, method_id) VALUES ('e5', 'v1', 'p1')"
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


def test_traverse_crosses_from_geo_to_flavor(client):
    # Deep enough to walk country -> region -> farm -> variety -> flavor/processing.
    r = client.get("/api/v1/graph/traverse", params={"start_id": "c1", "max_depth": 5})
    data = r.json()
    types = sorted(n["entity_type"] for n in data["nodes"])
    assert types == ["country", "farm", "flavor", "processing", "region", "variety"]
    edge_types = {e["edge_type"] for e in data["edges"]}
    assert {"farm_variety", "variety_flavor", "variety_processing"} <= edge_types


def test_path_spans_components(client):
    # The graph is now one connected component: country reaches flavor.
    r = client.get("/api/v1/graph/path", params={"start_id": "c1", "end_id": "flav1"})
    assert r.status_code == 200
    data = r.json()
    assert [n["id"] for n in data["path"]] == ["c1", "r1", "f1", "v1", "flav1"]
    assert data["total_weight"] == 4.0


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
    # c2 (Brazil) is an isolated node with no edges — unreachable from c1.
    r = client.get("/api/v1/graph/path", params={"start_id": "c1", "end_id": "c2"})
    assert r.status_code == 404


def test_path_404_for_unknown_id(client):
    r = client.get("/api/v1/graph/path", params={"start_id": "c1", "end_id": "nope"})
    assert r.status_code == 404


def test_traverse_node_budget_truncates(client, monkeypatch):
    """The server-side work budget must stop a traversal that would otherwise
    fan out unbounded (depth alone doesn't cap cost on high-degree nodes) and
    flag the response as truncated."""
    import backend.routers.graph as graph_router

    monkeypatch.setattr(graph_router, "MAX_TRAVERSE_NODES", 2)
    r = client.get("/api/v1/graph/traverse", params={"start_id": "c1", "max_depth": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["truncated"] is True
    assert len(data["nodes"]) <= 2


def test_traverse_within_budget_not_truncated(client):
    r = client.get("/api/v1/graph/traverse", params={"start_id": "c1", "max_depth": 5})
    assert r.json()["truncated"] is False


def test_path_budget_exhausted_404(client, monkeypatch):
    import backend.routers.graph as graph_router

    monkeypatch.setattr(graph_router, "MAX_PATH_VISITED", 1)
    r = client.get("/api/v1/graph/path", params={"start_id": "c1", "end_id": "flav1"})
    assert r.status_code == 404
    assert "budget" in r.json()["detail"]


def test_traverse_crosses_processing_flavor(client, graph_db):
    """edges_processing_flavor is one of the 18 edge tables and must be
    traversable — it was previously missing from the router's EDGES list, so
    processing <-> flavor was invisible to /graph/traverse and /graph/path."""
    graph_db.execute(
        "INSERT INTO edges_processing_flavor (id, method_id, flavor_id, effect) "
        "VALUES ('e6', 'p1', 'flav1', 'enhances')"
    )
    r = client.get("/api/v1/graph/traverse", params={"start_id": "p1", "max_depth": 1})
    ids = {n["id"] for n in r.json()["nodes"]}
    assert "flav1" in ids
    edge_types = {e["edge_type"] for e in r.json()["edges"]}
    assert "processing_flavor" in edge_types
