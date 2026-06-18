"""Tests for the specialty-shop heuristic.

Covers the chain classifier (backend/ingest/shop_scrapers/chains.py) and the
score/flag computation (backend/ingest/shop_specialty.py).
"""

from __future__ import annotations

import duckdb

from backend.ingest.shop_scrapers.chains import is_nonspecialty_chain, is_specialty_chain
from backend.ingest.shop_specialty import compute_specialty


# --- Chain classifier ---


def test_specialty_chain_matches_with_and_without_suffix():
    assert is_specialty_chain("Blue Bottle")
    assert is_specialty_chain("Blue Bottle Coffee")
    assert is_specialty_chain("intelligentsia coffee")


def test_nonspecialty_chain_matches_franchise_variants():
    assert is_nonspecialty_chain("Starbucks")
    assert is_nonspecialty_chain("Starbucks Reserve")
    assert is_nonspecialty_chain("Peet's Coffee & Tea")


def test_specialty_chain_overrides_blocklist():
    # A specialty chain is never classified as a non-specialty chain.
    assert is_specialty_chain("La Colombe")
    assert not is_nonspecialty_chain("La Colombe")


def test_word_boundary_avoids_false_positives():
    # "Costa Coffee" is blocklisted; an unrelated "Costa Rica" roaster is not.
    assert is_nonspecialty_chain("Costa Coffee")
    assert not is_nonspecialty_chain("Costa Rica Coffee Roasters")
    assert not is_specialty_chain("Independent Corner Cafe")


# --- Score + flag computation ---


def _insert_shop(conn: duckdb.DuckDBPyConnection, shop_id: str, name: str, **cols: object) -> None:
    keys = ["id", "name", *cols.keys()]
    placeholders = ", ".join("?" for _ in keys)
    conn.execute(
        f"INSERT INTO shop_shops ({', '.join(keys)}) VALUES ({placeholders})",
        [shop_id, name, *cols.values()],
    )


def test_compute_specialty_flags_by_signal(db):
    _insert_shop(db, "chain_no", "Starbucks", website="https://starbucks.com")
    _insert_shop(db, "chain_yes", "Blue Bottle Coffee", website="https://bluebottlecoffee.com")
    _insert_shop(db, "desc", "Pour & Co", description="Specialty single-origin pour-over bar")
    _insert_shop(db, "roastshop", "Roastery X", roasts_in_house=True)
    _insert_shop(db, "rated", "Highly Rated Cafe", rating=4.6)
    _insert_shop(db, "weak", "Generic Cafe", website="https://generic.example")
    _insert_shop(db, "nosignal", "Bare Cafe")

    # A shop matched to a curated roaster via edges_shop_roaster.
    _insert_shop(db, "curated", "Roaster-Owned Cafe", website="https://onyx.example")
    db.execute("INSERT INTO roast_roasters (id, name) VALUES ('r1', 'Onyx Coffee Lab')")
    db.execute(
        "INSERT INTO edges_shop_roaster (id, shop_id, roaster_id) VALUES ('e1', 'curated', 'r1')"
    )

    counts = compute_specialty(conn=db)

    flags = dict(db.execute("SELECT id, is_specialty FROM shop_shops").fetchall())
    assert flags["chain_no"] is False  # non-specialty chain → excluded
    assert flags["chain_yes"] is True  # specialty chain → kept
    assert flags["desc"] is True  # scraper-vetted description
    assert flags["roastshop"] is True  # roasts in house
    assert flags["rated"] is True  # rating over threshold
    assert flags["curated"] is True  # curated-roaster match
    assert flags["weak"] is False  # website alone is not enough
    assert flags["nosignal"] is False  # nothing → excluded

    assert counts.total == 8
    assert counts.specialty == 5


def test_compute_specialty_is_idempotent(db):
    _insert_shop(db, "s1", "Blue Bottle", website="https://bluebottlecoffee.com")
    first = compute_specialty(conn=db)
    second = compute_specialty(conn=db)
    assert first == second
    score = db.execute("SELECT specialty_score FROM shop_shops WHERE id = 's1'").fetchone()
    assert score is not None and score[0] == 1.0


def test_compute_specialty_handles_empty_shops(db):
    counts = compute_specialty(conn=db)
    assert counts == counts.__class__(total=0, specialty=0)
