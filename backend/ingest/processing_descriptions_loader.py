"""Enrich proc_methods with curated, human-readable descriptions.

cqi_loader creates processing methods with only a name and a coarse category
(wet / dry / honey / semi-washed). This stage fills in `description`, which
powers the processing detail page and — once the embeddings stage runs — makes
methods semantically searchable (proc_methods.description_embedding is built
from this text).

Descriptions are keyed by category, so they stay stable across CQI re-ingests.
cqi_loader treats proc_methods.description as enrichment and snapshots/restores
it around its rebuild, so the order is: run this after `cqi`, and a later
standalone `--stage cqi` re-run will preserve what we wrote here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from backend.db.connection import get_connection

# Keyed by the coarse category cqi_loader assigns. "other" is left untouched —
# it's a catch-all with no meaningful single description.
PROCESSING_DESCRIPTIONS: dict[str, str] = {
    "wet": (
        "Washed — also called wet — processing removes the cherry's skin and pulp, then "
        "ferments and rinses the sticky mucilage off the parchment before drying. Taking the "
        "fruit out of contact with the bean early produces the cleanest, most transparent cup, "
        "foregrounding a variety's intrinsic acidity, floral notes and origin character."
    ),
    "dry": (
        "Natural — or dry — processing dries the whole cherry intact, so the bean ferments "
        "slowly inside its own fruit for days or weeks. The extended fruit contact builds a "
        "heavy body and pronounced berry, jammy and winey sweetness, at the cost of the clean "
        "acidity a washed coffee shows."
    ),
    "honey": (
        "Honey, or pulped natural, processing depulps the cherry but leaves a measured amount "
        "of sweet mucilage clinging to the parchment as it dries. The result sits between washed "
        "and natural: a rounded, syrupy sweetness and soft fruit, with more clarity than a "
        "natural but more body than a washed."
    ),
    "semi-washed": (
        "Semi-washed — the wet-hulled giling basah method common in Indonesia — strips the "
        "parchment while the bean is still damp, then finishes drying the bare green bean. The "
        "short, humid process yields the earthy, herbal, cedar-and-spice profile and full, "
        "low-acid body associated with Sumatran coffees."
    ),
}


@dataclass
class DescriptionCounts:
    methods_updated: int
    categories_applied: int
    skipped_categories: list[str] = field(default_factory=list)


def load_processing_descriptions(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> DescriptionCounts:
    """Set proc_methods.description for every method whose category we curate.

    Pass `conn` for an existing connection (e.g. in-memory tests); otherwise a
    new connection is opened against `db_path` or the configured default.
    Idempotent: writing the same text twice is a no-op. Categories with no
    matching method (e.g. an origin set with no honey coffees) are reported as
    skipped rather than raising.
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)

    try:
        methods_updated = 0
        categories_applied = 0
        skipped: list[str] = []

        for category, description in PROCESSING_DESCRIPTIONS.items():
            matched = conn.execute(
                "SELECT COUNT(*) FROM proc_methods WHERE category = ?", [category]
            ).fetchone()
            assert matched is not None
            if matched[0] == 0:
                skipped.append(category)
                continue
            # Plain scalar UPDATE: safe on FK-referenced rows (unlike the ARRAY
            # embedding column, which DuckDB rewrites as delete+insert).
            conn.execute(
                "UPDATE proc_methods SET description = ?, updated_at = now() WHERE category = ?",
                [description, category],
            )
            methods_updated += matched[0]
            categories_applied += 1

        return DescriptionCounts(
            methods_updated=methods_updated,
            categories_applied=categories_applied,
            skipped_categories=skipped,
        )
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    counts = load_processing_descriptions()
    print(
        f"Described {counts.methods_updated} methods across {counts.categories_applied} categories"
    )
    if counts.skipped_categories:
        print(f"  Skipped categories (no method present): {counts.skipped_categories}")
