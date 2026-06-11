"""Load the distribution domain from a hand-curated seed file.

Populates dist_certifications, dist_importers, and dist_trade_routes from
data/raw/distribution_seed.json. Importing countries that are not yet present
in org_countries are inserted using the same ORIGIN_NAMESPACE scheme as
cqi_loader so IDs remain stable across stages.

Trade-route annual_volume is left NULL — only the relationships are asserted.
Backfill volumes from FAOSTAT or ICO bilateral data when fuller numbers matter.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import duckdb

from backend.db.connection import get_connection

ORIGIN_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000003")
DIST_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000006")
DEFAULT_SOURCE = Path("data/raw/distribution_seed.json")


@dataclass
class DistributionCounts:
    countries_added: int
    certifications: int
    importers: int
    trade_routes: int
    unresolved: list[str]


def _slug(*parts: str) -> str:
    return ":".join(p.strip().lower() for p in parts if p)


def _uid(namespace: uuid.UUID, *parts: str) -> str:
    return str(uuid.uuid5(namespace, _slug(*parts)))


def _country_id(name: str) -> str:
    return _uid(ORIGIN_NAMESPACE, "country", name)


def _ensure_countries(
    conn: duckdb.DuckDBPyConnection, names: list[str]
) -> tuple[dict[str, str], int]:
    """Return name→id map for all countries referenced, inserting any missing rows."""
    existing = dict(conn.execute("SELECT name, id FROM org_countries").fetchall())
    new_rows = [(_country_id(n), n) for n in names if n not in existing]
    if new_rows:
        conn.executemany("INSERT INTO org_countries (id, name) VALUES (?, ?)", new_rows)
        for cid, n in new_rows:
            existing[n] = cid
    return existing, len(new_rows)


def load_distribution(
    db_path: str | None = None,
    source_path: str | Path = DEFAULT_SOURCE,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> DistributionCounts:
    seed = json.loads(Path(source_path).read_text(encoding="utf-8"))

    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)

    try:
        referenced = {*seed.get("import_countries", [])}
        referenced.update(i["country"] for i in seed["importers"])
        referenced.update(r["exporter"] for r in seed["trade_routes"])
        referenced.update(r["importer"] for r in seed["trade_routes"])
        name_to_id, countries_added = _ensure_countries(conn, sorted(referenced))

        for table in ("dist_trade_routes", "dist_importers", "dist_certifications"):
            conn.execute(f"DELETE FROM {table}")

        cert_rows = [
            (_uid(DIST_NAMESPACE, "cert", c["name"]), c["name"], c.get("description"))
            for c in seed["certifications"]
        ]
        conn.executemany(
            "INSERT INTO dist_certifications (id, name, description) VALUES (?, ?, ?)",
            cert_rows,
        )

        unresolved: list[str] = []
        importer_rows = []
        for imp in seed["importers"]:
            country_id = name_to_id.get(imp["country"])
            if country_id is None:
                unresolved.append(f"importer:{imp['name']} → {imp['country']}")
                continue
            importer_rows.append(
                (
                    _uid(DIST_NAMESPACE, "importer", imp["name"]),
                    imp["name"],
                    country_id,
                    imp.get("website"),
                )
            )
        conn.executemany(
            "INSERT INTO dist_importers (id, name, country_id, website) VALUES (?, ?, ?, ?)",
            importer_rows,
        )

        route_rows = []
        for r in seed["trade_routes"]:
            exp_id = name_to_id.get(r["exporter"])
            imp_id = name_to_id.get(r["importer"])
            if exp_id is None or imp_id is None:
                unresolved.append(f"route:{r['exporter']} → {r['importer']}")
                continue
            route_rows.append(
                (
                    _uid(DIST_NAMESPACE, "route", exp_id, imp_id),
                    exp_id,
                    imp_id,
                    None,
                    None,
                )
            )
        conn.executemany(
            "INSERT INTO dist_trade_routes "
            "(id, exporter_country_id, importer_country_id, annual_volume, year) "
            "VALUES (?, ?, ?, ?, ?)",
            route_rows,
        )

        return DistributionCounts(
            countries_added=countries_added,
            certifications=len(cert_rows),
            importers=len(importer_rows),
            trade_routes=len(route_rows),
            unresolved=unresolved,
        )
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    counts = load_distribution()
    print(
        f"Loaded {counts.certifications} certifications, "
        f"{counts.importers} importers, {counts.trade_routes} trade routes "
        f"(+{counts.countries_added} new countries)"
    )
    if counts.unresolved:
        print(f"Unresolved: {counts.unresolved}")
