"""Tests for /api/v1/roasting/roasters."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def roasters_db() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO roast_roasters (id, name, location, website) VALUES "
        "('r1', 'Verve Coffee', 'Santa Cruz, CA', 'https://www.vervecoffee.com'), "
        "('r2', 'Onyx Coffee Lab', 'Arkansas', 'https://onyxcoffeelab.com')"
    )
    conn.execute(
        "INSERT INTO prod_products (id, name, roaster_id, is_blend, price) VALUES "
        "('p1', 'Ethiopia Ayla', 'r1', false, 28.0), "
        "('p2', 'Pride Blend', 'r1', true, 24.0)"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(roasters_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: roasters_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_roasters(client):
    r = client.get("/api/v1/roasting/roasters")
    assert r.status_code == 200
    rows = r.json()
    assert [row["name"] for row in rows] == ["Onyx Coffee Lab", "Verve Coffee"]


def test_get_roaster(client):
    r = client.get("/api/v1/roasting/roasters/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Verve Coffee"
    assert body["location"] == "Santa Cruz, CA"
    assert body["website"] == "https://www.vervecoffee.com"


def test_get_roaster_404(client):
    assert client.get("/api/v1/roasting/roasters/nope").status_code == 404


def test_roaster_products_via_products_filter(client):
    """A roaster's catalog is reachable through the existing product filter."""
    r = client.get("/api/v1/products", params={"roaster_id": "r1"})
    assert r.status_code == 200
    assert {p["name"] for p in r.json()} == {"Ethiopia Ayla", "Pride Blend"}
