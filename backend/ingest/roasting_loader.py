"""Load the roasting domain from a hand-curated seed file.

Populates roast_profiles and roast_roasters from data/raw/roasting_seed.json,
then derives edges_roast_variety (RoastProfile → suitableFor → Variety) by
resolving each profile's `suitable_for` rule against var_varieties:

- species: the variety's species must be one of the listed species
- min_optimal_altitude: the variety's optimal_altitude_max must reach
  the threshold — high-grown beans are denser and keep the acidity that
  lighter profiles are built to showcase

Profiles and roasters load fine on an empty database, but the suitability
edges only materialize for varieties present at load time, so run the
varieties stage first.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from backend.db.connection import get_connection

ROAST_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000007")
DEFAULT_SOURCE = Path("data/raw/roasting_seed.json")


@dataclass
class RoastingCounts:
    profiles: int
    roasters: int
    roast_variety_edges: int


def _slug(*parts: str) -> str:
    return ":".join(p.strip().lower() for p in parts if p)


def _uid(*parts: str) -> str:
    return str(uuid.uuid5(ROAST_NAMESPACE, _slug(*parts)))


def _suitability_edges(
    conn: duckdb.DuckDBPyConnection, profile_id: str, rule: dict[str, Any]
) -> int:
    """Insert edges for every variety matching the profile's suitable_for rule."""
    species = rule.get("species", [])
    if not species:
        return 0

    placeholders = ", ".join("?" for _ in species)
    where = [f"species IN ({placeholders})"]
    params: list[Any] = [profile_id, profile_id, *species]

    min_altitude = rule.get("min_optimal_altitude")
    if min_altitude is not None:
        where.append("optimal_altitude_max >= ?")
        params.append(min_altitude)

    conn.execute(
        f"""
        INSERT INTO edges_roast_variety (id, profile_id, variety_id)
        SELECT 'rv:' || ? || ':' || id, ?, id
        FROM var_varieties
        WHERE {" AND ".join(where)}
        """,
        params,
    )
    row = conn.execute(
        "SELECT COUNT(*) FROM edges_roast_variety WHERE profile_id = ?", [profile_id]
    ).fetchone()
    assert row is not None
    return row[0]


def load_roasting(
    db_path: str | None = None,
    source_path: str | Path = DEFAULT_SOURCE,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> RoastingCounts:
    seed = json.loads(Path(source_path).read_text(encoding="utf-8"))

    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)

    try:
        # Edges reference profiles by FK, so they go first; then delete+insert
        # the referenced tables (ON CONFLICT can't update FK-referenced rows).
        for table in ("edges_roast_variety", "roast_profiles", "roast_roasters"):
            conn.execute(f"DELETE FROM {table}")

        profile_rows = [
            (
                _uid("profile", p["name"]),
                p["name"],
                p.get("roast_level"),
                p.get("first_crack_temp"),
                p.get("development_time_ratio"),
                p.get("charge_temp"),
                p.get("total_roast_time"),
                p.get("description"),
            )
            for p in seed["profiles"]
        ]
        conn.executemany(
            """
            INSERT INTO roast_profiles
                (id, name, roast_level, first_crack_temp, development_time_ratio,
                 charge_temp, total_roast_time, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            profile_rows,
        )

        roaster_rows = [
            (_uid("roaster", r["name"]), r["name"], r.get("location"), r.get("website"))
            for r in seed["roasters"]
        ]
        conn.executemany(
            "INSERT INTO roast_roasters (id, name, location, website) VALUES (?, ?, ?, ?)",
            roaster_rows,
        )

        edges = 0
        for profile, (profile_id, *_rest) in zip(seed["profiles"], profile_rows):
            edges += _suitability_edges(conn, profile_id, profile.get("suitable_for", {}))

        return RoastingCounts(
            profiles=len(profile_rows),
            roasters=len(roaster_rows),
            roast_variety_edges=edges,
        )
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    counts = load_roasting()
    print(
        f"Loaded {counts.profiles} roast profiles, {counts.roasters} roasters, "
        f"{counts.roast_variety_edges} roast→variety edges"
    )
