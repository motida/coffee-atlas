"""Load the SCAA 2016 / WCR flavor wheel hierarchy into flav_attributes.

Source: data/raw/scaa_2016_flavor_wheel.json — a curated JSON of the Coffee
Taster's Flavor Wheel (2016), derived from the WCR Sensory Lexicon. The file
contains 9 top-level categories, 28 subcategories, and 73 leaf attributes
(110 total) with definitions and sensory references.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import duckdb

from backend.db.connection import get_connection

FLAVOR_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000001")
DEFAULT_SOURCE = Path("data/raw/scaa_2016_flavor_wheel.json")


def _flavor_id(path: tuple[str, ...]) -> str:
    key = "flavor:" + "/".join(p.lower() for p in path)
    return str(uuid.uuid5(FLAVOR_NAMESPACE, key))


def _format_references(refs: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Return (sensory_reference, intensity_reference) as human-readable strings."""
    if not refs:
        return None, None
    names = [r["reference"] for r in refs if r.get("reference")]
    intensities = []
    for r in refs:
        parts = []
        if "flavor" in r:
            parts.append(f"flavor={r['flavor']}")
        if "aroma" in r:
            parts.append(f"aroma={r['aroma']}")
        if parts and r.get("reference"):
            intensities.append(f"{r['reference']}: {', '.join(parts)}")
    sensory = "; ".join(names) if names else None
    intensity = "; ".join(intensities) if intensities else None
    return sensory, intensity


def _walk(
    nodes: list[dict[str, Any]],
    rows: list[tuple],
    path: tuple[str, ...] = (),
    category: str | None = None,
    subcategory: str | None = None,
    parent_id: str | None = None,
    depth: int = 1,
) -> None:
    for node in nodes:
        name = node["name"]
        node_path = path + (name,)
        node_id = _flavor_id(node_path)
        node_category = name if depth == 1 else category
        node_subcategory = name if depth == 2 else subcategory
        sensory, intensity = _format_references(node.get("references", []))
        rows.append(
            (
                node_id,
                name,
                node_category,
                node_subcategory,
                node.get("definition"),
                intensity,
                sensory,
                parent_id,
            )
        )
        children = node.get("children") or []
        if children:
            _walk(children, rows, node_path, node_category, node_subcategory, node_id, depth + 1)


def _build_rows(source: Path) -> list[tuple]:
    doc = json.loads(source.read_text(encoding="utf-8"))
    rows: list[tuple] = []
    _walk(doc["data"], rows)
    return rows


def load_wcr_lexicon(
    db_path: str | None = None,
    source_path: str | Path = DEFAULT_SOURCE,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Populate flav_attributes from the flavor wheel JSON.

    Pass `conn` for an existing connection (e.g. in-memory tests); otherwise a
    new connection is opened against `db_path` or the configured default.
    Returns the number of attributes inserted.
    """
    source = Path(source_path)
    rows = _build_rows(source)

    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)

    try:
        conn.execute("DELETE FROM flav_attributes")
        conn.executemany(
            """
            INSERT INTO flav_attributes
                (id, name, category, subcategory, description,
                 intensity_reference, sensory_reference, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        if owns_conn:
            conn.close()

    return len(rows)


if __name__ == "__main__":
    count = load_wcr_lexicon()
    print(f"Loaded {count} flavor attributes")
