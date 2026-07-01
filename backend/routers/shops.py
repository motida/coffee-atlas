"""Shop domain endpoints: specialty-shop discovery, map GeoJSON, and detail."""

from typing import Any

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db.columns import PRODUCT_COLS, prefixed
from backend.db.connection import fetchall_dicts, get_db
from backend.db.geojson import feature_collection, point_feature
from backend.models.products import ProductRead
from backend.models.shops import ShopRead
from backend.routers._helpers import fetchone_or_404, require_entity

router = APIRouter(prefix="/api/v1/shops", tags=["shops"])

# Columns safe to ship to clients — excludes embedding vector (3072 floats).
SHOP_PUBLIC_COLS = (
    "id, name, latitude, longitude, address, city, country, "
    "website, rating, roasts_in_house, description, is_specialty, "
    "created_at, updated_at"
)

# The app surfaces only specialty shops; discovery endpoints filter on this.
# `is_specialty` is materialized by the `specialty` ingest stage.
SPECIALTY_FILTER = "is_specialty"


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
    include_non_specialty: bool = Query(False, description="Include non-specialty shops"),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    where = "" if include_non_specialty else f"WHERE {SPECIALTY_FILTER}"
    return fetchall_dicts(
        db.execute(
            f"SELECT {SHOP_PUBLIC_COLS} FROM shop_shops {where} LIMIT ? OFFSET ?",
            [limit, offset],
        )
    )


@router.get("/geo")
def get_shops_geo(
    bbox: str | None = Query(None, description="xmin,ymin,xmax,ymax (lng/lat)"),
    limit: int = Query(5000, ge=1, le=50000),
    include_non_specialty: bool = Query(False, description="Include non-specialty shops"),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict[str, Any]:
    where = ["latitude IS NOT NULL"]
    if not include_non_specialty:
        where.append(SPECIALTY_FILTER)
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
        point_feature(
            row["longitude"],
            row["latitude"],
            {k: v for k, v in row.items() if k not in ("longitude", "latitude")},
        )
        for row in rows
    ]
    return feature_collection(features)


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
                WHERE latitude IS NOT NULL AND is_specialty
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
    return fetchone_or_404(
        db.execute(f"SELECT {SHOP_PUBLIC_COLS} FROM shop_shops WHERE id = ?", [shop_id]), "Shop"
    )


@router.get("/{shop_id}/products", response_model=list[ProductRead])
def get_shop_products(
    shop_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    """Products this shop serves (via the roaster it partners with)."""
    require_entity(db, "shop_shops", shop_id, "Shop")
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT {prefixed(PRODUCT_COLS, "p")}, r.name AS roaster_name
            FROM prod_products p
            JOIN edges_shop_product e ON e.product_id = p.id
            LEFT JOIN roast_roasters r ON p.roaster_id = r.id
            WHERE e.shop_id = ? ORDER BY p.name
            """,
            [shop_id],
        )
    )
