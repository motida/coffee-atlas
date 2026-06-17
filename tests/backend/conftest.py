from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import duckdb
import pytest

from backend.db.schema import create_tables

# Tables truncated between tests, children first (FKs cascade from usr_users).
_PG_CLEAN_TABLES = "usr_cupping_notes, usr_favorites, usr_users"


@pytest.fixture
def db() -> Iterator[duckdb.DuckDBPyConnection]:
    """In-memory DuckDB connection with all content tables created."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    yield conn
    conn.close()


def _normalize_pg_url(url: str) -> str:
    """Strip any SQLAlchemy-style driver suffix so psycopg accepts the URL."""
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql://", 1)
    return url


def _resolve_database_url() -> tuple[str | None, Any]:
    """Find a Postgres for the user-data tests.

    Priority: an explicit ``DATABASE_URL`` (e.g. a CI ``services: postgres``),
    else a throwaway ``testcontainers`` container (needs Docker). Returns
    ``(url, container)`` — both ``None`` when no Postgres is reachable, so the
    user-data tests skip and the DuckDB suite still runs.
    """
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return _normalize_pg_url(env_url), None
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:16")
        container.start()
    except Exception:
        return None, None
    return _normalize_pg_url(container.get_connection_url()), container


@pytest.fixture(scope="session")
def pg_pool():
    """Session-scoped psycopg pool against a real Postgres, with tables created.

    Skips the whole user-data suite when no Postgres is reachable.
    """
    url, container = _resolve_database_url()
    if url is None:
        pytest.skip("No Postgres available (set DATABASE_URL or run Docker for testcontainers)")

    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    from backend.db.pg_schema import create_pg_tables

    pool = ConnectionPool(url, min_size=1, max_size=5, kwargs={"row_factory": dict_row}, open=True)
    with pool.connection() as conn:
        create_pg_tables(conn)
    try:
        yield pool
    finally:
        pool.close()
        if container is not None:
            container.stop()


@pytest.fixture
def pg(pg_pool):
    """A committed connection for direct seeding/inspection.

    Truncates the ``usr_*`` tables on teardown so each test starts clean — this
    is the per-test isolation boundary for everything written via the API too.
    """
    with pg_pool.connection() as conn:
        yield conn
    with pg_pool.connection() as cleanup:
        with cleanup.cursor() as cur:
            cur.execute(f"TRUNCATE {_PG_CLEAN_TABLES} CASCADE")
        cleanup.commit()
