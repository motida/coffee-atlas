from typing import Any

from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import fetchall_dicts, get_db
from backend.models.varieties import VarietyRead

router = APIRouter(prefix="/api/v1/varieties", tags=["varieties"])


@router.get("", response_model=list[VarietyRead])
def list_varieties(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute("SELECT * FROM var_varieties LIMIT ? OFFSET ?", [limit, offset])
    )


@router.get("/{variety_id}", response_model=VarietyRead)
def get_variety(variety_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    row = db.execute("SELECT * FROM var_varieties WHERE id = ?", [variety_id]).fetchone()
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Variety not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))


@router.get("/{variety_id}/flavor")
def get_variety_flavor(
    variety_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute(
            """
            SELECT f.* FROM flav_attributes f
            JOIN edges_variety_flavor e ON e.flavor_id = f.id
            WHERE e.variety_id = ?
            """,
            [variety_id],
        )
    )
