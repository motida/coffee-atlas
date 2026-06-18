"""Compute the specialty flag for coffee shops.

Overture gives us *every* coffee POI; this stage decides which ones are
"specialty" and materializes `shop_shops.is_specialty` (+ a `specialty_score`)
so the API can filter cheaply.

The signal is a multi-source heuristic over the data we actually populate
(rating/roasts_in_house are usually NULL — see overture_shops_loader):

  is_specialty =
      specialty_chain                          -- allowlist override → always true
      OR (NOT nonspecialty_chain AND score >= SPECIALTY_THRESHOLD)

  score = curated-roaster match (edges_shop_roaster) ........ 0.6
        + scraper-vetted coffee description ................. 0.3
        + roasts in house (when known) ..................... 0.2
        + rating >= RATING_THRESHOLD (when known) .......... 0.2
        + has its own website .............................. 0.1   (weak; not enough alone)

A non-specialty chain is forced to score 0. The threshold (0.2) is set so any
single *meaningful* signal qualifies while a bare website does not. Tune the
weights/threshold below.

Runs after the graph stage (it reads `edges_shop_roaster`). Robust to that
table being empty (local bootstrap without products) and to shop_shops being
empty (no-op).
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from backend.ingest._common import managed_connection
from backend.ingest.shop_scrapers.chains import is_nonspecialty_chain, is_specialty_chain

# --- Tunable heuristic ---
WEIGHT_CURATED_ROASTER = 0.6
WEIGHT_DESCRIPTION = 0.3
WEIGHT_ROASTS_IN_HOUSE = 0.2
WEIGHT_RATING = 0.2
WEIGHT_WEBSITE = 0.1
RATING_THRESHOLD = 4.0
SPECIALTY_THRESHOLD = 0.2


@dataclass(frozen=True)
class SpecialtyCounts:
    total: int
    specialty: int


def _ensure_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add the specialty columns if an older DB predates them.

    Fresh DBs already have them (see schema.py). We only ALTER when genuinely
    missing — DuckDB refuses to ALTER a table other tables FK-reference (which
    shop_shops is), so attempting the ALTER unconditionally would error even
    when the column exists.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info('shop_shops')").fetchall()}
    if "specialty_score" not in existing:
        conn.execute("ALTER TABLE shop_shops ADD COLUMN specialty_score DOUBLE")
    if "is_specialty" not in existing:
        conn.execute("ALTER TABLE shop_shops ADD COLUMN is_specialty BOOLEAN DEFAULT FALSE")


def _classify_chains(conn: duckdb.DuckDBPyConnection) -> None:
    """Materialize a temp table of per-shop chain flags.

    Chain matching is normalized/prefix-aware Python (see chains.py) — too
    awkward as pure SQL and DuckDB Python UDFs need numpy here — so we classify
    names in Python and join the flags back in the set-based UPDATEs below.
    """
    conn.execute(
        "CREATE OR REPLACE TEMP TABLE _shop_chain_flags "
        "(id TEXT, spec_chain BOOLEAN, nonspec_chain BOOLEAN)"
    )
    rows = conn.execute("SELECT id, name FROM shop_shops").fetchall()
    flags = [(sid, is_specialty_chain(name), is_nonspecialty_chain(name)) for sid, name in rows]
    if flags:
        conn.executemany("INSERT INTO _shop_chain_flags VALUES (?, ?, ?)", flags)


def _count(conn: duckdb.DuckDBPyConnection, where: str = "") -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM shop_shops {where}").fetchone()
    assert row is not None
    return int(row[0])


def compute_specialty(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> SpecialtyCounts:
    """Score every shop and set `is_specialty`. Pass `conn` for tests."""
    with managed_connection(db_path, conn) as conn:
        _ensure_columns(conn)
        _classify_chains(conn)

        # 1) Score. Allowlist → 1.0, blocklist → 0.0, else weighted signals.
        conn.execute(
            """
            UPDATE shop_shops AS s SET
                specialty_score = CASE
                    WHEN f.spec_chain THEN 1.0
                    WHEN f.nonspec_chain THEN 0.0
                    ELSE LEAST(1.0,
                        (CASE WHEN EXISTS (
                            SELECT 1 FROM edges_shop_roaster e WHERE e.shop_id = s.id
                         ) THEN ? ELSE 0 END)
                      + (CASE WHEN s.description IS NOT NULL THEN ? ELSE 0 END)
                      + (CASE WHEN s.roasts_in_house IS TRUE THEN ? ELSE 0 END)
                      + (CASE WHEN s.rating >= ? THEN ? ELSE 0 END)
                      + (CASE WHEN s.website IS NOT NULL AND TRIM(s.website) <> ''
                              THEN ? ELSE 0 END)
                    )
                END,
                updated_at = now()
            FROM _shop_chain_flags f
            WHERE s.id = f.id
            """,
            [
                WEIGHT_CURATED_ROASTER,
                WEIGHT_DESCRIPTION,
                WEIGHT_ROASTS_IN_HOUSE,
                RATING_THRESHOLD,
                WEIGHT_RATING,
                WEIGHT_WEBSITE,
            ],
        )

        # 2) Flag. Allowlist forces true; otherwise not-a-chain AND over threshold.
        conn.execute(
            """
            UPDATE shop_shops AS s SET
                is_specialty = f.spec_chain
                    OR (NOT f.nonspec_chain AND s.specialty_score >= ?)
            FROM _shop_chain_flags f
            WHERE s.id = f.id
            """,
            [SPECIALTY_THRESHOLD],
        )

        total = _count(conn)
        specialty = _count(conn, "WHERE is_specialty")

    return SpecialtyCounts(total=total, specialty=specialty)


if __name__ == "__main__":
    counts = compute_specialty()
    print(f"Specialty: {counts.specialty}/{counts.total} shops flagged")
