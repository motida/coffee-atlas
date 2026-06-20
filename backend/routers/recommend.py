"""Recommendation endpoints.

- ``GET /recommend/{entity_type}/{entity_id}`` — item-based "you might also
  like" for any recommendable entity (hybrid embedding + graph overlap).
- ``GET /recommend/for-you`` — the signed-in user's personalized feed, built
  from their favorites + cupping notes. Postgres-backed, so it 503s when no
  user-data store is configured (like the rest of ``/account``).
"""

from typing import Any

import duckdb
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import DictRow

from backend.db.connection import get_db
from backend.db.pg import get_pg
from backend.models.recommend import Recommendation
from backend.routers._helpers import require_entity
from backend.services.auth import get_current_user
from backend.services.recommendations import RECOMMENDABLE, RecommendationService

router = APIRouter(prefix="/api/v1/recommend", tags=["recommend"])

_service = RecommendationService()


def _require_recommendable(entity_type: str) -> None:
    if entity_type not in RECOMMENDABLE:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Recommendations are not available for '{entity_type}'. "
                f"Supported: {sorted(RECOMMENDABLE)}"
            ),
        )


@router.get("/for-you", response_model=list[Recommendation])
def recommendations_for_you(
    entity_type: str = Query("product"),
    limit: int = Query(10, ge=1, le=50),
    user: dict[str, Any] = Depends(get_current_user),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> list[Recommendation]:
    _require_recommendable(entity_type)
    return _service.for_user(db, pg, user["id"], entity_type, limit)


@router.get("/{entity_type}/{entity_id}", response_model=list[Recommendation])
def similar_entities(
    entity_type: str,
    entity_id: str,
    limit: int = Query(6, ge=1, le=50),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[Recommendation]:
    _require_recommendable(entity_type)
    require_entity(db, RECOMMENDABLE[entity_type].table, entity_id, entity_type)
    return _service.similar(db, entity_type, entity_id, limit)
