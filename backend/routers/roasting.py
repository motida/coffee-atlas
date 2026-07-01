"""Roasting domain endpoints: roast profiles and roasters (with product counts)."""

from typing import Any

import duckdb
from fastapi import APIRouter, Depends, Query

from backend.db.connection import fetchall_dicts, get_db
from backend.models.roasting import RoasterListItem, RoasterRead, RoastProfileRead
from backend.routers._helpers import fetchone_or_404

router = APIRouter(prefix="/api/v1/roasting", tags=["roasting"])


@router.get("/profiles", response_model=list[RoastProfileRead])
def list_profiles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute("SELECT * FROM roast_profiles LIMIT ? OFFSET ?", [limit, offset])
    )


@router.get("/profiles/{profile_id}", response_model=RoastProfileRead)
def get_profile(profile_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    return fetchone_or_404(
        db.execute("SELECT * FROM roast_profiles WHERE id = ?", [profile_id]), "Roast profile"
    )


@router.get("/roasters", response_model=list[RoasterListItem])
def list_roasters(
    limit: int = Query(60, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, description="Case-insensitive match on roaster name"),
    sort: str = Query("count", pattern="^(count|name)$"),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if search:
        where = "WHERE LOWER(r.name) LIKE ?"
        params.append(f"%{search.lower()}%")
    order = "product_count DESC, r.name" if sort == "count" else "r.name"
    params.extend([limit, offset])
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT r.id, r.name, r.location, r.website, r.created_at, r.updated_at,
                   COUNT(e.product_id) AS product_count
            FROM roast_roasters r
            LEFT JOIN edges_roaster_product e ON e.roaster_id = r.id
            {where}
            GROUP BY r.id, r.name, r.location, r.website, r.created_at, r.updated_at
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            params,
        )
    )


@router.get("/roasters/{roaster_id}", response_model=RoasterRead)
def get_roaster(roaster_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    return fetchone_or_404(
        db.execute("SELECT * FROM roast_roasters WHERE id = ?", [roaster_id]), "Roaster"
    )
