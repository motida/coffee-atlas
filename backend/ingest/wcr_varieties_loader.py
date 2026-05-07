"""Load World Coffee Research (WCR) varieties catalog into var_varieties.

Source: data/raw/wcr_varieties.json — extracted from the WCR online catalog
(varieties.worldcoffeeresearch.org). Contains 70 Arabica and 47 Robusta
varieties with genetic groups, agronomic traits, and descriptive text.

License: CC BY-NC-ND 4.0
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import duckdb

from backend.db.connection import get_connection

VARIETY_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000002")
DEFAULT_SOURCE = Path("data/raw/wcr_varieties.json")


def _variety_id(slug: str) -> str:
    """Deterministic UUID from variety slug."""
    key = f"variety:{slug}"
    return str(uuid.uuid5(VARIETY_NAMESPACE, key))


def _build_rows(source: Path) -> list[tuple]:
    """Parse the JSON file and produce INSERT-ready tuples."""
    doc = json.loads(source.read_text(encoding="utf-8"))
    rows: list[tuple] = []

    for v in doc["varieties"]:
        row = (
            _variety_id(v["slug"]),
            v["name"],
            v["species"],
            v.get("genetic_group"),
            v.get("description"),
            v.get("yield_potential"),
            v.get("optimal_altitude_min"),
            v.get("optimal_altitude_max"),
            v.get("bean_size"),
            None,  # cherry_color — not available in WCR listing data
            v.get("stature"),
            v.get("disease_resistance"),
        )
        rows.append(row)

    return rows


def load_wcr_varieties(
    db_path: str | None = None,
    source_path: str | Path = DEFAULT_SOURCE,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Populate var_varieties from the WCR varieties JSON.

    Pass `conn` for an existing connection (e.g. in-memory tests); otherwise a
    new connection is opened against `db_path` or the configured default.
    Returns the number of varieties inserted.
    """
    source = Path(source_path)
    rows = _build_rows(source)

    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)

    try:
        for edge in (
            "edges_variety_flavor",
            "edges_country_variety",
            "edges_region_variety",
            "edges_farm_variety",
            "edges_shop_variety",
            "edges_variety_processing",
            "edges_roast_variety",
        ):
            conn.execute(f"DELETE FROM {edge}")
        conn.execute("DELETE FROM var_varieties")
        conn.executemany(
            """
            INSERT INTO var_varieties
                (id, name, species, genetic_group, description,
                 yield_potential, optimal_altitude_min, optimal_altitude_max,
                 bean_size, cherry_color, stature, disease_resistance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        if owns_conn:
            conn.close()

    return len(rows)


if __name__ == "__main__":
    count = load_wcr_varieties()
    print(f"Loaded {count} varieties")
