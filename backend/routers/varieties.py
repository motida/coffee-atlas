from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import duckdb

from backend.db.connection import fetchall_dicts, get_db
from backend.models.varieties import VarietyRead

router = APIRouter(prefix="/api/v1/varieties", tags=["varieties"])


@router.get("", response_model=list[VarietyRead])
def list_varieties(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    species: str | None = Query(None, description="Filter by species, e.g. Arabica or Robusta"),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if species is not None:
        where = "WHERE LOWER(species) = LOWER(?)"
        params.append(species)
    params.extend([limit, offset])
    return fetchall_dicts(
        db.execute(
            f"SELECT * FROM var_varieties {where} ORDER BY name LIMIT ? OFFSET ?",
            params,
        )
    )


@router.get("/{variety_id}", response_model=VarietyRead)
def get_variety(variety_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    row = db.execute("SELECT * FROM var_varieties WHERE id = ?", [variety_id]).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Variety not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))


@router.get("/{variety_id}/flavor")
def get_variety_flavor(
    variety_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    if not db.execute("SELECT 1 FROM var_varieties WHERE id = ?", [variety_id]).fetchone():
        raise HTTPException(status_code=404, detail="Variety not found")
    # Explicit column list: never ship the 3072-float name_embedding to clients.
    return fetchall_dicts(
        db.execute(
            """
            SELECT f.id, f.name, f.category, f.subcategory, f.description,
                   f.intensity_reference, f.sensory_reference, f.parent_id,
                   e.strength
            FROM flav_attributes f
            JOIN edges_variety_flavor e ON e.flavor_id = f.id
            WHERE e.variety_id = ?
            ORDER BY f.name
            """,
            [variety_id],
        )
    )
