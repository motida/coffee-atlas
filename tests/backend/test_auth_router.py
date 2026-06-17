"""Tests for /api/v1/auth (register, login, logout, me)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.db.pg import get_pg
from backend.main import app


@pytest.fixture
def client(pg, pg_pool) -> Iterator[TestClient]:
    # `pg` truncates usr_* on teardown (per-test isolation). The override uses
    # the pool directly so each request gets production commit/rollback semantics.
    settings.JWT_SECRET = "router-test-secret-key-at-least-32-bytes!!"
    settings.COOKIE_SECURE = False  # TestClient speaks http; Secure cookies won't persist

    def override_get_pg():
        with pg_pool.connection() as conn:
            yield conn

    app.dependency_overrides[get_pg] = override_get_pg
    yield TestClient(app)
    app.dependency_overrides.clear()


def _register(client: TestClient, email="a@example.com", password="password123", name="Ada"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )


def test_register_sets_cookie_and_returns_user(client: TestClient) -> None:
    res = _register(client)
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "a@example.com"
    assert body["display_name"] == "Ada"
    assert body["is_active"] is True
    assert "password_hash" not in body
    assert settings.COOKIE_NAME in res.cookies


def test_register_duplicate_email_409(client: TestClient) -> None:
    assert _register(client).status_code == 201
    # Case-insensitive: different case still conflicts.
    dup = _register(client, email="A@Example.com")
    assert dup.status_code == 409


def test_register_short_password_422(client: TestClient) -> None:
    res = _register(client, password="short")
    assert res.status_code == 422


def test_login_good_and_bad(client: TestClient) -> None:
    _register(client, email="b@example.com", password="password123")
    client.cookies.clear()

    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "B@example.com", "password": "password123"},
    )
    assert ok.status_code == 200
    assert settings.COOKIE_NAME in ok.cookies

    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "b@example.com", "password": "wrongpassword"},
    )
    assert bad.status_code == 401

    missing = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert missing.status_code == 401


def test_me_requires_cookie(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401

    _register(client, email="c@example.com")  # registration sets the cookie
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "c@example.com"


def test_logout_clears_session(client: TestClient) -> None:
    _register(client, email="d@example.com")
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401
