"""Tests for the roasting seed loader and its suitability-edge derivation."""

import json
from pathlib import Path

from backend.ingest.roasting_loader import DEFAULT_SOURCE, load_roasting

SEED = json.loads(Path(DEFAULT_SOURCE).read_text(encoding="utf-8"))


def _insert_variety(db, vid, name, species, alt_max=None):
    db.execute(
        "INSERT INTO var_varieties (id, name, species, optimal_altitude_max) VALUES (?, ?, ?, ?)",
        [vid, name, species, alt_max],
    )


def test_loads_all_profiles_and_roasters(db):
    counts = load_roasting(conn=db)
    # Profiles are a stable taxonomy; roasters are a curation surface that grows
    # (e.g. regional additions), so assert against the seed length, not a literal.
    assert counts.profiles == len(SEED["profiles"]) == 11
    assert counts.roasters == len(SEED["roasters"])
    assert db.execute("SELECT COUNT(*) FROM roast_profiles").fetchone()[0] == 11
    assert db.execute("SELECT COUNT(*) FROM roast_roasters").fetchone()[0] == len(SEED["roasters"])


def test_no_varieties_means_no_edges(db):
    counts = load_roasting(conn=db)
    assert counts.roast_variety_edges == 0


def test_profile_fields_populated(db):
    load_roasting(conn=db)
    row = db.execute(
        """
        SELECT roast_level, first_crack_temp, development_time_ratio,
               charge_temp, total_roast_time, description
        FROM roast_profiles WHERE name = 'Nordic Light'
        """
    ).fetchone()
    assert row is not None
    level, fc, dtr, charge, total, desc = row
    assert level == "light"
    assert 190 < fc < 210
    assert 0 < dtr < 1
    assert charge > 0
    assert total > 0
    assert "filter" in desc.lower()


def test_suitability_edges_respect_species_and_altitude(db):
    _insert_variety(db, "v_high", "Geisha", "Arabica", alt_max=2000)
    _insert_variety(db, "v_low", "AB3", "Arabica", alt_max=800)
    _insert_variety(db, "v_null", "Unknown", "Arabica", alt_max=None)
    _insert_variety(db, "v_rob", "Nemaya", "Robusta", alt_max=800)
    counts = load_roasting(conn=db)
    assert counts.roast_variety_edges > 0

    def varieties_for(profile_name):
        rows = db.execute(
            """
            SELECT e.variety_id
            FROM edges_roast_variety e
            JOIN roast_profiles p ON e.profile_id = p.id
            WHERE p.name = ?
            """,
            [profile_name],
        ).fetchall()
        return {r[0] for r in rows}

    # Light + altitude-gated: low-grown and NULL-altitude Arabica are excluded.
    assert varieties_for("Nordic Light") == {"v_high"}
    # Arabica-only, no altitude gate: all Arabica including NULL altitude.
    assert varieties_for("City Roast") == {"v_high", "v_low", "v_null"}
    # Dark roasts accept both species.
    assert varieties_for("Italian Roast") == {"v_high", "v_low", "v_null", "v_rob"}


def test_idempotent_reload(db):
    _insert_variety(db, "v1", "Geisha", "Arabica", alt_max=2000)
    first = load_roasting(conn=db)
    second = load_roasting(conn=db)
    assert first == second
    assert db.execute("SELECT COUNT(*) FROM roast_profiles").fetchone()[0] == 11
