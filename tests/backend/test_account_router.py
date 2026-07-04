"""Tests for /api/v1/account (favorites + cupping notes)."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.db.connection import get_db
from backend.db.pg import get_pg
from backend.main import app


@pytest.fixture
def seeded_db(db: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Content DB with one variety and one product to reference."""
    db.execute("INSERT INTO var_varieties (id, name) VALUES ('v1', 'Geisha')")
    db.execute("INSERT INTO prod_products (id, name) VALUES ('p1', 'Geisha Natural')")
    return db


@pytest.fixture
def client(seeded_db, pg, pg_pool) -> Iterator[TestClient]:
    settings.JWT_SECRET = "account-test-secret-key-at-least-32-bytes!"
    settings.COOKIE_SECURE = False  # TestClient speaks http; Secure cookies won't persist

    def override_get_pg():
        with pg_pool.connection() as conn:
            yield conn

    app.dependency_overrides[get_db] = lambda: seeded_db
    app.dependency_overrides[get_pg] = override_get_pg
    yield TestClient(app)
    app.dependency_overrides.clear()


def _new_user(email: str) -> TestClient:
    """A client with its own cookie jar, signed in as a fresh user."""
    c = TestClient(app)  # shares app-level dependency overrides
    res = c.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": email.split("@")[0]},
    )
    assert res.status_code == 201
    return c


# --- Favorites ---
def test_favorite_crud_and_idempotency(client: TestClient) -> None:
    user = _new_user("fav@example.com")

    add = user.post("/api/v1/account/favorites", json={"entity_type": "variety", "entity_id": "v1"})
    assert add.status_code == 201
    fav_id = add.json()["id"]
    assert add.json()["entity_type"] == "variety"
    assert add.json()["name"] == "Geisha"  # display name resolved from DuckDB

    # Idempotent: same (type, id) returns the same row, no duplicate.
    again = user.post(
        "/api/v1/account/favorites", json={"entity_type": "variety", "entity_id": "v1"}
    )
    assert again.status_code == 201
    assert again.json()["id"] == fav_id

    listed = user.get("/api/v1/account/favorites")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["name"] == "Geisha"

    # Filter by entity_type.
    assert len(user.get("/api/v1/account/favorites?entity_type=variety").json()) == 1
    assert len(user.get("/api/v1/account/favorites?entity_type=shop").json()) == 0

    assert user.delete(f"/api/v1/account/favorites/{fav_id}").status_code == 204
    assert len(user.get("/api/v1/account/favorites").json()) == 0
    # Deleting again → 404.
    assert user.delete(f"/api/v1/account/favorites/{fav_id}").status_code == 404


def test_favorite_unknown_entity_id_404(client: TestClient) -> None:
    user = _new_user("nf@example.com")
    res = user.post(
        "/api/v1/account/favorites", json={"entity_type": "variety", "entity_id": "does-not-exist"}
    )
    assert res.status_code == 404


def test_favorite_bad_entity_type_422(client: TestClient) -> None:
    user = _new_user("bt@example.com")
    res = user.post("/api/v1/account/favorites", json={"entity_type": "banana", "entity_id": "v1"})
    assert res.status_code == 422


def test_favorite_requires_auth(client: TestClient) -> None:
    anon = TestClient(app)
    res = anon.post("/api/v1/account/favorites", json={"entity_type": "variety", "entity_id": "v1"})
    assert res.status_code == 401


# --- Cupping notes ---
def test_note_crud(client: TestClient) -> None:
    user = _new_user("note@example.com")

    add = user.post(
        "/api/v1/account/notes",
        json={
            "entity_type": "product",
            "entity_id": "p1",
            "notes": "Jasmine and bergamot",
            "score": 88.5,
            "brew_method": "V60",
        },
    )
    assert add.status_code == 201
    note = add.json()
    assert note["score"] == 88.5
    assert note["user_id"]
    note_id = note["id"]

    listed = user.get("/api/v1/account/notes?entity_type=product&entity_id=p1")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    patched = user.patch(f"/api/v1/account/notes/{note_id}", json={"score": 90, "notes": "Updated"})
    assert patched.status_code == 200
    assert patched.json()["score"] == 90
    assert patched.json()["notes"] == "Updated"

    assert user.delete(f"/api/v1/account/notes/{note_id}").status_code == 204
    assert len(user.get("/api/v1/account/notes").json()) == 0


def test_note_on_variety_ok_but_shop_422(client: TestClient) -> None:
    user = _new_user("nv@example.com")
    ok = user.post(
        "/api/v1/account/notes",
        json={"entity_type": "variety", "entity_id": "v1", "notes": "Floral"},
    )
    assert ok.status_code == 201
    # Shops are favoritable but not cuppable.
    bad = user.post(
        "/api/v1/account/notes",
        json={"entity_type": "shop", "entity_id": "v1", "notes": "n/a"},
    )
    assert bad.status_code == 422


def test_note_unknown_entity_404(client: TestClient) -> None:
    user = _new_user("nu@example.com")
    res = user.post(
        "/api/v1/account/notes",
        json={"entity_type": "product", "entity_id": "missing", "notes": "x"},
    )
    assert res.status_code == 404


# --- Isolation ---
def test_cross_user_isolation(client: TestClient) -> None:
    alice = _new_user("alice@example.com")
    bob = _new_user("bob@example.com")

    fav = alice.post(
        "/api/v1/account/favorites", json={"entity_type": "variety", "entity_id": "v1"}
    )
    alice_fav_id = fav.json()["id"]
    note = alice.post(
        "/api/v1/account/notes",
        json={"entity_type": "product", "entity_id": "p1", "notes": "Alice's note"},
    )
    alice_note_id = note.json()["id"]

    # Bob sees none of Alice's activity.
    assert bob.get("/api/v1/account/favorites").json() == []
    assert bob.get("/api/v1/account/notes").json() == []

    # Bob cannot delete Alice's rows (scoped by user_id → 404, not 403-leak).
    assert bob.delete(f"/api/v1/account/favorites/{alice_fav_id}").status_code == 404
    assert bob.delete(f"/api/v1/account/notes/{alice_note_id}").status_code == 404
    assert (
        bob.patch(f"/api/v1/account/notes/{alice_note_id}", json={"notes": "hijack"}).status_code
        == 404
    )

    # Alice still has them.
    assert len(alice.get("/api/v1/account/favorites").json()) == 1
    assert len(alice.get("/api/v1/account/notes").json()) == 1


def test_note_patch_explicit_null_notes_422(client: TestClient) -> None:
    """An explicit "notes": null must 422 at validation, not reach Postgres —
    the column is NOT NULL, and the NotNullViolation previously surfaced as an
    unhandled 500."""
    user = _new_user("nullnote@example.com")
    add = user.post(
        "/api/v1/account/notes",
        json={"entity_type": "product", "entity_id": "p1", "notes": "Original"},
    )
    note_id = add.json()["id"]

    res = user.patch(f"/api/v1/account/notes/{note_id}", json={"notes": None})
    assert res.status_code == 422

    # Nulling a nullable field (score) stays allowed.
    ok = user.patch(f"/api/v1/account/notes/{note_id}", json={"score": None})
    assert ok.status_code == 200
    assert ok.json()["notes"] == "Original"
