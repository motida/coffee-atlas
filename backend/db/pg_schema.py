"""DDL for the Postgres user-data tables. Parallels ``backend/db/schema.py``.

All user-owned data lives here (not DuckDB): accounts, saved favorites, and
cupping notes. Tables use the ``usr_`` prefix and Python-side ``str(uuid4())``
ids, uniform with how the DuckDB loaders mint ids.

Caveat: these idempotent ``CREATE TABLE IF NOT EXISTS`` statements can create
tables but cannot *evolve* columns of live user data. V1 ships this way to
match the project's no-migration convention; the first schema change that has
to touch existing user rows is the trigger to adopt a migration tool (Alembic).
"""

from typing import LiteralString

import psycopg

PG_TABLES: list[LiteralString] = [
    """
    CREATE TABLE IF NOT EXISTS usr_users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    # Case-insensitive email uniqueness (lookups also key on LOWER(email)).
    "CREATE UNIQUE INDEX IF NOT EXISTS usr_users_email_lower_idx ON usr_users (LOWER(email))",
    """
    CREATE TABLE IF NOT EXISTS usr_favorites (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES usr_users(id) ON DELETE CASCADE,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, entity_type, entity_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS usr_favorites_user_idx ON usr_favorites (user_id)",
    """
    CREATE TABLE IF NOT EXISTS usr_cupping_notes (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES usr_users(id) ON DELETE CASCADE,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        score DOUBLE PRECISION,
        notes TEXT NOT NULL,
        brew_method TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS usr_cupping_notes_user_idx ON usr_cupping_notes (user_id)",
]


def create_pg_tables(conn: psycopg.Connection) -> None:
    """Create all user-data tables (idempotent)."""
    with conn.cursor() as cur:
        for ddl in PG_TABLES:
            cur.execute(ddl)
    conn.commit()
