from backend.ingest.wcr_lexicon_loader import load_wcr_lexicon


def test_loads_all_110_attributes(db):
    count = load_wcr_lexicon(conn=db)
    assert count == 110
    assert db.execute("SELECT COUNT(*) FROM flav_attributes").fetchone()[0] == 110


def test_hierarchy_shape(db):
    load_wcr_lexicon(conn=db)
    tier1 = db.execute(
        "SELECT COUNT(*) FROM flav_attributes WHERE parent_id IS NULL"
    ).fetchone()[0]
    assert tier1 == 9

    orphans = db.execute(
        """
        SELECT COUNT(*) FROM flav_attributes a
        WHERE a.parent_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM flav_attributes p WHERE p.id = a.parent_id)
        """
    ).fetchone()[0]
    assert orphans == 0


def test_leaf_attributes_have_context(db):
    load_wcr_lexicon(conn=db)
    row = db.execute(
        """
        SELECT category, subcategory, description
        FROM flav_attributes WHERE name = 'Blackberry'
        """
    ).fetchone()
    assert row == ("Fruity", "Berry", row[2])
    assert "blackberr" in row[2].lower()


def test_idempotent_reload(db):
    load_wcr_lexicon(conn=db)
    load_wcr_lexicon(conn=db)
    assert db.execute("SELECT COUNT(*) FROM flav_attributes").fetchone()[0] == 110
