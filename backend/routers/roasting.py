from typing import Any

from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import get_db
from backend.models.roasting import RoastProfileRead

router = APIRouter(prefix="/api/v1/roasting", tags=["roasting"])


@router.get("/profiles", response_model=list[RoastProfileRead])
def list_profiles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = db.execute("SELECT * FROM roast_profiles LIMIT ? OFFSET ?", [limit, offset]).fetchdf()
    return rows.to_dict(orient="records")


@router.get("/profiles/{profile_id}", response_model=RoastProfileRead)
def get_profile(profile_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    row = db.execute("SELECT * FROM roast_profiles WHERE id = ?", [profile_id]).fetchone()
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Roast profile not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))
