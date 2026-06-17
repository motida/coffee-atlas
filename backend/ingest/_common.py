"""Shared building blocks for the ingest loaders.

Every loader stage owns-or-borrows a DuckDB connection, derives stable UUIDs
from natural keys, and normalizes free text the same way; these helpers keep
those mechanics in one place instead of being copy-pasted per stage.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import duckdb

from backend.db.connection import get_connection


@contextmanager
def managed_connection(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield a DuckDB connection, closing it only if we opened it.

    Pass an existing ``conn`` (e.g. an in-memory test DB) and it is borrowed and
    left open; otherwise a new connection is opened from ``db_path`` (or the
    configured default) and closed on exit.
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)
    try:
        yield conn
    finally:
        if owns_conn:
            conn.close()


def uuid_slug(*parts: str) -> str:
    """Join key parts into the normalized slug used for deterministic UUIDs."""
    return ":".join(p.strip().lower() for p in parts if p)


def deterministic_uuid(namespace: uuid.UUID, *parts: str) -> str:
    """A stable UUID5 over ``parts`` within ``namespace`` (returned as text)."""
    return str(uuid.uuid5(namespace, uuid_slug(*parts)))


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces and trim the ends."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_dedup(name: str) -> str:
    """Whitespace-normalized, case-folded key for case-insensitive matching."""
    return normalize_whitespace(name).casefold()
