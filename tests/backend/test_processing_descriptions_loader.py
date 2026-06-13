"""Tests for the curated processing-method description enricher."""

from backend.ingest.processing_descriptions_loader import (
    PROCESSING_DESCRIPTIONS,
    load_processing_descriptions,
)


def _seed_methods(db):
    """The five CQI processing methods, keyed by category."""
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


def test_describes_curated_categories(db):
    _seed_methods(db)
    counts = load_processing_descriptions(conn=db)
    assert counts.categories_applied == 4
    assert counts.methods_updated == 4
    assert counts.skipped_categories == []

    rows = dict(db.execute("SELECT category, description FROM proc_methods").fetchall())
    assert rows["wet"].startswith("Washed")
    assert rows["dry"] == PROCESSING_DESCRIPTIONS["dry"]
    # "other" is intentionally left untouched.
    assert rows["other"] is None


def test_idempotent(db):
    _seed_methods(db)
    load_processing_descriptions(conn=db)
    first = db.execute("SELECT description FROM proc_methods WHERE category = 'wet'").fetchone()[0]
    load_processing_descriptions(conn=db)
    second = db.execute("SELECT description FROM proc_methods WHERE category = 'wet'").fetchone()[0]
    assert first == second == PROCESSING_DESCRIPTIONS["wet"]


def test_missing_categories_are_skipped(db):
    # Only a washed method present — the other curated categories have no row.
    db.execute(
        "INSERT INTO proc_methods (id, name, category) VALUES ('m_wet', 'Washed / Wet', 'wet')"
    )
    counts = load_processing_descriptions(conn=db)
    assert counts.categories_applied == 1
    assert counts.methods_updated == 1
    assert set(counts.skipped_categories) == {"dry", "honey", "semi-washed"}


def test_preserves_fk_referenced_edges(db):
    """Describing a method must not disturb edges that reference it by FK."""
    _seed_methods(db)
    db.execute("INSERT INTO var_varieties (id, name) VALUES ('v1', 'Bourbon')")
    db.execute("INSERT INTO flav_attributes (id, name) VALUES ('f1', 'Berry')")
    db.execute(
        "INSERT INTO edges_variety_processing (id, variety_id, method_id) VALUES ('e1', 'v1', 'm_wet')"
    )
    db.execute(
        "INSERT INTO edges_processing_flavor (id, method_id, flavor_id, effect) "
        "VALUES ('e2', 'm_wet', 'f1', 'enhances')"
    )
    load_processing_descriptions(conn=db)
    assert db.execute("SELECT COUNT(*) FROM edges_variety_processing").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM edges_processing_flavor").fetchone()[0] == 1


def test_no_methods_is_noop(db):
    counts = load_processing_descriptions(conn=db)
    assert counts.methods_updated == 0
    assert counts.categories_applied == 0
    assert set(counts.skipped_categories) == set(PROCESSING_DESCRIPTIONS)
