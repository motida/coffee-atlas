from typing import Any

from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import fetchall_dicts, get_db
from backend.models.origins import CountryRead

router = APIRouter(prefix="/api/v1/origins", tags=["origins"])


@router.get("", response_model=list[CountryRead])
def list_origins(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute("SELECT * FROM org_countries LIMIT ? OFFSET ?", [limit, offset])
    )


@router.get("/geo")
def get_origins_geo(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    rows = fetchall_dicts(
        db.execute(
            "SELECT id, name, iso_code, latitude, longitude, production_volume "
            "FROM org_countries WHERE latitude IS NOT NULL"
        )
    )
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": row,
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/regions/geo")
def get_regions_geo(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    rows = fetchall_dicts(
        db.execute(
            """
            SELECT r.id, r.name, r.latitude, r.longitude,
                   c.name AS country_name, c.iso_code
            FROM org_regions r
            JOIN org_countries c ON r.country_id = c.id
            WHERE r.latitude IS NOT NULL
            """
        )
    )
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": row,
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/{origin_id}", response_model=CountryRead)
def get_origin(origin_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    row = db.execute("SELECT * FROM org_countries WHERE id = ?", [origin_id]).fetchone()
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Origin not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))
