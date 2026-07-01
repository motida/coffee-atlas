"""Shared helpers for the API routers."""

from typing import Any

import duckdb
from fastapi import HTTPException

from backend.db.connection import fetchone_dict


def require_entity(db: duckdb.DuckDBPyConnection, table: str, entity_id: str, name: str) -> None:
    """Raise 404 unless ``table`` has a row with the given id.

    ``table`` is always a hardcoded constant supplied by the router, never user
    input, so interpolating it into the SQL is safe.
    """
    if not db.execute(f"SELECT 1 FROM {table} WHERE id = ?", [entity_id]).fetchone():
        raise HTTPException(status_code=404, detail=f"{name} not found")


def fetchone_or_404(cursor: duckdb.DuckDBPyConnection, name: str) -> dict[str, Any]:
    """Return the next row as a dict, or raise 404 if the query matched nothing.

    Collapses the ``row = fetchone_dict(...); if row is None: raise 404`` block
    that every entity-detail endpoint would otherwise repeat.
    """
    row = fetchone_dict(cursor)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return row
