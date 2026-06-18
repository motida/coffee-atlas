from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import duckdb

from backend.db.connection import fetchall_dicts, fetchone_dict, get_db
from backend.models.roasting import RoasterListItem, RoasterRead, RoastProfileRead

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
    row = fetchone_dict(db.execute("SELECT * FROM roast_profiles WHERE id = ?", [profile_id]))
    if row is None:
        raise HTTPException(status_code=404, detail="Roast profile not found")
    return row


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
    row = fetchone_dict(db.execute("SELECT * FROM roast_roasters WHERE id = ?", [roaster_id]))
    if row is None:
        raise HTTPException(status_code=404, detail="Roaster not found")
    return row
