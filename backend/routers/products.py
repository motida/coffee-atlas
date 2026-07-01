"""Product domain endpoints: roaster catalogs and each product's varieties,
flavors, and named origins."""

from typing import Any

import duckdb
from fastapi import APIRouter, Depends, Query

from backend.db.columns import FLAVOR_COLS, PRODUCT_COLS, VARIETY_COLS, prefixed
from backend.db.connection import fetchall_dicts, get_db
from backend.models.flavor import FlavorAttributeRead
from backend.models.products import ProductRead
from backend.models.varieties import VarietyRead
from backend.routers._helpers import fetchone_or_404, require_entity

router = APIRouter(prefix="/api/v1/products", tags=["products"])

# Product flavor rows are serialized as FlavorAttributeRead, which carries the
# audit timestamps the bare FLAVOR_COLS list omits.
_FLAVOR_COLS = f"{FLAVOR_COLS}, created_at, updated_at"

_SELECT = (
    f"SELECT {prefixed(PRODUCT_COLS, 'p')}, r.name AS roaster_name "
    "FROM prod_products p LEFT JOIN roast_roasters r ON p.roaster_id = r.id"
)


@router.get("", response_model=list[ProductRead])
def list_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    roaster_id: str | None = Query(None),
    is_blend: bool | None = Query(None),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if roaster_id is not None:
        where.append("p.roaster_id = ?")
        params.append(roaster_id)
    if is_blend is not None:
        where.append("p.is_blend = ?")
        params.append(is_blend)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    params.extend([limit, offset])
    return fetchall_dicts(db.execute(f"{_SELECT}{clause} ORDER BY p.name LIMIT ? OFFSET ?", params))


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    return fetchone_or_404(db.execute(f"{_SELECT} WHERE p.id = ?", [product_id]), "Product")


@router.get("/{product_id}/varieties", response_model=list[VarietyRead])
def get_product_varieties(
    product_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    """Varieties this product consists of (single-origin: one; blend: several)."""
    require_entity(db, "prod_products", product_id, "Product")
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT {prefixed(VARIETY_COLS, "v")} FROM var_varieties v
            JOIN edges_product_variety e ON e.variety_id = v.id
            WHERE e.product_id = ? ORDER BY v.name
            """,
            [product_id],
        )
    )


@router.get("/{product_id}/flavors", response_model=list[FlavorAttributeRead])
def get_product_flavors(
    product_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    """Flavor attributes the product's tasting notes mention."""
    require_entity(db, "prod_products", product_id, "Product")
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT {prefixed(_FLAVOR_COLS, "f")} FROM flav_attributes f
            JOIN edges_product_flavor e ON e.flavor_id = f.id
            WHERE e.product_id = ? ORDER BY f.name
            """,
            [product_id],
        )
    )


@router.get("/{product_id}/origin")
def get_product_origin(
    product_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> dict[str, list[dict[str, Any]]]:
    """Origin countries and regions named by the product."""
    require_entity(db, "prod_products", product_id, "Product")
    countries = fetchall_dicts(
        db.execute(
            """
            SELECT c.id, c.name FROM org_countries c
            JOIN edges_product_country e ON e.country_id = c.id
            WHERE e.product_id = ? ORDER BY c.name
            """,
            [product_id],
        )
    )
    regions = fetchall_dicts(
        db.execute(
            """
            SELECT rg.id, rg.name FROM org_regions rg
            JOIN edges_product_region e ON e.region_id = rg.id
            WHERE e.product_id = ? ORDER BY rg.name
            """,
            [product_id],
        )
    )
    return {"countries": countries, "regions": regions}
