"""DuckDB connection manager with extension loading."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

import duckdb

from backend.config import settings


def get_connection() -> duckdb.DuckDBPyConnection:
    """Create a new DuckDB connection to the configured database path."""
    db_path = Path(settings.DUCKDB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    _load_extensions(conn)
    return conn


def get_memory_connection() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB connection (for testing)."""
    conn = duckdb.connect(":memory:")
    _load_extensions(conn)
    return conn


def _load_extensions(conn: duckdb.DuckDBPyConnection) -> None:
    """Install and load DuckDB extensions (VSS, PGQ)."""
    for ext in ("vss", "pgq"):
        try:
            conn.execute(f"INSTALL {ext}")
            conn.execute(f"LOAD {ext}")
        except Exception:
            pass  # Extension may not be available in all environments


def get_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """FastAPI dependency that yields a DuckDB connection."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def fetchall_dicts(cursor: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Materialize a SELECT result as a list of column→value dicts."""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
