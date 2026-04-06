from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import get_db
from backend.models.origins import CountryRead

router = APIRouter(prefix="/api/v1/origins", tags=["origins"])


@router.get("", response_model=list[CountryRead])
def list_origins(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
):
    rows = db.execute(
        "SELECT * FROM org_countries LIMIT ? OFFSET ?", [limit, offset]
    ).fetchdf()
    return rows.to_dict(orient="records")


@router.get("/geo")
def get_origins_geo(db: duckdb.DuckDBPyConnection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM org_countries WHERE latitude IS NOT NULL"
    ).fetchdf()
    features = []
    for _, row in rows.iterrows():
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": row.to_dict(),
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/{origin_id}", response_model=CountryRead)
def get_origin(origin_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)):
    row = db.execute("SELECT * FROM org_countries WHERE id = ?", [origin_id]).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Origin not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))
