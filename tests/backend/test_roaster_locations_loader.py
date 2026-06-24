"""Tests for the roaster-location backfill stage.

The stage fills roast_roasters.location by matching the curated name→location
map onto existing rows. It must only touch blanks (unless overwrite=True), never
insert/delete (roast_roasters is FK-referenced by the product tables), and be
idempotent on re-run.
"""

import json
from pathlib import Path

from backend.ingest.roaster_locations_loader import (
    DEFAULT_SOURCE,
    backfill_roaster_locations,
)

REAL_MAP = json.loads(Path(DEFAULT_SOURCE).read_text(encoding="utf-8"))["locations"]


def _insert_roaster(db, rid, name, location=None):
    db.execute(
        "INSERT INTO roast_roasters (id, name, location) VALUES (?, ?, ?)",
        [rid, name, location],
    )


def _write_map(tmp_path, mapping):
    path = tmp_path / "roaster_locations.json"
    path.write_text(json.dumps({"locations": mapping}), encoding="utf-8")
    return path


def test_fills_blank_locations(db, tmp_path):
    _insert_roaster(db, "r1", "Blank Roaster")  # location NULL
    _insert_roaster(db, "r2", "Empty Roaster", "   ")  # whitespace-only
    src = _write_map(
        tmp_path, {"Blank Roaster": "Oslo, Norway", "Empty Roaster": "Bath, United Kingdom"}
    )

    counts = backfill_roaster_locations(conn=db, source_path=src)

    assert counts.updated == 2
    assert counts.already_set == 0
    assert counts.unmatched == []
    locs = dict(db.execute("SELECT name, location FROM roast_roasters ORDER BY name").fetchall())
    assert locs == {"Blank Roaster": "Oslo, Norway", "Empty Roaster": "Bath, United Kingdom"}


def test_does_not_overwrite_existing_by_default(db, tmp_path):
    _insert_roaster(db, "r1", "Seeded Roaster", "Tel Aviv, Israel")
    src = _write_map(tmp_path, {"Seeded Roaster": "Wrong, Nowhere"})

    counts = backfill_roaster_locations(conn=db, source_path=src)

    assert counts.updated == 0
    assert counts.already_set == 1
    loc = db.execute("SELECT location FROM roast_roasters WHERE id = 'r1'").fetchone()[0]
    assert loc == "Tel Aviv, Israel"


def test_overwrite_flag_replaces_existing(db, tmp_path):
    _insert_roaster(db, "r1", "Seeded Roaster", "Old, Place")
    src = _write_map(tmp_path, {"Seeded Roaster": "New, Place"})

    counts = backfill_roaster_locations(conn=db, source_path=src, overwrite=True)

    assert counts.updated == 1
    loc = db.execute("SELECT location FROM roast_roasters WHERE id = 'r1'").fetchone()[0]
    assert loc == "New, Place"


def test_unmatched_names_are_reported_not_inserted(db, tmp_path):
    src = _write_map(tmp_path, {"Ghost Roaster": "Nowhere, Land"})

    counts = backfill_roaster_locations(conn=db, source_path=src)

    assert counts.updated == 0
    assert counts.unmatched == ["Ghost Roaster"]
    assert db.execute("SELECT COUNT(*) FROM roast_roasters").fetchone()[0] == 0


def test_idempotent_rerun(db, tmp_path):
    _insert_roaster(db, "r1", "Blank Roaster")
    src = _write_map(tmp_path, {"Blank Roaster": "Oslo, Norway"})

    first = backfill_roaster_locations(conn=db, source_path=src)
    second = backfill_roaster_locations(conn=db, source_path=src)

    assert first.updated == 1
    assert second.updated == 0
    assert second.already_set == 1


def test_real_map_locations_all_carry_a_country(db):
    # Every curated location must have a country segment (text after the last
    # comma, or the whole string) — that segment is the frontend grouping key.
    for name, location in REAL_MAP.items():
        country = location.split(",")[-1].strip()
        assert country, f"{name!r} has no country in {location!r}"
