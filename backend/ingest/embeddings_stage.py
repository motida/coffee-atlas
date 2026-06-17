"""Batch-embed text columns across all domain tables.

Scans each registered table for rows where the embedding column is NULL,
generates vectors via the Gemini embedding service, and writes them back.
Idempotent: re-running only processes rows that haven't been embedded yet.

DuckDB executes UPDATEs of ARRAY columns as delete+insert internally, so
embedding a row that an edge table references by foreign key raises a
constraint error. The write-back therefore snapshots the referencing edge
tables, clears them, applies the updates, and restores them in a
try/finally (see _fk_safe_write_back).

Targets marked embed_by_default=False (shop_shops, ~215K rows — far past
the Gemini free tier's daily request quota) only run when named
explicitly via `tables`.

Run with:  python -m backend.ingest.pipeline --stage embeddings
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from backend.ingest._common import managed_connection
from backend.services.embeddings import Embedder, EmbeddingService


@dataclass(frozen=True)
class EmbeddingTarget:
    table: str
    text_sql: str  # SQL expression that produces the text to embed
    embedding_col: str
    embed_by_default: bool = True  # False: only when named via `tables`


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
        table="prod_products",
        text_sql="name || ' — ' || COALESCE(description, '')",
        embedding_col="description_embedding",
    ),
    EmbeddingTarget(
        table="shop_shops",
        text_sql="name || ' — ' || COALESCE(description, '')",
        embedding_col="description_embedding",
        embed_by_default=False,  # ~215K rows; needs a deliberate, quota-aware run
    ),
]


def run_embeddings(
    conn: duckdb.DuckDBPyConnection | None = None,
    service: Embedder | None = None,
    tables: list[str] | None = None,
) -> dict[str, int]:
    """Embed the default targets in TARGETS, or just `tables` if given.

    Without `tables`, targets marked embed_by_default=False are skipped —
    shop_shops would blow the Gemini free-tier daily quota on its own.
    Naming a table in `tables` always includes it, default or not.
    Unknown names raise ValueError.

    Returns a dict of {table_name: rows_embedded}.
    Pass `conn` and `service` for testing (in-memory DB + fake embedder).
    """
    targets = [t for t in TARGETS if t.embed_by_default]
    if tables is not None:
        known = {t.table for t in TARGETS}
        unknown = sorted(set(tables) - known)
        if unknown:
            raise ValueError(
                f"Unknown embedding tables: {', '.join(unknown)} "
                f"(valid: {', '.join(sorted(known))})"
            )
        wanted = set(tables)
        targets = [t for t in TARGETS if t.table in wanted]

    if service is None:
        service = EmbeddingService()

    results: dict[str, int] = {}

    with managed_connection(conn=conn) as conn:
        for target in targets:
            count = _embed_table(conn, service, target)
            results[target.table] = count

    return results


def _embed_table(
    conn: duckdb.DuckDBPyConnection,
    service: Embedder,
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

    _fk_safe_write_back(conn, target, list(zip(ids, vectors)))
    return len(ids)


def _referencing_tables(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Tables holding a foreign key into `table` (e.g. its edge tables)."""
    rows = conn.execute(
        """
        SELECT DISTINCT table_name FROM duckdb_constraints()
        WHERE constraint_type = 'FOREIGN KEY'
          AND constraint_text LIKE '%REFERENCES ' || ? || '(%'
        """,
        [table],
    ).fetchall()
    return [r[0] for r in rows]


def _fk_safe_write_back(
    conn: duckdb.DuckDBPyConnection,
    target: EmbeddingTarget,
    id_vectors: list[tuple[str, list[float]]],
) -> None:
    """Write embeddings, working around DuckDB's FK limitation.

    Updating an ARRAY column rewrites the row as delete+insert, which fails
    while any edge row references it. Snapshot the referencing tables into
    temp tables, clear them, update, and restore. This cannot run as one
    transaction — DuckDB's over-eager FK checking still sees the deleted
    edge index entries until their delete commits — so the restore happens
    in a try/finally instead. If the process dies mid-write the temp
    snapshot is lost, but every edge table is rebuilt from source by its
    ingest stage (cqi / roasting / graph), so recovery is a stage re-run.
    """
    refs = _referencing_tables(conn, target.table)
    for ref in refs:
        conn.execute(f"CREATE TEMP TABLE _snapshot_{ref} AS SELECT * FROM {ref}")
        conn.execute(f"DELETE FROM {ref}")

    try:
        for row_id, vector in id_vectors:
            conn.execute(
                f"UPDATE {target.table} SET {target.embedding_col} = $1 WHERE id = $2",
                [vector, row_id],
            )
    finally:
        for ref in refs:
            conn.execute(f"INSERT INTO {ref} SELECT * FROM _snapshot_{ref}")
            conn.execute(f"DROP TABLE _snapshot_{ref}")
