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


# INSTALL outcome, attempted once per process: None = not yet tried. INSTALL
# hits the filesystem (and the extension repo on a cold cache), so retrying it
# on every request-scoped connection added a doomed network round-trip per
# request — previously made worse by also trying "pgq", which isn't the
# extension's name (it's "duckpgq", parked: the community build crashes on
# DuckDB 1.5.1; graph endpoints BFS the edge tables instead).
_vss_installed: bool | None = None


def _load_extensions(conn: duckdb.DuckDBPyConnection) -> None:
    """Load the VSS extension: INSTALL once per process, LOAD per connection.

    VSS is optional today — semantic search uses the built-in
    array_cosine_similarity; the extension is only needed once HNSW indexing
    lands — so every failure is non-fatal.
    """
    global _vss_installed
    if _vss_installed is None:
        try:
            conn.execute("INSTALL vss")
            _vss_installed = True
        except Exception:
            _vss_installed = False
    if _vss_installed:
        try:
            conn.execute("LOAD vss")  # per-connection, local, no network
        except Exception:
            pass


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


def fetchone_dict(cursor: duckdb.DuckDBPyConnection) -> dict[str, Any] | None:
    """Materialize the next SELECT row as a column→value dict, or None if empty."""
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))
