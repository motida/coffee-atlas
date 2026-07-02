"""Tests for /flavor — the wheel tree construction and attribute detail."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app


@pytest.fixture
def flavor_db() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO flav_attributes (id, name, category, subcategory) VALUES "
        "('f1', 'Jasmine', 'Floral', 'White Flower'), "
        "('f2', 'Rose', 'Floral', 'White Flower'), "
        "('f3', 'Lemon', 'Fruity', 'Citrus'), "
        "('f4', 'Uncategorized Note', NULL, NULL), "
        "('f5', 'Odd Sub', 'Fruity', NULL)"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(flavor_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: flavor_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_wheel_builds_category_subcategory_tree(client):
    tree = client.get("/api/v1/flavor/wheel").json()
    assert set(tree) == {"Floral", "Fruity", "Other"}
    assert {leaf["name"] for leaf in tree["Floral"]["White Flower"]} == {"Jasmine", "Rose"}
    assert [leaf["name"] for leaf in tree["Fruity"]["Citrus"]] == ["Lemon"]


def test_wheel_null_category_and_subcategory_fall_back_to_other(client):
    tree = client.get("/api/v1/flavor/wheel").json()
    assert [leaf["name"] for leaf in tree["Other"]["Other"]] == ["Uncategorized Note"]
    assert [leaf["name"] for leaf in tree["Fruity"]["Other"]] == ["Odd Sub"]


def test_wheel_leaves_never_carry_the_embedding(client):
    tree = client.get("/api/v1/flavor/wheel").json()
    leaf = tree["Floral"]["White Flower"][0]
    assert "name_embedding" not in leaf


def test_attribute_detail_and_404(client):
    res = client.get("/api/v1/flavor/attributes/f1")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Jasmine"
    # The response model must filter the SELECT * — never ship 3072 floats.
    assert "name_embedding" not in body
    assert client.get("/api/v1/flavor/attributes/nope").status_code == 404
