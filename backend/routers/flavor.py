"""Flavor domain endpoints: the WCR sensory-lexicon wheel and attribute detail."""

from typing import Any

import duckdb
from fastapi import APIRouter, Depends

from backend.db.columns import FLAVOR_COLS
from backend.db.connection import fetchall_dicts, get_db
from backend.models.flavor import FlavorAttributeRead
from backend.routers._helpers import fetchone_or_404

router = APIRouter(prefix="/api/v1/flavor", tags=["flavor"])


@router.get("/wheel")
def get_flavor_wheel(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    """Return the full flavor wheel as a hierarchical JSON tree."""
    rows = fetchall_dicts(
        db.execute(
            f"SELECT {FLAVOR_COLS} FROM flav_attributes ORDER BY category, subcategory, name"
        )
    )
    tree: dict[str, Any] = {}
    for row in rows:
        cat = row.get("category") or "Other"
        sub = row.get("subcategory") or "Other"
        tree.setdefault(cat, {}).setdefault(sub, []).append(row)
    return tree


@router.get("/attributes/{attribute_id}", response_model=FlavorAttributeRead)
def get_flavor_attribute(
    attribute_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> dict[str, Any]:
    return fetchone_or_404(
        db.execute("SELECT * FROM flav_attributes WHERE id = ?", [attribute_id]),
        "Flavor attribute",
    )
