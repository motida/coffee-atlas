"""Tests for /search/text and /search/semantic.

Semantic search hits the Gemini API in production, so the embedding
service is monkeypatched to a deterministic stub.
"""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.db.connection import get_db
from backend.db.schema import create_tables
from backend.main import app
from backend.services.embeddings import DIMENSIONS


@pytest.fixture
def search_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """In-memory DB with a small mix of varieties, flavors, countries, shops."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO var_varieties (id, name, species, description) VALUES "
        "('v1', 'Geisha', 'Arabica', 'Floral aromatic Ethiopian landrace'), "
        "('v2', 'SL28', 'Arabica', 'Bold Kenyan variety'), "
        "('v3', 'Caturra', 'Arabica', 'Compact Brazilian mutation'), "
        "('v4', 'Nemaya', 'Robusta', 'Floral hardy rootstock hybrid')"
    )
    conn.execute(
        "INSERT INTO flav_attributes (id, name, description) VALUES "
        "('f1', 'Floral', 'Aromatic flowers'), "
        "('f2', 'Citrus', 'Bright acidity')"
    )
    conn.execute("INSERT INTO org_countries (id, name) VALUES ('c1', 'Ethiopia'), ('c2', 'Kenya')")
    conn.execute("INSERT INTO org_regions (id, name) VALUES ('r1', 'sidamo'), ('r2', 'nyeri')")
    conn.execute(
        "INSERT INTO shop_shops (id, name, description, latitude, longitude) VALUES "
        "('s1', 'Floral Cafe', 'Specialty pour-over shop', 1.0, 2.0)"
    )
    yield conn
    conn.close()


@pytest.fixture
def client(search_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: search_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_text_search_matches_across_types(client):
    r = client.get("/api/v1/search/text", params={"query": "floral", "limit": 50})
    assert r.status_code == 200
    results = r.json()
    types = sorted({row["entity_type"] for row in results})
    # "floral" hits Geisha (description), Floral (flavor), Floral Cafe (shop).
    assert "variety" in types
    assert "flavor" in types
    assert "shop" in types


def test_text_search_entity_type_filter(client):
    r = client.get(
        "/api/v1/search/text",
        params=[("query", "floral"), ("limit", "50"), ("entity_types", "flavor")],
    )
    results = r.json()
    assert results, "expected at least one match"
    assert {row["entity_type"] for row in results} == {"flavor"}


def test_text_search_species_filter_scopes_to_variety(client):
    # "floral" also matches a flavor and a shop, but a species filter must
    # restrict the result set to varieties of that species only.
    r = client.get(
        "/api/v1/search/text",
        params=[("query", "floral"), ("species", "Arabica"), ("limit", "50")],
    )
    assert r.status_code == 200
    results = r.json()
    assert {row["entity_type"] for row in results} == {"variety"}
    assert {row["id"] for row in results} == {"v1"}


def test_text_search_species_robusta(client):
    # Same query, the other species: only the Robusta variety comes back.
    r = client.get(
        "/api/v1/search/text",
        params=[("query", "floral"), ("species", "Robusta"), ("limit", "50")],
    )
    assert {row["id"] for row in r.json()} == {"v4"}


def test_text_search_species_case_insensitive(client):
    r = client.get(
        "/api/v1/search/text",
        params=[("query", "floral"), ("species", "arabica"), ("limit", "50")],
    )
    assert {row["id"] for row in r.json()} == {"v1"}


def test_text_search_empty_query_rejected(client):
    r = client.get("/api/v1/search/text", params={"query": ""})
    assert r.status_code == 422


def test_text_search_no_match(client):
    r = client.get("/api/v1/search/text", params={"query": "xyzzynonexistent"})
    assert r.json() == []


def test_semantic_search_uses_embedding(client, search_db, monkeypatch):
    """Stub the embedder so the test stays offline."""

    class FakeEmbedder:
        def __init__(self, *_, **__):
            pass

        def embed(self, text: str) -> list[float]:
            # Deterministic vector — values don't matter, ranking just needs
            # SOME order.
            return [0.01] * DIMENSIONS

    # Pin the embeddings config so the test exercises the real semantic path
    # regardless of the ambient environment (no .env / GEMINI_API_KEY in CI).
    monkeypatch.setattr(settings, "ENABLE_EMBEDDINGS", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("backend.routers.search.EmbeddingService", FakeEmbedder)

    # Add a fake embedding to one variety + one flavor + one roast profile so
    # the cosine call has something to compute against — the roast profile
    # exercises the description_embedding column path.
    vec = [0.01] * DIMENSIONS
    search_db.execute("UPDATE var_varieties SET name_embedding = ? WHERE id = 'v1'", [vec])
    search_db.execute("UPDATE flav_attributes SET name_embedding = ? WHERE id = 'f1'", [vec])
    search_db.execute(
        "INSERT INTO roast_profiles (id, name, description, description_embedding) "
        "VALUES ('p1', 'Nordic Light', 'Floral filter roast', ?)",
        [vec],
    )

    r = client.get("/api/v1/search/semantic", params={"query": "floral", "limit": 10})
    assert r.status_code == 200
    results = r.json()
    assert results, "expected results for entities with embeddings"
    assert {row["entity_type"] for row in results} == {"variety", "flavor", "roast_profile"}
    # Each result should carry a numeric similarity score.
    for row in results:
        assert isinstance(row["similarity"], float)


def test_semantic_search_falls_back_without_key(client, monkeypatch):
    """With no Gemini key (e.g. the public demo), /semantic must degrade to text
    search and return 200 instead of 502."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    r = client.get("/api/v1/search/semantic", params={"query": "floral", "limit": 10})
    assert r.status_code == 200
    results = r.json()
    assert results, "fallback should still surface text matches"
    # Text-search fallback carries no similarity score.
    assert all(row["similarity"] is None for row in results)
