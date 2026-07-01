"""Allowed entity types for user activity, mapped to their DuckDB tables.

User activity (favorites, cupping notes) references content entities by an
opaque ``entity_type`` + ``entity_id`` pair (cross-database FKs are impossible:
content lives in DuckDB, activity in Postgres). At write time we validate the
``entity_id`` exists by resolving ``entity_type`` to its DuckDB table and
reusing ``require_entity``.

Resolving the type through these dicts is also what keeps the SQL safe: only a
known, hardcoded table name ever reaches ``require_entity``'s interpolation —
the client never controls the table string.

The keys here must match ``frontend/lib/entity-config.ts`` ``ENTITY_CONFIG``
keys so the account page can build detail-page hrefs from a favorite's
``entity_type`` with no remapping.
"""

from fastapi import HTTPException

from backend.db.entities import CONTENT_ENTITY_TABLES

# Any content entity can be favorited.
FAVORITE_ENTITY_TABLES = CONTENT_ENTITY_TABLES

# Cupping notes only make sense on something you brew/taste.
CUPPING_ENTITY_TABLES: dict[str, str] = {
    "product": "prod_products",
    "variety": "var_varieties",
}


def resolve_entity_table(allowed: dict[str, str], entity_type: str) -> str:
    """Return the DuckDB table for ``entity_type``, or raise 422 if unsupported."""
    table = allowed.get(entity_type)
    if table is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported entity_type '{entity_type}'. Allowed: {sorted(allowed)}",
        )
    return table
