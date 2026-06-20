"""Tests for /api/v1/recommend (item-based + personalized).

The item-based suite runs on an in-memory DuckDB only. The /for-you suite also
needs the Postgres user-data store, so it reuses the shared ``pg``/``pg_pool``
fixtures (which skip when no Postgres is reachable).
"""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.db.connection import get_db
from backend.db.pg import get_pg
from backend.db.schema import create_tables
from backend.main import app
from backend.services.embeddings import DIMENSIONS


def _vec(x: float) -> list[float]:
    return [float(x)] * DIMENSIONS


# A vector roughly orthogonal to the all-positive ones (cosine ~0).
_FAR = [(-1.0 if i % 2 else 1.0) for i in range(DIMENSIONS)]


@pytest.fixture
def rec_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """Seed: a seed variety with an embedding-near peer, an embedding-far peer,
    and a peer reachable only through shared flavor edges (no embedding)."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute(
        "INSERT INTO var_varieties (id, name, species, description, name_embedding) VALUES "
        "('s', 'Seed', 'Arabica', 'seed', ?), "
        "('near', 'Near', 'Arabica', 'near', ?), "
        "('far', 'Far', 'Arabica', 'far', ?), "
        "('graph', 'GraphOnly', 'Arabica', 'graph', NULL)",
        [_vec(1.0), _vec(0.99), _FAR],
    )
    conn.execute("INSERT INTO flav_attributes (id, name) VALUES ('f1', 'Floral'), ('f2', 'Citrus')")
    # Seed shares both flavors with 'graph' (overlap 2) and one with 'near' (overlap 1).
    conn.execute(
        "INSERT INTO edges_variety_flavor (id, variety_id, flavor_id) VALUES "
        "('e1', 's', 'f1'), ('e2', 's', 'f2'), "
        "('e3', 'graph', 'f1'), ('e4', 'graph', 'f2'), "
        "('e5', 'near', 'f1')"
    )
    # A product, so /for-you (entity_type=product) has something to rank.
    conn.execute(
        "INSERT INTO prod_products (id, name, description, description_embedding) VALUES "
        "('p1', 'Saved Roast', 'a', ?), "
        "('p2', 'Similar Roast', 'b', ?), "
        "('p3', 'Other Roast', 'c', ?)",
        [_vec(1.0), _vec(0.98), _FAR],
    )
    yield conn
    conn.close()


@pytest.fixture
def client(rec_db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: rec_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Item-based: /recommend/{entity_type}/{entity_id} ---
def test_similar_ranks_and_excludes_self(client: TestClient) -> None:
    r = client.get("/api/v1/recommend/variety/s", params={"limit": 10})
    assert r.status_code == 200
    recs = r.json()
    ids = [row["id"] for row in recs]
    assert "s" not in ids, "seed must not recommend itself"
    # Embedding-near beats embedding-far; graph-only peer beats the unrelated far one.
    assert ids.index("near") < ids.index("far")
    assert ids.index("graph") < ids.index("far")
    # Scores are descending.
    scores = [row["score"] for row in recs]
    assert scores == sorted(scores, reverse=True)


def test_similar_reason_reflects_shared_neighbors(client: TestClient) -> None:
    recs = client.get("/api/v1/recommend/variety/s", params={"limit": 10}).json()
    by_id = {row["id"]: row for row in recs}
    assert by_id["graph"]["reason"] == "Shares 2 flavor notes"
    assert by_id["near"]["reason"] == "Shares 1 flavor note"


def test_similar_limit_respected(client: TestClient) -> None:
    recs = client.get("/api/v1/recommend/variety/s", params={"limit": 1}).json()
    assert len(recs) == 1


def test_similar_graph_only_when_seed_has_no_embedding(client: TestClient) -> None:
    # 'graph' has a NULL embedding — recommendations must still come back, ranked
    # purely on the shared-flavor graph signal.
    recs = client.get("/api/v1/recommend/variety/graph", params={"limit": 10}).json()
    ids = [row["id"] for row in recs]
    assert "s" in ids  # seed shares both flavors with 'graph'


def test_similar_unknown_id_404(client: TestClient) -> None:
    assert client.get("/api/v1/recommend/variety/missing").status_code == 404


def test_similar_unsupported_entity_type_404(client: TestClient) -> None:
    # Countries have no embeddings, so they aren't recommendable.
    assert client.get("/api/v1/recommend/country/anything").status_code == 404


# --- Personalized: /recommend/for-you (Postgres-backed) ---
@pytest.fixture
def auth_client(rec_db, pg, pg_pool) -> Iterator[TestClient]:
    settings.JWT_SECRET = "recommend-test-secret-key-at-least-32-bytes!"
    settings.COOKIE_SECURE = False

    def override_get_pg():
        with pg_pool.connection() as conn:
            yield conn

    app.dependency_overrides[get_db] = lambda: rec_db
    app.dependency_overrides[get_pg] = override_get_pg
    yield TestClient(app)
    app.dependency_overrides.clear()


def _signed_in(email: str) -> TestClient:
    c = TestClient(app)
    res = c.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "u"},
    )
    assert res.status_code == 201
    return c


def test_for_you_requires_auth(auth_client: TestClient) -> None:
    anon = TestClient(app)
    assert anon.get("/api/v1/recommend/for-you").status_code == 401


def test_for_you_empty_without_activity(auth_client: TestClient) -> None:
    user = _signed_in("noactivity@example.com")
    res = user.get("/api/v1/recommend/for-you", params={"entity_type": "product"})
    assert res.status_code == 200
    assert res.json() == []


def test_for_you_recommends_excluding_saved(auth_client: TestClient) -> None:
    user = _signed_in("foryou@example.com")
    # Favorite p1; the feed should surface its embedding-near peer p2, not p1 itself.
    fav = user.post("/api/v1/account/favorites", json={"entity_type": "product", "entity_id": "p1"})
    assert fav.status_code == 201

    res = user.get("/api/v1/recommend/for-you", params={"entity_type": "product"})
    assert res.status_code == 200
    ids = [row["id"] for row in res.json()]
    assert "p1" not in ids, "must not recommend an already-saved item"
    assert "p2" in ids
    assert ids[0] == "p2", "the nearest peer should rank first"
