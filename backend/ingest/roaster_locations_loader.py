"""Backfill roast_roasters.location from a curated name→location map.

Most roasters enter the database through the products scrape
(backend/ingest/products_loader), which records only name + website — so they
arrive with location = NULL and land in the "Other" bucket on the frontend
Roasters page. This stage fills location by matching roaster name against
data/raw/roaster_locations.json.

Unlike the roasting stage (which delete+inserts roast_roasters and is therefore
unsafe to re-run on a populated DB, because roaster ids are FK-referenced by the
product tables), this stage only ever issues UPDATEs keyed on the roaster id of
rows it has already matched by name. It never inserts or deletes, so it is safe
and idempotent to re-run. By default it fills blanks only; pass overwrite=True to
also correct rows that already carry a location.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from backend.ingest._common import managed_connection

DEFAULT_SOURCE = Path("data/raw/roaster_locations.json")


@dataclass
class LocationBackfillCounts:
    updated: int = 0
    already_set: int = 0
    unmatched: list[str] = field(default_factory=list)


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def backfill_roaster_locations(
    db_path: str | None = None,
    source_path: str | Path = DEFAULT_SOURCE,
    conn: duckdb.DuckDBPyConnection | None = None,
    overwrite: bool = False,
) -> LocationBackfillCounts:
    seed = json.loads(Path(source_path).read_text(encoding="utf-8"))
    mapping: dict[str, str] = seed["locations"]

    counts = LocationBackfillCounts()
    with managed_connection(db_path, conn) as conn:
        for name, location in mapping.items():
            rows = conn.execute(
                "SELECT id, location FROM roast_roasters WHERE name = ?", [name]
            ).fetchall()
            if not rows:
                counts.unmatched.append(name)
                continue
            for roaster_id, existing in rows:
                if not _is_blank(existing) and not overwrite:
                    counts.already_set += 1
                    continue
                conn.execute(
                    "UPDATE roast_roasters SET location = ?, updated_at = now() WHERE id = ?",
                    [location, roaster_id],
                )
                counts.updated += 1

    return counts


if __name__ == "__main__":
    result = backfill_roaster_locations()
    print(f"Backfilled location on {result.updated} roasters ({result.already_set} already set)")
    if result.unmatched:
        print(f"  Unmatched names (no roaster row): {result.unmatched}")
