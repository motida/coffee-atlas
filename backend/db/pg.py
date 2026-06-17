"""Postgres connection manager for the user-data store.

Mirrors ``connection.py``'s dependency shape, but for the second store. DuckDB
holds the read-only content graph; Postgres holds everything user-owned
(accounts, favorites, cupping notes) because the hosted content DuckDB ships
read-only into an ephemeral Space and cannot accept request-time writes.

Uses psycopg 3 (sync) with a connection pool and ``dict_row`` so cursors
return column→value dicts — the same materialization shape DuckDB routers get
from ``fetchall_dicts``.
"""

from collections.abc import Generator
from typing import cast

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from backend.config import settings

_pool: ConnectionPool | None = None


def init_pool() -> ConnectionPool:
    """Open (once) and return the module-global connection pool.

    ``max_size`` is intentionally small: free Postgres tiers cap connections,
    and on Neon the ``-pooler`` host should be preferred in ``DATABASE_URL``.
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings.DATABASE_URL,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool() -> None:
    """Close the pool (called on app shutdown)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pg() -> Generator[psycopg.Connection[DictRow], None, None]:
    """FastAPI dependency that yields a pooled Postgres connection.

    The ``with conn`` block commits on clean exit and rolls back if the route
    raises, then returns the connection to the pool. The connection is created
    with ``dict_row`` at runtime, so it is cast to ``Connection[DictRow]`` (the
    pool can't carry the row-factory type statically) — cursors then yield dicts.
    """
    if _pool is None:
        raise RuntimeError("Postgres pool not initialized — is DATABASE_URL set?")
    with _pool.connection() as conn:
        yield cast("psycopg.Connection[DictRow]", conn)
