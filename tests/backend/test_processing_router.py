"""Tests for /processing endpoints: methods and their connected entities."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def proc_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """In-memory DB: two methods, one variety, one flavor, and their edges."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO proc_methods (id, name, category) VALUES "
        "('m_washed', 'Washed', 'washed'), "
        "('m_natural', 'Natural', 'natural')"
    )
    conn.execute(
        "INSERT INTO var_varieties (id, name, species) VALUES ('v_gesha', 'Gesha', 'Arabica')"
    )
    conn.execute(
        "INSERT INTO flav_attributes (id, name, category) VALUES ('f_berry', 'Berry', 'Fruity')"
    )
    conn.execute(
        "INSERT INTO edges_variety_processing (id, variety_id, method_id) VALUES "
        "('vp1', 'v_gesha', 'm_natural')"
    )
    conn.execute(
        "INSERT INTO edges_processing_flavor (id, method_id, flavor_id, effect) VALUES "
        "('pf1', 'm_natural', 'f_berry', 'enhances')"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(proc_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: proc_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_methods(client):
    r = client.get("/api/v1/processing/methods")
    assert r.status_code == 200
    assert [row["name"] for row in r.json()] == ["Natural", "Washed"]


def test_list_methods_category_filter(client):
    r = client.get("/api/v1/processing/methods", params={"category": "WASHED"})
    assert r.status_code == 200
    assert [row["name"] for row in r.json()] == ["Washed"]


def test_list_methods_excludes_embedding(client):
    r = client.get("/api/v1/processing/methods")
    assert all("description_embedding" not in row for row in r.json())


def test_get_method(client):
    r = client.get("/api/v1/processing/methods/m_washed")
    assert r.status_code == 200
    assert r.json()["name"] == "Washed"


def test_get_method_not_found(client):
    r = client.get("/api/v1/processing/methods/nope")
    assert r.status_code == 404


def test_method_varieties(client):
    r = client.get("/api/v1/processing/methods/m_natural/varieties")
    assert r.status_code == 200
    rows = r.json()
    assert [row["name"] for row in rows] == ["Gesha"]
    assert all("name_embedding" not in row for row in rows)


def test_method_varieties_empty(client):
    r = client.get("/api/v1/processing/methods/m_washed/varieties")
    assert r.status_code == 200
    assert r.json() == []


def test_method_varieties_not_found(client):
    r = client.get("/api/v1/processing/methods/nope/varieties")
    assert r.status_code == 404


def test_method_flavor(client):
    r = client.get("/api/v1/processing/methods/m_natural/flavor")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "Berry"
    assert rows[0]["effect"] == "enhances"


def test_method_flavor_not_found(client):
    r = client.get("/api/v1/processing/methods/nope/flavor")
    assert r.status_code == 404


def test_pagination(client):
    r = client.get("/api/v1/processing/methods", params={"limit": 1, "offset": 1})
    assert [row["name"] for row in r.json()] == ["Washed"]
