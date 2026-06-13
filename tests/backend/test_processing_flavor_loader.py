"""Tests for the curated processing→flavor edge seeder."""

import json
from pathlib import Path

from backend.ingest.processing_flavor_loader import DEFAULT_SOURCE, load_processing_flavor

SEED = json.loads(Path(DEFAULT_SOURCE).read_text(encoding="utf-8"))


def _seed_methods(db):
    """Insert the five CQI processing methods, keyed by category."""
    db.executemany(
        "INSERT INTO proc_methods (id, name, category) VALUES (?, ?, ?)",
        [
            ("m_wet", "Washed / Wet", "wet"),
            ("m_dry", "Natural / Dry", "dry"),
            ("m_honey", "Pulped natural / honey", "honey"),
            ("m_semi", "Semi-washed / Semi-pulped", "semi-washed"),
            ("m_other", "Other", "other"),
        ],
    )


def _seed_flavors(db):
    """Insert the wheel nodes the seed references, plus the ambiguous duplicate."""
    names = [
        ("Citrus fruit", "Fruity", "Citrus fruit", "f_citrus"),
        ("Black Tea", "Floral", "Black Tea", "f_blacktea"),
        ("Sour", "Sour/Fermented", "Sour", "f_sour"),
        ("Alcohol/Fermented", "Sour/Fermented", "Alcohol/Fermented", "f_alc"),
        ("Berry", "Fruity", "Berry", "f_berry"),
        ("Dried fruit", "Fruity", "Dried fruit", "f_dried"),
        ("Other fruit", "Fruity", "Other fruit", "f_otherfruit"),
        ("Brown sugar", "Sweet", "Brown sugar", "f_brownsugar"),
        ("Overall sweet", "Sweet", "Overall sweet", "f_oversweet"),
        ("Vanilla", "Sweet", "Vanilla", "f_vanilla"),
        ("Sweet Aromatics", "Sweet", "Sweet Aromatics", "f_sweetarom"),
        ("Cocoa", "Nutty/Cocoa", "Cocoa", "f_cocoa"),
        ("Brown spice", "Spices", "Brown spice", "f_brownspice"),
        ("Beany", "Green/Vegetative", "Beany", "f_beany"),
        ("Pipe tobacco", "Roasted", "Pipe tobacco", "f_pipe"),
    ]
    db.executemany(
        "INSERT INTO flav_attributes (id, name, category, subcategory, parent_id) "
        "VALUES (?, ?, ?, ?, ?)",
        [(fid, name, cat, sub, "p_root") for name, cat, sub, fid in names],
    )
    # "Floral" appears twice in the real wheel: a top-level category (parent_id
    # NULL) and a same-named child. The loader must pick the top-level node.
    db.execute(
        "INSERT INTO flav_attributes (id, name, category, subcategory, parent_id) VALUES "
        "('f_floral_top', 'Floral', 'Floral', NULL, NULL), "
        "('f_floral_child', 'Floral', 'Floral', 'Floral', 'f_floral_top')"
    )


def test_seeds_expected_edge_count(db):
    _seed_methods(db)
    _seed_flavors(db)
    counts = load_processing_flavor(conn=db)
    # 5 (wet) + 6 (dry) + 5 (honey) + 6 (semi-washed) = 22; "other" is unmapped.
    assert counts.edges == 22
    assert counts.methods_matched == 4
    assert counts.skipped_methods == []
    assert counts.skipped_flavors == []
    assert db.execute("SELECT COUNT(*) FROM edges_processing_flavor").fetchone()[0] == 22


def test_effects_are_stored(db):
    _seed_methods(db)
    _seed_flavors(db)
    load_processing_flavor(conn=db)
    effects = {
        r[0] for r in db.execute("SELECT DISTINCT effect FROM edges_processing_flavor").fetchall()
    }
    assert effects == {"enhances", "diminishes"}
    # Natural/dry enhances Berry...
    assert db.execute(
        "SELECT effect FROM edges_processing_flavor WHERE method_id='m_dry' AND flavor_id='f_berry'"
    ).fetchone() == ("enhances",)
    # ...and diminishes Citrus fruit.
    assert db.execute(
        "SELECT effect FROM edges_processing_flavor "
        "WHERE method_id='m_dry' AND flavor_id='f_citrus'"
    ).fetchone() == ("diminishes",)


def test_ambiguous_floral_resolves_to_top_level(db):
    _seed_methods(db)
    _seed_flavors(db)
    load_processing_flavor(conn=db)
    # Washed enhances "Floral" — must bind the top-level node, not the child.
    rows = db.execute(
        "SELECT flavor_id FROM edges_processing_flavor "
        "WHERE method_id='m_wet' AND effect='enhances'"
    ).fetchall()
    flavor_ids = {r[0] for r in rows}
    assert "f_floral_top" in flavor_ids
    assert "f_floral_child" not in flavor_ids


def test_idempotent_rerun(db):
    _seed_methods(db)
    _seed_flavors(db)
    load_processing_flavor(conn=db)
    load_processing_flavor(conn=db)
    assert db.execute("SELECT COUNT(*) FROM edges_processing_flavor").fetchone()[0] == 22


def test_missing_flavors_are_skipped_not_fatal(db):
    _seed_methods(db)
    # No flav_attributes inserted at all.
    counts = load_processing_flavor(conn=db)
    assert counts.edges == 0
    assert counts.methods_matched == 4
    assert "Berry" in counts.skipped_flavors


def test_missing_methods_are_reported(db):
    _seed_flavors(db)
    # No proc_methods inserted.
    counts = load_processing_flavor(conn=db)
    assert counts.edges == 0
    assert counts.methods_matched == 0
    assert set(counts.skipped_methods) == {"wet", "dry", "honey", "semi-washed"}


def test_seed_file_references_only_known_categories():
    cats = {rel["method_category"] for rel in SEED["relationships"]}
    assert cats <= {"wet", "dry", "honey", "semi-washed", "other"}
