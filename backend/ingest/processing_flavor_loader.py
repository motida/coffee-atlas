"""Seed edges_processing_flavor (ProcessingMethod → enhances/diminishes → FlavorAttribute).

Hand-curated from data/raw/processing_flavor_seed.json. Each relationship keys a
processing method by the coarse `category` cqi_loader assigns (wet / dry / honey /
semi-washed) and lists the flavor attributes the method tends to enhance or
diminish. Flavors are resolved by name against flav_attributes (the WCR/SCAA
wheel); for the two names that appear at more than one depth (Floral,
Green/Vegetative) the top-level node wins.

Ordering: run after the cqi and lexicon stages — both rebuild this edge table's
neighbours and clear it — and before embeddings/graph, which read it. Methods or
flavors missing at load time are skipped and counted rather than raising, so the
stage is safe on a partially-seeded database.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from backend.ingest._common import managed_connection

# Own namespace, distinct from products (which uses …000008); sharing it would
# risk edge-id collisions across the two unrelated domains.
PROC_FLAVOR_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000009")
DEFAULT_SOURCE = Path("data/raw/processing_flavor_seed.json")

EFFECTS = ("enhances", "diminishes")


@dataclass
class ProcessingFlavorCounts:
    edges: int
    methods_matched: int
    skipped_methods: list[str] = field(default_factory=list)
    skipped_flavors: list[str] = field(default_factory=list)


def _edge_id(method_id: str, flavor_id: str, effect: str) -> str:
    return str(uuid.uuid5(PROC_FLAVOR_NAMESPACE, f"{method_id}:{flavor_id}:{effect}"))


def _method_ids(conn: duckdb.DuckDBPyConnection, category: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT id FROM proc_methods WHERE LOWER(category) = LOWER(?)", [category]
        ).fetchall()
    ]


def _flavor_id(conn: duckdb.DuckDBPyConnection, name: str) -> str | None:
    # Two wheel names (Floral, Green/Vegetative) exist as both a top-level
    # category and a child; prefer the top-level node for a stable match.
    row = conn.execute(
        """
        SELECT id FROM flav_attributes
        WHERE LOWER(name) = LOWER(?)
        ORDER BY (parent_id IS NULL) DESC, id
        LIMIT 1
        """,
        [name],
    ).fetchone()
    return row[0] if row else None


def load_processing_flavor(
    db_path: str | None = None,
    source_path: str | Path = DEFAULT_SOURCE,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> ProcessingFlavorCounts:
    """Populate edges_processing_flavor from the curated seed.

    Pass `conn` for an existing connection (e.g. in-memory tests); otherwise a
    new connection is opened against `db_path` or the configured default.
    Idempotent: the edge table is cleared and rebuilt from the seed.
    """
    seed = json.loads(Path(source_path).read_text(encoding="utf-8"))

    with managed_connection(db_path, conn) as conn:
        conn.execute("DELETE FROM edges_processing_flavor")

        edges: dict[str, tuple[str, str, str, str]] = {}
        methods_matched: set[str] = set()
        skipped_methods: list[str] = []
        skipped_flavors: set[str] = set()

        for rel in seed["relationships"]:
            category = rel["method_category"]
            method_ids = _method_ids(conn, category)
            if not method_ids:
                skipped_methods.append(category)
                continue
            methods_matched.update(method_ids)

            for effect in EFFECTS:
                for name in rel.get(effect, []):
                    flavor_id = _flavor_id(conn, name)
                    if flavor_id is None:
                        skipped_flavors.add(name)
                        continue
                    for method_id in method_ids:
                        edge_id = _edge_id(method_id, flavor_id, effect)
                        edges[edge_id] = (edge_id, method_id, flavor_id, effect)

        if edges:
            conn.executemany(
                "INSERT INTO edges_processing_flavor (id, method_id, flavor_id, effect) "
                "VALUES (?, ?, ?, ?)",
                list(edges.values()),
            )

        return ProcessingFlavorCounts(
            edges=len(edges),
            methods_matched=len(methods_matched),
            skipped_methods=skipped_methods,
            skipped_flavors=sorted(skipped_flavors),
        )


if __name__ == "__main__":
    counts = load_processing_flavor()
    print(f"Seeded {counts.edges} processing→flavor edges across {counts.methods_matched} methods")
    if counts.skipped_methods:
        print(f"  Skipped method categories (not found): {counts.skipped_methods}")
    if counts.skipped_flavors:
        print(f"  Skipped flavors (not found): {counts.skipped_flavors}")
