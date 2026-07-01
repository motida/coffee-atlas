"""Tests for backend/ingest/overture_shops_loader.py — helpers only.

The S3-hitting integration path is verified by running `just ingest shops`
manually; not exercised here to keep tests offline and fast.
"""

from __future__ import annotations

import pytest

from backend.ingest.overture_shops_loader import (
    DEFAULT_BBOX,
    _category_predicate,
    _merge_shops,
    _resolve_bbox,
)


def test_resolve_bbox_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OVERTURE_BBOX", raising=False)
    assert _resolve_bbox() == DEFAULT_BBOX


def test_resolve_bbox_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERTURE_BBOX", "-10.5,30.0,40.25,60.5")
    assert _resolve_bbox() == (-10.5, 30.0, 40.25, 60.5)


def test_resolve_bbox_rejects_malformed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERTURE_BBOX", "1,2,3")
    with pytest.raises(ValueError, match="must be"):
        _resolve_bbox()


def test_category_predicate_quotes_categories():
    pred = _category_predicate()
    assert "categories.primary IN" in pred
    assert "'coffee_shop'" in pred
    assert "'cafe'" in pred


def test_category_predicate_safe_against_basic_injection():
    """The category list is a module constant, not user input. Sanity check
    that nothing exotic slipped in."""
    pred = _category_predicate()
    assert ";" not in pred
    assert "--" not in pred
    assert "/*" not in pred


def _make_overture_temp(conn, **overrides):
    cols = {
        "id": "'s1'",
        "name": "'New Name'",
        "longitude": "10.0",
        "latitude": "20.0",
        "address": "'1 Main St'",
        "city": "'NYC'",
        "country": "'US'",
        "website": "'http://example.com'",
        "confidence": "0.9",
    }
    cols.update(overrides)
    select = ", ".join(f"{v} AS {k}" for k, v in cols.items())
    conn.execute(f"CREATE OR REPLACE TEMP TABLE _overture_shops AS SELECT {select}")


def test_merge_preserves_curated_enrichment(db):
    """Re-ingesting an existing shop refreshes source fields but must preserve
    scraped/enriched columns and created_at. Regression for INSERT OR REPLACE."""
    db.execute(
        "INSERT INTO shop_shops (id, name, latitude, longitude, rating, "
        "roasts_in_house, description, created_at) VALUES "
        "('s1', 'Old Name', 1.0, 2.0, 4.5, true, 'Lovely scraped bio', "
        "TIMESTAMP '2024-01-01 00:00:00')"
    )
    _make_overture_temp(db)
    _merge_shops(db)
    row = db.execute(
        "SELECT name, latitude, longitude, rating, roasts_in_house, description, "
        "created_at FROM shop_shops WHERE id = 's1'"
    ).fetchone()
    assert row[0] == "New Name"  # source field refreshed
    assert (row[1], row[2]) == (20.0, 10.0)  # coordinates refreshed
    assert row[3] == 4.5  # rating preserved
    assert row[4] is True  # roasts_in_house preserved
    assert row[5] == "Lovely scraped bio"  # description preserved
    assert str(row[6]) == "2024-01-01 00:00:00"  # created_at preserved


def test_merge_inserts_new_shop_with_null_enrichment(db):
    _make_overture_temp(db, id="'s2'", name="'Brand New'")
    _merge_shops(db)
    row = db.execute("SELECT name, rating, description FROM shop_shops WHERE id = 's2'").fetchone()
    assert row == ("Brand New", None, None)
