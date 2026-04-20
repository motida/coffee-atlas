"""Batch-embed text columns across all domain tables.

Scans each registered table for rows where the embedding column is NULL,
generates vectors via the Gemini embedding service, and writes them back.
Idempotent: re-running only processes rows that haven't been embedded yet.

Run with:  python -m backend.ingest.pipeline --stage embeddings
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from backend.db.connection import get_connection
from backend.services.embeddings import EmbeddingService


@dataclass(frozen=True)
class EmbeddingTarget:
    table: str
    text_sql: str  # SQL expression that produces the text to embed
    embedding_col: str


TARGETS: list[EmbeddingTarget] = [
    EmbeddingTarget(
        table="flav_attributes",
        text_sql="name || ' — ' || COALESCE(description, '')",
        embedding_col="name_embedding",
    ),
    EmbeddingTarget(
        table="var_varieties",
        text_sql="name || ' — ' || COALESCE(description, '')",
        embedding_col="name_embedding",
    ),
    EmbeddingTarget(
        table="proc_methods",
        text_sql="name || ' — ' || COALESCE(description, '')",
        embedding_col="description_embedding",
    ),
    EmbeddingTarget(
        table="roast_profiles",
        text_sql="name || ' — ' || COALESCE(description, '')",
        embedding_col="description_embedding",
    ),
    EmbeddingTarget(
        table="shop_shops",
        text_sql="name || ' — ' || COALESCE(description, '')",
        embedding_col="description_embedding",
    ),
]


def run_embeddings(
    conn: duckdb.DuckDBPyConnection | None = None,
    service: EmbeddingService | None = None,
) -> dict[str, int]:
    """Embed all tables registered in TARGETS.

    Returns a dict of {table_name: rows_embedded}.
    Pass `conn` and `service` for testing (in-memory DB + fake embedder).
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    if service is None:
        service = EmbeddingService()

    results: dict[str, int] = {}

    try:
        for target in TARGETS:
            count = _embed_table(conn, service, target)
            results[target.table] = count
    finally:
        if owns_conn:
            conn.close()

    return results


def _embed_table(
    conn: duckdb.DuckDBPyConnection,
    service: EmbeddingService,
    target: EmbeddingTarget,
) -> int:
    """Embed un-embedded rows for a single table. Returns rows processed."""
    rows = conn.execute(
        f"""
        SELECT id, {target.text_sql} AS text
        FROM {target.table}
        WHERE {target.embedding_col} IS NULL
        ORDER BY id
        """
    ).fetchall()

    if not rows:
        return 0

    ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    vectors = service.embed_batch(texts)

    for row_id, vector in zip(ids, vectors):
        conn.execute(
            f"UPDATE {target.table} SET {target.embedding_col} = $1 WHERE id = $2",
            [vector, row_id],
        )

    return len(ids)
