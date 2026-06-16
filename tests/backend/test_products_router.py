"""Tests for /api/v1/products and /shops/{id}/products."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def products_db() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO roast_roasters (id, name, website) VALUES "
        "('r1', 'Verve Coffee', 'https://www.vervecoffee.com')"
    )
    conn.execute(
        "INSERT INTO prod_products (id, name, roaster_id, is_blend, price) VALUES "
        "('p1', 'Ethiopia Ayla', 'r1', false, 28.0), "
        "('p2', 'Pride Blend', 'r1', true, 24.0)"
    )
    conn.execute("INSERT INTO var_varieties (id, name, species) VALUES ('v1', 'Geisha', 'Arabica')")
    conn.execute("INSERT INTO flav_attributes (id, name) VALUES ('f1', 'Jasmine')")
    conn.execute("INSERT INTO org_countries (id, name) VALUES ('c1', 'Ethiopia')")
    conn.execute("INSERT INTO shop_shops (id, name) VALUES ('s1', 'Verve SF')")
    conn.execute(
        "INSERT INTO edges_product_variety (id, product_id, variety_id) VALUES ('e1','p1','v1')"
    )
    conn.execute(
        "INSERT INTO edges_product_flavor (id, product_id, flavor_id) VALUES ('e2','p1','f1')"
    )
    conn.execute(
        "INSERT INTO edges_product_country (id, product_id, country_id) VALUES ('e3','p1','c1')"
    )
    conn.execute(
        "INSERT INTO edges_shop_product (id, shop_id, product_id) VALUES ('e4','s1','p1'),('e5','s1','p2')"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(products_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: products_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_products(client):
    r = client.get("/api/v1/products")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert {row["roaster_name"] for row in rows} == {"Verve Coffee"}


def test_filter_blends(client):
    r = client.get("/api/v1/products", params={"is_blend": "true"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "Pride Blend"


def test_get_product_with_roaster_name(client):
    r = client.get("/api/v1/products/p1")
    assert r.status_code == 200
    assert r.json()["name"] == "Ethiopia Ayla"
    assert r.json()["roaster_name"] == "Verve Coffee"


def test_get_product_404(client):
    assert client.get("/api/v1/products/nope").status_code == 404


def test_product_varieties(client):
    r = client.get("/api/v1/products/p1/varieties")
    assert r.status_code == 200
    assert [v["name"] for v in r.json()] == ["Geisha"]


def test_product_flavors(client):
    r = client.get("/api/v1/products/p1/flavors")
    assert r.status_code == 200
    assert [f["name"] for f in r.json()] == ["Jasmine"]


def test_product_origin(client):
    r = client.get("/api/v1/products/p1/origin")
    assert r.status_code == 200
    body = r.json()
    assert [c["name"] for c in body["countries"]] == ["Ethiopia"]
    assert body["regions"] == []


def test_shop_products(client):
    r = client.get("/api/v1/shops/s1/products")
    assert r.status_code == 200
    assert {p["name"] for p in r.json()} == {"Ethiopia Ayla", "Pride Blend"}


def test_shop_products_404(client):
    assert client.get("/api/v1/shops/nope/products").status_code == 404
