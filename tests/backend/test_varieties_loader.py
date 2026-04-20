"""Tests for the WCR varieties loader."""

from backend.ingest.wcr_varieties_loader import load_wcr_varieties


def test_loads_all_varieties(db):
    count = load_wcr_varieties(conn=db)
    assert count == 117


def test_species_split(db):
    load_wcr_varieties(conn=db)
    arabica = db.execute("SELECT COUNT(*) FROM var_varieties WHERE species = 'Arabica'").fetchone()[
        0
    ]
    robusta = db.execute("SELECT COUNT(*) FROM var_varieties WHERE species = 'Robusta'").fetchone()[
        0
    ]
    assert arabica == 70
    assert robusta == 47


def test_genetic_groups_populated(db):
    load_wcr_varieties(conn=db)
    with_group = db.execute(
        "SELECT COUNT(*) FROM var_varieties WHERE genetic_group IS NOT NULL"
    ).fetchone()[0]
    # All 117 should have a genetic group resolved
    assert with_group == 117


def test_known_variety_fields(db):
    """Bourbon is a well-known variety — verify its fields are populated."""
    load_wcr_varieties(conn=db)
    row = db.execute(
        "SELECT name, species, genetic_group, description FROM var_varieties WHERE name = 'Bourbon'"
    ).fetchone()
    assert row is not None
    assert row[0] == "Bourbon"
    assert row[1] == "Arabica"
    assert row[2] == "Bourbon-Typica group (Bourbon related)"
    assert row[3] is not None and len(row[3]) > 50


def test_idempotent(db):
    load_wcr_varieties(conn=db)
    load_wcr_varieties(conn=db)
    count = db.execute("SELECT COUNT(*) FROM var_varieties").fetchone()[0]
    assert count == 117


def test_descriptions_not_empty(db):
    load_wcr_varieties(conn=db)
    no_desc = db.execute(
        "SELECT COUNT(*) FROM var_varieties WHERE description IS NULL OR description = ''"
    ).fetchone()[0]
    assert no_desc == 0
