import importlib.metadata

from fastapi.testclient import TestClient

from backend import __version__
from backend.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_version_comes_from_package_metadata():
    # The FastAPI app version must be sourced from the installed package metadata
    # (built from pyproject.toml), not a hardcoded literal.
    assert __version__ == importlib.metadata.version("coffee-atlas-backend")
    assert app.version == __version__
