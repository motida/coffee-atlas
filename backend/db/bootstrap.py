"""Idempotent DB bootstrap.

Run with: `python -m backend.db.bootstrap`

Steps performed:
  1. Open the configured DuckDB file (creates it if missing).
  2. Run `CREATE TABLE IF NOT EXISTS` for every table in the schema.
  3. If `ontology_triples` is empty, parse the .ttl files and populate it.

Designed to run on container startup so a fresh deploy always has a usable
schema and ontology triples present, without overwriting existing data.
"""

from __future__ import annotations

import duckdb

from backend.db.connection import get_connection
from backend.db.schema import create_tables


def _is_empty(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return row[0] == 0


def bootstrap(conn: duckdb.DuckDBPyConnection | None = None) -> None:
    """Create tables and seed ontology triples if missing."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        create_tables(conn)
        print("Bootstrap: schema ensured")

        if _is_empty(conn, "ontology_triples"):
            from ontology.scripts.export_triples import export

            n = export(conn=conn)
            print(f"Bootstrap: wrote {n} ontology triples")
        else:
            row = conn.execute("SELECT COUNT(*) FROM ontology_triples").fetchone()
            assert row is not None
            print(f"Bootstrap: ontology_triples already populated ({row[0]} rows), skipping")
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    bootstrap()
