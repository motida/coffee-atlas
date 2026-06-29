import importlib.metadata

from fastapi.testclient import TestClient

import backend.db.pg as pg
from backend import __version__
from backend.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    # `accounts` reflects whether the Postgres pool came up (DATABASE_URL set at
    # boot). Derive the expectation from the live pool state so the assertion is
    # exact regardless of the test environment's DATABASE_URL.
    expected_accounts = "enabled" if pg.pool_ready() else "disabled"
    assert response.json() == {"status": "ok", "accounts": expected_accounts}


def test_health_reports_accounts_disabled_without_pool(monkeypatch):
    # With no Postgres pool (the content-only / missing-DATABASE_URL case), the
    # probe must say "disabled" — the signal that auth/account routes will 503.
    monkeypatch.setattr(pg, "_pool", None)
    response = TestClient(app).get("/health")
    assert response.json() == {"status": "ok", "accounts": "disabled"}


def test_app_version_comes_from_package_metadata():
    # The FastAPI app version must be sourced from the installed package metadata
    # (built from pyproject.toml), not a hardcoded literal.
    assert __version__ == importlib.metadata.version("coffee-atlas-backend")
    assert app.version == __version__


def test_version_endpoint():
    # Exposed under /api/v1 so the frontend proxy can reach it.
    client = TestClient(app)
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json() == {"version": __version__}
