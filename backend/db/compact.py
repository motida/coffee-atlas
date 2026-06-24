"""Build a compacted, deploy-ready copy of the content DuckDB.

The content DB accumulates two kinds of weight DuckDB never reclaims on its own:

1. the full Overture POI dump in ``shop_shops`` — ~210k rows, of which only the
   ~2% flagged ``is_specialty`` are ever served (the discovery endpoints filter to
   it), and
2. free / tombstoned blocks left behind by re-running ingest stages (DuckDB's
   single file only ever grows to its high-water mark; a plain CHECKPOINT does
   not shrink it).

This module rebuilds the database into a fresh file via ``CREATE TABLE AS
SELECT`` — dropping non-specialty shops (and the edge rows that reference them)
and writing every table sequentially, which reclaims all free space. It is run at
deploy time (``deploy/huggingface/deploy.sh``) so the *local* DB keeps the full
POI set (re-tune the specialty heuristic, re-run stages) while the Space ships
only the lean served subset. CTAS omits PK/FK constraints, which carry no runtime
value for the read-only content store.

The source DB is opened READ-ONLY and never modified.

Usage:
    python -m backend.db.compact <source.duckdb> <out.duckdb>
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import duckdb

SHOP_TABLE = "shop_shops"
SPECIALTY_PRED = "is_specialty IS TRUE"


@dataclass
class CompactStats:
    src_bytes: int
    out_bytes: int
    tables: int
    shops_before: int
    shops_after: int

    @property
    def pct_smaller(self) -> float:
        return 100 * (1 - self.out_bytes / self.src_bytes) if self.src_bytes else 0.0


def _scalar(conn: duckdb.DuckDBPyConnection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    assert row is not None
    return row[0]


def _main_tables(conn: duckdb.DuckDBPyConnection, catalog: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema='main' AND table_catalog='{catalog}' ORDER BY table_name"
        ).fetchall()
    ]


def compact_database(src_path: str, out_path: str) -> CompactStats:
    """Rebuild ``src_path`` into a fresh, pruned, compacted ``out_path``.

    Non-specialty shops and the edge rows pointing at them are dropped; every
    other table round-trips unchanged. Raises if an integrity check fails or if
    the prune would leave zero shops (a sign the specialty stage never ran).
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(src_path)
    for f in (out_path, out_path + ".wal"):
        if os.path.exists(f):
            os.remove(f)

    conn = duckdb.connect(out_path)
    try:
        conn.execute(f"ATTACH '{src_path}' AS src (READ_ONLY)")
        tables = _main_tables(conn, "src")
        has_shops = SHOP_TABLE in tables

        shops_before = shops_after = 0
        shop_fk_tables: set[str] = set()
        if has_shops:
            shops_before = _scalar(conn, f"SELECT count(*) FROM src.{SHOP_TABLE}")
            # Any table with a shop_id column references a shop; filter it to kept shops.
            shop_fk_tables = {
                r[0]
                for r in conn.execute(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_catalog='src' AND table_schema='main' AND column_name='shop_id'"
                ).fetchall()
            }

        kept = f"(SELECT id FROM src.{SHOP_TABLE} WHERE {SPECIALTY_PRED})"
        for t in tables:
            if has_shops and t == SHOP_TABLE:
                sql = f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}" WHERE {SPECIALTY_PRED}'
            elif t in shop_fk_tables:
                sql = (
                    f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}" '
                    f"WHERE shop_id IS NULL OR shop_id IN {kept}"
                )
            else:
                sql = f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"'
            conn.execute(sql)
        conn.execute("CHECKPOINT")

        if has_shops:
            shops_after = _scalar(conn, f"SELECT count(*) FROM {SHOP_TABLE}")
            if shops_before > 0 and shops_after == 0:
                raise RuntimeError(
                    "compaction would drop every shop — is_specialty is unset; "
                    "run the `specialty` ingest stage before deploying"
                )

        # Integrity: every table not subject to the prune must round-trip exactly.
        for t in tables:
            if t == SHOP_TABLE or t in shop_fk_tables:
                continue
            s = _scalar(conn, f'SELECT count(*) FROM src."{t}"')
            d = _scalar(conn, f'SELECT count(*) FROM "{t}"')
            if s != d:
                raise RuntimeError(f"row-count mismatch on {t}: src={s}, out={d}")

        conn.execute("DETACH src")
    finally:
        conn.close()

    return CompactStats(
        src_bytes=os.path.getsize(src_path),
        out_bytes=os.path.getsize(out_path),
        tables=len(tables),
        shops_before=shops_before,
        shops_after=shops_after,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("usage: python -m backend.db.compact <source.duckdb> <out.duckdb>", file=sys.stderr)
        sys.exit(2)

    stats = compact_database(sys.argv[1], sys.argv[2])
    print(
        f"Compacted {stats.src_bytes / 1024 / 1024:.1f} MiB -> "
        f"{stats.out_bytes / 1024 / 1024:.1f} MiB ({stats.pct_smaller:.0f}% smaller); "
        f"shops {stats.shops_before:,} -> {stats.shops_after:,}; {stats.tables} tables"
    )
