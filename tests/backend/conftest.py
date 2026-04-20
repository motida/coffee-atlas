from collections.abc import Iterator

import pytest
import duckdb

from backend.db.schema import create_tables


@pytest.fixture
def db() -> Iterator[duckdb.DuckDBPyConnection]:
    """In-memory DuckDB connection with all tables created."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    yield conn
    conn.close()
