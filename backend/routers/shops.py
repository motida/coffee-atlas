from typing import Any

from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import get_db
from backend.models.shops import ShopRead

router = APIRouter(prefix="/api/v1/shops", tags=["shops"])


@router.get("", response_model=list[ShopRead])
def list_shops(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = db.execute("SELECT * FROM shop_shops LIMIT ? OFFSET ?", [limit, offset]).fetchdf()
    return rows.to_dict(orient="records")


@router.get("/geo")
def get_shops_geo(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute("SELECT * FROM shop_shops WHERE latitude IS NOT NULL").fetchdf()
    features: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
                "properties": row.to_dict(),
            }
        )
    return {"type": "FeatureCollection", "features": features}


@router.get("/nearby")
def get_nearby_shops(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(5.0),
    limit: int = Query(20, ge=1, le=100),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Find shops within a given radius using Haversine approximation."""
    rows = db.execute(
        """
        SELECT *, (
            6371 * acos(
                cos(radians(?)) * cos(radians(latitude))
                * cos(radians(longitude) - radians(?))
                + sin(radians(?)) * sin(radians(latitude))
            )
        ) AS distance_km
        FROM shop_shops
        WHERE latitude IS NOT NULL
        HAVING distance_km <= ?
        ORDER BY distance_km
        LIMIT ?
        """,
        [lat, lng, lat, radius_km, limit],
    ).fetchdf()
    return rows.to_dict(orient="records")


@router.get("/{shop_id}", response_model=ShopRead)
def get_shop(shop_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    row = db.execute("SELECT * FROM shop_shops WHERE id = ?", [shop_id]).fetchone()
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Shop not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))
