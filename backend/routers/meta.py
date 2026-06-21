"""App metadata endpoints.

A tiny version endpoint under /api/v1 so the frontend (which proxies only
/api/v1/*) can surface the live API version. The /health check stays at the
root for infra probes.
"""

from fastapi import APIRouter

from backend import __version__

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/version")
def get_version() -> dict[str, str]:
    """Backend API version (sourced from package metadata / pyproject.toml)."""
    return {"version": __version__}
