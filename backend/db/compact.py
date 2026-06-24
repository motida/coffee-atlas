"""Build a compacted, deploy-ready copy of the content DuckDB.

The content DB accumulates two kinds of weight DuckDB never reclaims on its own:

1. the full Overture POI dump in ``shop_shops`` — ~210k rows, of which only the
   ~2% flagged ``is_specialty`` are ever served (the discovery endpoints filter to
   it), and
2. free / tombstoned blocks left behind by re-running ingest stages (DuckDB's
   single file only ever grows to its high-water mark; a plain CHECKPOINT does
   not shrink it).

This module rebuilds the database into a fresh file: it recreates the real
schema with :func:`create_tables` (so PK/FK constraints are preserved), then
copies every table's rows in FK-dependency order — dropping non-specialty shops
and the edges that reference them. Writing into a brand-new file reclaims all
free space.

Preserving the constraints is **required**, not cosmetic: the API container runs
``backend.db.bootstrap`` at startup, which calls ``create_tables`` (CREATE TABLE
IF NOT EXISTS) against the shipped DB. If a referenced table has lost its primary
key, recreating any table whose FK points at it fails and the container crashes
(``Failed to create foreign key: there is no primary key ... for ... org_countries``).
The final self-check here re-runs ``create_tables`` to guarantee the artifact
survives that path before it ever ships.

The source DB is opened READ-ONLY and never modified. Run at deploy time
(``deploy/huggingface/deploy.sh``) so the local DB keeps the full POI set while
the Space ships only the lean served subset.

Usage:
    python -m backend.db.compact <source.duckdb> <out.duckdb>
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import duckdb

from backend.db.schema import create_tables

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


def _tables(conn: duckdb.DuckDBPyConnection, catalog: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema='main' AND table_catalog='{catalog}' ORDER BY table_name"
        ).fetchall()
    ]


def _columns(conn: duckdb.DuckDBPyConnection, catalog: str, table: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_catalog='{catalog}' AND table_schema='main' AND table_name=? "
            "ORDER BY ordinal_position",
            [table],
        ).fetchall()
    ]


def _fk_load_order(conn: duckdb.DuckDBPyConnection, catalog: str, tables: list[str]) -> list[str]:
    """Topologically sort ``tables`` so a table's FK parents load first.

    Built from the compacted schema's own FK constraints (those are what get
    enforced during INSERT). The graph is acyclic with no self-references, so a
    full order always exists.
    """
    deps: dict[str, set[str]] = {t: set() for t in tables}
    for child, parent in conn.execute(
        "SELECT DISTINCT table_name, referenced_table FROM duckdb_constraints() "
        f"WHERE constraint_type='FOREIGN KEY' AND database_name='{catalog}' "
        "AND table_name <> referenced_table"
    ).fetchall():
        if child in deps and parent in deps:
            deps[child].add(parent)

    order, done = [], set()
    while len(done) < len(tables):
        ready = sorted(t for t in tables if t not in done and deps[t] <= done)
        if not ready:
            raise RuntimeError(f"FK cycle among {set(tables) - done}")
        order += ready
        done.update(ready)
    return order


def compact_database(src_path: str, out_path: str) -> CompactStats:
    """Rebuild ``src_path`` into a fresh, pruned, compacted ``out_path``.

    Non-specialty shops and the edge rows pointing at them are dropped; every
    other table round-trips unchanged with its PK/FK constraints intact. Raises
    if an integrity check fails, if the prune would leave zero shops (the
    specialty stage never ran), or if the artifact would fail bootstrap's
    ``create_tables`` step.
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(src_path)
    for f in (out_path, out_path + ".wal"):
        if os.path.exists(f):
            os.remove(f)

    conn = duckdb.connect(out_path)
    try:
        cat_row = conn.execute("SELECT current_database()").fetchone()
        assert cat_row is not None
        out_cat = cat_row[0]
        create_tables(conn)  # full schema with PK/FK constraints, before attaching src
        schema_tables = _tables(conn, out_cat)

        conn.execute(f"ATTACH '{src_path}' AS src (READ_ONLY)")
        src_tables = _tables(conn, "src")
        has_shops = SHOP_TABLE in src_tables

        shops_before = shops_after = 0
        shop_fk_tables: set[str] = set()
        if has_shops:
            shops_before = _scalar(conn, f"SELECT count(*) FROM src.{SHOP_TABLE}")
            shop_fk_tables = {
                r[0]
                for r in conn.execute(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_catalog='src' AND table_schema='main' AND column_name='shop_id'"
                ).fetchall()
            }
        kept = f"(SELECT id FROM src.{SHOP_TABLE} WHERE {SPECIALTY_PRED})"

        # Load schema tables in FK order, then any source-only auxiliary tables.
        load_order = _fk_load_order(conn, out_cat, schema_tables)
        load_order += [t for t in src_tables if t not in schema_tables]

        for t in load_order:
            if t not in src_tables:
                continue  # schema-only table (drift): create_tables already made it empty
            if t not in schema_tables:
                conn.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
                continue
            # Match columns by name (the bundled DB's column order has drifted
            # from schema.py, so positional INSERT is unsafe).
            cols = [c for c in _columns(conn, out_cat, t) if c in set(_columns(conn, "src", t))]
            collist = ", ".join(f'"{c}"' for c in cols)
            where = ""
            if has_shops and t == SHOP_TABLE:
                where = f"WHERE {SPECIALTY_PRED}"
            elif t in shop_fk_tables:
                where = f"WHERE shop_id IS NULL OR shop_id IN {kept}"
            conn.execute(f'INSERT INTO "{t}" ({collist}) SELECT {collist} FROM src."{t}" {where}')

        if has_shops:
            shops_after = _scalar(conn, f"SELECT count(*) FROM {SHOP_TABLE}")
            if shops_before > 0 and shops_after == 0:
                raise RuntimeError(
                    "compaction would drop every shop — is_specialty is unset; "
                    "run the `specialty` ingest stage before deploying"
                )

        # Integrity: every table not subject to the prune round-trips exactly.
        for t in src_tables:
            if t == SHOP_TABLE or t in shop_fk_tables or t not in schema_tables:
                continue
            s = _scalar(conn, f'SELECT count(*) FROM src."{t}"')
            d = _scalar(conn, f'SELECT count(*) FROM "{t}"')
            if s != d:
                raise RuntimeError(f"row-count mismatch on {t}: src={s}, out={d}")

        conn.execute("DETACH src")
        # Self-check: re-run the exact bootstrap step against the artifact.
        create_tables(conn)
        conn.execute("CHECKPOINT")
    finally:
        conn.close()

    return CompactStats(
        src_bytes=os.path.getsize(src_path),
        out_bytes=os.path.getsize(out_path),
        tables=len(schema_tables),
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
