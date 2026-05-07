from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import duckdb

from backend.db.connection import fetchall_dicts, get_db
from backend.models.shops import ShopRead

router = APIRouter(prefix="/api/v1/shops", tags=["shops"])

# Columns safe to ship to clients — excludes embedding vector (3072 floats).
SHOP_PUBLIC_COLS = (
    "id, name, latitude, longitude, address, city, country, "
    "website, rating, roasts_in_house, description, created_at, updated_at"
)


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    try:
        parts = [float(x) for x in bbox.split(",")]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid bbox: {e}") from e
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must be 'xmin,ymin,xmax,ymax'")
    return parts[0], parts[1], parts[2], parts[3]


@router.get("", response_model=list[ShopRead])
def list_shops(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute(f"SELECT {SHOP_PUBLIC_COLS} FROM shop_shops LIMIT ? OFFSET ?", [limit, offset])
    )


@router.get("/geo")
def get_shops_geo(
    bbox: str | None = Query(None, description="xmin,ymin,xmax,ymax (lng/lat)"),
    limit: int = Query(5000, ge=1, le=50000),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict[str, Any]:
    where = ["latitude IS NOT NULL"]
    params: list[Any] = []
    parsed = _parse_bbox(bbox)
    if parsed is not None:
        xmin, ymin, xmax, ymax = parsed
        where.append("longitude BETWEEN ? AND ?")
        where.append("latitude BETWEEN ? AND ?")
        params.extend([xmin, xmax, ymin, ymax])
    sql = f"SELECT {SHOP_PUBLIC_COLS} FROM shop_shops WHERE {' AND '.join(where)} LIMIT ?"
    params.append(limit)
    rows = fetchall_dicts(db.execute(sql, params))
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.pop("longitude"), row.pop("latitude")],
            },
            "properties": row,
        }
        for row in rows
    ]
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
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT * FROM (
                SELECT {SHOP_PUBLIC_COLS}, (
                    6371 * acos(
                        cos(radians(?)) * cos(radians(latitude))
                        * cos(radians(longitude) - radians(?))
                        + sin(radians(?)) * sin(radians(latitude))
                    )
                ) AS distance_km
                FROM shop_shops
                WHERE latitude IS NOT NULL
            )
            WHERE distance_km <= ?
            ORDER BY distance_km
            LIMIT ?
            """,
            [lat, lng, lat, radius_km, limit],
        )
    )


@router.get("/{shop_id}", response_model=ShopRead)
def get_shop(shop_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    row = db.execute(
        f"SELECT {SHOP_PUBLIC_COLS} FROM shop_shops WHERE id = ?", [shop_id]
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))
