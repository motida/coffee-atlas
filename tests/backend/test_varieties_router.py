"""Tests for the /varieties endpoints, focusing on the species filter."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def varieties_db() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO var_varieties (id, name, species) VALUES "
        "('v1', 'Geisha', 'Arabica'), "
        "('v2', 'SL28', 'Arabica'), "
        "('v3', 'Nemaya', 'Robusta'), "
        "('v4', 'BRS 2299', 'Robusta')"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(varieties_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: varieties_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_all_varieties(client):
    r = client.get("/api/v1/varieties", params={"limit": 50})
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_filter_by_species(client):
    r = client.get("/api/v1/varieties", params={"species": "Robusta", "limit": 50})
    assert r.status_code == 200
    rows = r.json()
    assert {row["name"] for row in rows} == {"Nemaya", "BRS 2299"}
    assert {row["species"] for row in rows} == {"Robusta"}


def test_filter_by_species_case_insensitive(client):
    r = client.get("/api/v1/varieties", params={"species": "arabica", "limit": 50})
    assert {row["name"] for row in r.json()} == {"Geisha", "SL28"}


def test_filter_by_species_unknown_returns_empty(client):
    r = client.get("/api/v1/varieties", params={"species": "Liberica", "limit": 50})
    assert r.json() == []


def test_results_ordered_by_name(client):
    r = client.get("/api/v1/varieties", params={"limit": 50})
    names = [row["name"] for row in r.json()]
    assert names == sorted(names)
