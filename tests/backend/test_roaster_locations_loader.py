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
    _country_name,
    _iso_to_name,
    backfill_product_currency,
    backfill_roaster_locations,
    derive_roaster_locations_from_shops,
)

REAL_MAP = json.loads(Path(DEFAULT_SOURCE).read_text(encoding="utf-8"))["locations"]


def _insert_roaster(db, rid, name, location=None, website=None):
    db.execute(
        "INSERT INTO roast_roasters (id, name, location, website) VALUES (?, ?, ?, ?)",
        [rid, name, location, website],
    )


def _insert_shop(db, sid, name, website, city, country):
    db.execute(
        "INSERT INTO shop_shops (id, name, website, city, country) VALUES (?, ?, ?, ?, ?)",
        [sid, name, website, city, country],
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


# --- Source 2: derive location from the roaster's own Overture shop ---


def test_iso_to_name_maps_real_codes():
    iso = _iso_to_name()
    assert iso["US"] == "United States"
    assert iso["GB"] == "United Kingdom"


def test_country_name_normalizes_code_and_passes_names_through():
    iso = _iso_to_name()
    assert _country_name("US", iso) == "United States"
    assert _country_name("us", iso) == "United States"  # case-insensitive code
    assert _country_name("United States", iso) == "United States"  # already a name
    assert _country_name("", iso) is None
    assert _country_name(None, iso) is None


def test_derive_fills_blank_from_matching_shop_host(db):
    # Roaster website and shop website share a host despite www/path differences.
    _insert_roaster(db, "r1", "Verve", website="https://www.vervecoffee.com")
    _insert_shop(db, "s1", "Verve Cafe", "https://vervecoffee.com/pages/visit", "Santa Cruz", "US")

    counts = derive_roaster_locations_from_shops(conn=db)

    assert counts.derived == 1
    loc = db.execute("SELECT location FROM roast_roasters WHERE id = 'r1'").fetchone()[0]
    assert loc == "Santa Cruz, United States"  # ISO code normalized to full name


def test_derive_uses_country_only_when_shop_has_no_city(db):
    _insert_roaster(db, "r1", "Square Mile", website="https://squaremilecoffee.com")
    _insert_shop(db, "s1", "SM", "https://squaremilecoffee.com", None, "GB")

    derive_roaster_locations_from_shops(conn=db)

    loc = db.execute("SELECT location FROM roast_roasters WHERE id = 'r1'").fetchone()[0]
    assert loc == "United Kingdom"


def test_derive_picks_dominant_city_and_country_across_shops(db):
    _insert_roaster(db, "r1", "Chainy", website="https://chainy.com")
    _insert_shop(db, "s1", "A", "https://chainy.com", "Portland", "US")
    _insert_shop(db, "s2", "B", "https://chainy.com", "Portland", "US")
    _insert_shop(db, "s3", "C", "https://chainy.com", "Seattle", "US")

    derive_roaster_locations_from_shops(conn=db)

    loc = db.execute("SELECT location FROM roast_roasters WHERE id = 'r1'").fetchone()[0]
    assert loc == "Portland, United States"


def test_derive_does_not_overwrite_by_default_but_overwrite_flag_does(db):
    _insert_roaster(db, "r1", "Seeded", "Oslo, Norway", website="https://seeded.com")
    _insert_shop(db, "s1", "Shop", "https://seeded.com", "Wrong City", "US")

    kept = derive_roaster_locations_from_shops(conn=db)
    assert kept.derived == 0 and kept.already_set == 1
    assert (
        db.execute("SELECT location FROM roast_roasters WHERE id='r1'").fetchone()[0]
        == "Oslo, Norway"
    )

    forced = derive_roaster_locations_from_shops(conn=db, overwrite=True)
    assert forced.derived == 1
    assert (
        db.execute("SELECT location FROM roast_roasters WHERE id='r1'").fetchone()[0]
        == "Wrong City, United States"
    )


def test_derive_leaves_unmatched_roasters_untouched_and_inserts_nothing(db):
    _insert_roaster(db, "r1", "Online Only", website="https://noshop.com")
    _insert_shop(db, "s1", "Elsewhere", "https://other.com", "Berlin", "DE")

    counts = derive_roaster_locations_from_shops(conn=db)

    assert counts.derived == 0 and counts.unmatched == 1
    assert db.execute("SELECT location FROM roast_roasters WHERE id='r1'").fetchone()[0] is None
    # read-only: no rows inserted/deleted in either table
    assert db.execute("SELECT COUNT(*) FROM roast_roasters").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM shop_shops").fetchone()[0] == 1


def test_curated_then_derive_precedence(db, tmp_path):
    # The pipeline runs curated first, then derive. A roaster the curated map
    # names must keep that value even though a shop on its host says otherwise.
    _insert_roaster(db, "r1", "Curated Roaster", website="https://curated.com")
    _insert_shop(db, "s1", "Shop", "https://curated.com", "Shop City", "US")
    src = _write_map(tmp_path, {"Curated Roaster": "Oslo, Norway"})

    curated = backfill_roaster_locations(conn=db, source_path=src)
    derived = derive_roaster_locations_from_shops(conn=db)

    assert curated.updated == 1
    assert derived.already_set == 1 and derived.derived == 0
    loc = db.execute("SELECT location FROM roast_roasters WHERE id='r1'").fetchone()[0]
    assert loc == "Oslo, Norway"


# --------------------------------------------------------------------------
# Product currency from roaster location
# --------------------------------------------------------------------------


def _insert_product(db, pid, roaster_id, price=None, currency=None):
    db.execute(
        "INSERT INTO prod_products (id, name, roaster_id, price, currency) VALUES (?, ?, ?, ?, ?)",
        [pid, f"Coffee {pid}", roaster_id, price, currency],
    )


def test_currency_backfilled_from_roaster_country(db):
    _insert_roaster(db, "r-no", "Oslo Roaster", "Oslo, Norway")
    _insert_roaster(db, "r-jp", "Tokyo Roaster", "Tokyo, Japan")
    _insert_product(db, "p1", "r-no", price=189.0)
    _insert_product(db, "p2", "r-jp", price=1200.0)

    assert backfill_product_currency(conn=db) == 2
    rows = dict(db.execute("SELECT id, currency FROM prod_products").fetchall())
    assert rows == {"p1": "NOK", "p2": "JPY"}


def test_currency_backfill_never_overwrites_scraper_value(db):
    # A scraper-declared currency is authoritative — the location fallback must
    # not clobber it even when it disagrees with the roaster's country.
    _insert_roaster(db, "r1", "Oslo Roaster", "Oslo, Norway")
    _insert_product(db, "p1", "r1", price=20.0, currency="EUR")

    assert backfill_product_currency(conn=db) == 0
    assert db.execute("SELECT currency FROM prod_products WHERE id='p1'").fetchone()[0] == "EUR"


def test_currency_backfill_skips_unpriced_unknown_and_unlocated(db):
    _insert_roaster(db, "r-no", "Oslo Roaster", "Oslo, Norway")
    _insert_roaster(db, "r-none", "Nowhere Roaster")  # location NULL
    _insert_roaster(db, "r-etla", "Andean Roaster", "Cusco, Peru")  # unmapped country
    _insert_product(db, "p1", "r-no")  # no price → no currency to denominate
    _insert_product(db, "p2", "r-none", price=15.0)
    _insert_product(db, "p3", "r-etla", price=45.0)

    assert backfill_product_currency(conn=db) == 0
    currencies = [r[0] for r in db.execute("SELECT currency FROM prod_products").fetchall()]
    assert currencies == [None, None, None]


def test_currency_backfill_idempotent(db):
    _insert_roaster(db, "r1", "Oslo Roaster", "Oslo, Norway")
    _insert_product(db, "p1", "r1", price=189.0)

    assert backfill_product_currency(conn=db) == 1
    assert backfill_product_currency(conn=db) == 0  # second run touches nothing
    assert db.execute("SELECT currency FROM prod_products WHERE id='p1'").fetchone()[0] == "NOK"
