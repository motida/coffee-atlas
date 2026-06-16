from typing import Any

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db.connection import fetchall_dicts, get_db
from backend.models.flavor import FlavorAttributeRead
from backend.models.products import ProductRead
from backend.models.varieties import VarietyRead

router = APIRouter(prefix="/api/v1/products", tags=["products"])

# Product columns excluding the embedding vector, aliased to p for the join.
_PRODUCT_COLS = (
    "id, name, roaster_id, roast_level, process, is_blend, price, "
    "net_weight_grams, url, description, created_at, updated_at"
)
_VARIETY_COLS = (
    "id, name, species, genetic_group, description, yield_potential, "
    "optimal_altitude_min, optimal_altitude_max, bean_size, cherry_color, "
    "stature, disease_resistance, created_at, updated_at"
)
_FLAVOR_COLS = (
    "id, name, category, subcategory, description, "
    "intensity_reference, sensory_reference, parent_id, created_at, updated_at"
)

_SELECT = (
    f"SELECT {', '.join(f'p.{c}' for c in _PRODUCT_COLS.split(', '))}, r.name AS roaster_name "
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
    row = db.execute(f"{_SELECT} WHERE p.id = ?", [product_id]).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))


def _require_product(db: duckdb.DuckDBPyConnection, product_id: str) -> None:
    if not db.execute("SELECT 1 FROM prod_products WHERE id = ?", [product_id]).fetchone():
        raise HTTPException(status_code=404, detail="Product not found")


@router.get("/{product_id}/varieties", response_model=list[VarietyRead])
def get_product_varieties(
    product_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    """Varieties this product consists of (single-origin: one; blend: several)."""
    _require_product(db, product_id)
    cols = ", ".join(f"v.{c}" for c in _VARIETY_COLS.split(", "))
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT {cols} FROM var_varieties v
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
    _require_product(db, product_id)
    cols = ", ".join(f"f.{c}" for c in _FLAVOR_COLS.split(", "))
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT {cols} FROM flav_attributes f
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
    _require_product(db, product_id)
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
