"""Processing domain endpoints: methods and the entities they connect.

Processing methods are seeded from the CQI cupping data (washed, natural,
honey, …) and connect to two neighbours in the graph:

* varieties prepared with the method (``edges_variety_processing``), and
* flavor attributes the method enhances or diminishes
  (``edges_processing_flavor``).
"""

from typing import Any

import duckdb
from fastapi import APIRouter, Depends, Query

from backend.db.columns import FLAVOR_COLS, VARIETY_COLS, prefixed
from backend.db.connection import fetchall_dicts, get_db
from backend.models.processing import ProcessingMethodRead
from backend.models.varieties import VarietyRead
from backend.routers._helpers import fetchone_or_404, require_entity

router = APIRouter(prefix="/api/v1/processing", tags=["processing"])

# Explicit column list: never ship the 3072-float embedding columns to clients.
_METHOD_COLS = (
    "id, name, category, description, "
    "fermentation_duration, drying_duration, created_at, updated_at"
)


@router.get("/methods", response_model=list[ProcessingMethodRead])
def list_methods(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: str | None = Query(None, description="Filter by category, e.g. washed or natural"),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if category is not None:
        where = "WHERE LOWER(category) = LOWER(?)"
        params.append(category)
    params.extend([limit, offset])
    return fetchall_dicts(
        db.execute(
            f"SELECT {_METHOD_COLS} FROM proc_methods {where} ORDER BY name LIMIT ? OFFSET ?",
            params,
        )
    )


@router.get("/methods/{method_id}", response_model=ProcessingMethodRead)
def get_method(method_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    return fetchone_or_404(
        db.execute(f"SELECT {_METHOD_COLS} FROM proc_methods WHERE id = ?", [method_id]),
        "Processing method",
    )


@router.get("/methods/{method_id}/varieties", response_model=list[VarietyRead])
def get_method_varieties(
    method_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    """Varieties observed prepared with this processing method."""
    require_entity(db, "proc_methods", method_id, "Processing method")
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT {prefixed(VARIETY_COLS, "v")}
            FROM var_varieties v
            JOIN edges_variety_processing e ON e.variety_id = v.id
            WHERE e.method_id = ?
            ORDER BY v.name
            """,
            [method_id],
        )
    )


@router.get("/methods/{method_id}/flavor")
def get_method_flavor(
    method_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> list[dict[str, Any]]:
    """Flavor attributes this method enhances or diminishes."""
    require_entity(db, "proc_methods", method_id, "Processing method")
    return fetchall_dicts(
        db.execute(
            f"""
            SELECT {prefixed(FLAVOR_COLS, "f")}, e.effect
            FROM flav_attributes f
            JOIN edges_processing_flavor e ON e.flavor_id = f.id
            WHERE e.method_id = ?
            ORDER BY f.name
            """,
            [method_id],
        )
    )
