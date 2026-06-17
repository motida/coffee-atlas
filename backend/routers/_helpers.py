"""Shared helpers for the API routers."""

import duckdb
from fastapi import HTTPException


def require_entity(db: duckdb.DuckDBPyConnection, table: str, entity_id: str, name: str) -> None:
    """Raise 404 unless ``table`` has a row with the given id.

    ``table`` is always a hardcoded constant supplied by the router, never user
    input, so interpolating it into the SQL is safe.
    """
    if not db.execute(f"SELECT 1 FROM {table} WHERE id = ?", [entity_id]).fetchone():
        raise HTTPException(status_code=404, detail=f"{name} not found")
