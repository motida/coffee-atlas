"""Tests for the products loader: coffee classification, roaster attribution
(by site, not vendor), dedupe, and FK-safe insertion into prod_products."""

from typing import Any

from backend.ingest.products_loader import classify_coffee, load_products


def _rec(site: str, vendor: str, title: str, product_type: str | None, **kw: Any) -> dict[str, Any]:
    return {
        "site": site,
        "roaster": vendor,
        "title": title,
        "product_type": product_type,
        "tags": kw.get("tags", []),
        "price": kw.get("price"),
        "net_weight_grams": kw.get("net_weight_grams"),
        "roast_level": kw.get("roast_level"),
        "process": kw.get("process"),
        "is_blend": kw.get("is_blend", False),
        "url": kw.get("url"),
        "description": kw.get("description", ""),
    }


VERVE = "https://www.vervecoffee.com"
ONYX = "https://onyxcoffeelab.com"


def _records() -> list[dict[str, Any]]:
    return [
        _rec(VERVE, "Verve Coffee", "Ethiopia Ayla", "Coffee", price=28.0),
        _rec(VERVE, "Verve Coffee", "Pride Blend", "Coffee", is_blend=True, price=24.0),
        _rec(VERVE, "Verve Coffee", "Street Level", "Coffee", price=18.0),
        _rec(VERVE, "Fellow", "Stagg EKG Kettle", "Equipment"),  # dropped
        _rec(VERVE, "Rishi", "Jasmine Green", "Tea"),  # dropped
        _rec(ONYX, "Onyx Coffee Lab", "Geometry", "Coffee", price=22.0),
        _rec(ONYX, "Onyx Coffee Lab", "Southern Weather", "Coffee", is_blend=True),
    ]


def test_classify_coffee_units():
    assert classify_coffee("Ethiopia Natural", "Coffee", ["Natural"]) is True
    assert classify_coffee("El Burro Gesha", "Retail SO", []) is True
    assert classify_coffee("Cold Brew Concentrate", "Cold Brew", []) is True
    assert classify_coffee("English Breakfast", "Tea", []) is False
    assert classify_coffee("Stagg Kettle", "Equipment", []) is False
    assert classify_coffee("Logo Mug", "Merchandise", []) is False
    assert classify_coffee("Brew Guide", "Brewing", []) is False


def test_load_counts_and_drops(db):
    counts = load_products(_records(), db)
    assert counts.products == 5  # 3 Verve + 2 Onyx coffees
    assert counts.dropped_non_coffee == 2  # kettle + tea
    assert counts.roasters == 2


def test_roaster_attributed_by_site_modal_vendor(db):
    load_products(_records(), db)
    names = {r[0] for r in db.execute("SELECT name FROM roast_roasters").fetchall()}
    # The Fellow/Rishi vendors are dropped as non-coffee, so they never become
    # roasters; each site resolves to its coffee vendor.
    assert names == {"Verve Coffee", "Onyx Coffee Lab"}
    site = db.execute("SELECT website FROM roast_roasters WHERE name = 'Verve Coffee'").fetchone()
    assert site[0] == VERVE


def test_products_link_to_valid_roaster(db):
    load_products(_records(), db)
    orphans = db.execute(
        """
        SELECT COUNT(*) FROM prod_products p
        LEFT JOIN roast_roasters r ON p.roaster_id = r.id
        WHERE r.id IS NULL
        """
    ).fetchone()[0]
    assert orphans == 0
    verve_n = db.execute(
        """
        SELECT COUNT(*) FROM prod_products p
        JOIN roast_roasters r ON p.roaster_id = r.id
        WHERE r.name = 'Verve Coffee'
        """
    ).fetchone()[0]
    assert verve_n == 3


def test_idempotent_and_dedupe(db):
    recs = _records()
    load_products(recs, db)
    # Re-running replaces, not appends; a duplicate (same site+title) collapses.
    recs.append(_rec(VERVE, "Verve Coffee", "Ethiopia Ayla", "Coffee", price=29.0))
    counts = load_products(recs, db)
    assert counts.products == 5
    assert db.execute("SELECT COUNT(*) FROM prod_products").fetchone()[0] == 5


def test_roasting_roasters_not_clobbered(db):
    # A roaster from another domain (e.g. the roasting seed) must survive a
    # products load — roasters are inserted ON CONFLICT DO NOTHING.
    db.execute("INSERT INTO roast_roasters (id, name) VALUES ('seed-1', 'Seed Roaster')")
    load_products(_records(), db)
    assert db.execute("SELECT COUNT(*) FROM roast_roasters WHERE id = 'seed-1'").fetchone()[0] == 1


def test_existing_roaster_reused_not_duplicated(db):
    # A roaster name that already exists (e.g. from the roasting seed) must be
    # reused, not duplicated under a fresh products-namespace id.
    db.execute("INSERT INTO roast_roasters (id, name) VALUES ('seed-verve', 'Verve Coffee')")
    load_products(_records(), db)
    rows = db.execute("SELECT id FROM roast_roasters WHERE name = 'Verve Coffee'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "seed-verve"
    linked = db.execute(
        "SELECT COUNT(*) FROM prod_products WHERE roaster_id = 'seed-verve'"
    ).fetchone()[0]
    assert linked == 3


def test_roaster_reuse_is_case_insensitive(db):
    # vendor differs only in case/whitespace from a previously-seeded roaster.
    db.execute("INSERT INTO roast_roasters (id, name) VALUES ('seed-verve', 'Verve Coffee')")
    load_products([_rec(VERVE, "verve  coffee", "Ethiopia Ayla", "Coffee", price=28.0)], db)
    rows = db.execute("SELECT id FROM roast_roasters WHERE name ILIKE 'verve coffee'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "seed-verve"


def test_roaster_dedup_strips_generic_suffix(db):
    # The Stumptown bug: a seeded "Stumptown Coffee Roasters" must absorb a
    # scraped "Stumptown Coffee" rather than spawn a second node.
    db.execute(
        "INSERT INTO roast_roasters (id, name) VALUES ('seed-stump', 'Stumptown Coffee Roasters')"
    )
    load_products(
        [
            _rec(
                "https://www.stumptowncoffee.com",
                "Stumptown Coffee",
                "Hair Bender",
                "Coffee",
                price=18.0,
            )
        ],
        db,
    )
    rows = db.execute("SELECT id FROM roast_roasters WHERE name ILIKE 'stumptown%'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "seed-stump"
    assert (
        db.execute("SELECT COUNT(*) FROM prod_products WHERE roaster_id = 'seed-stump'").fetchone()[
            0
        ]
        == 1
    )


def test_roaster_dedup_strips_leading_the(db):
    db.execute("INSERT INTO roast_roasters (id, name) VALUES ('seed-cc', 'The Coffee Collective')")
    load_products(
        [_rec("https://coffeecollective.dk", "Coffee Collective", "Kieni", "Coffee", price=20.0)],
        db,
    )
    rows = db.execute(
        "SELECT id FROM roast_roasters WHERE name ILIKE '%coffee collective%'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "seed-cc"


def test_vendor_alias_renames_roaster(db):
    # birdrockcoffee.com's Shopify vendor is the abbreviation "BRCR Roasting";
    # the alias maps it to the friendly name on load.
    load_products(
        [_rec("https://www.birdrockcoffee.com", "BRCR Roasting", "Honduras Las Capucas", "Coffee")],
        db,
    )
    names = {r[0] for r in db.execute("SELECT name FROM roast_roasters").fetchall()}
    assert names == {"Bird Rock Coffee Roasters"}


def test_vendor_alias_reuses_existing_canonical_row(db):
    # With the friendly name already present, an aliased re-scrape must reuse it
    # (not spawn a "BRCR Roasting" duplicate).
    db.execute(
        "INSERT INTO roast_roasters (id, name) VALUES ('seed-brcr', 'Bird Rock Coffee Roasters')"
    )
    load_products(
        [_rec("https://www.birdrockcoffee.com", "BRCR Roasting", "Honduras Las Capucas", "Coffee")],
        db,
    )
    rows = db.execute("SELECT id FROM roast_roasters WHERE name ILIKE '%bird rock%'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "seed-brcr"


def test_site_override_names_roaster_when_vendor_is_tasting_notes(db):
    # catandcloud.com files each coffee's tasting notes as the Shopify vendor, so
    # modal-vendor attribution can't recover "Cat & Cloud" once merch is filtered.
    # The per-site override must name the roaster regardless of the junk vendors.
    cc = "https://www.catandcloud.com"
    load_products(
        [
            _rec(cc, "Lavender • Raspberry • Green Tea", "Brazil Cavaquinho Natural", "Coffee"),
            _rec(cc, "Cherry • Honey • Nougat", "Ethiopia Kercha Natural", "Coffee"),
            _rec(cc, "Cat & Cloud", "Birthday Shirt", None, tags=["merch"]),  # dropped
        ],
        db,
    )
    rows = db.execute(
        "SELECT r.name, count(p.id) FROM roast_roasters r "
        "JOIN prod_products p ON p.roaster_id = r.id GROUP BY r.name"
    ).fetchall()
    assert rows == [("Cat & Cloud", 2)]


def test_site_override_reuses_existing_roaster_row(db):
    # The override name must collapse onto an existing "Cat & Cloud" row, not
    # spawn a duplicate under a fresh id.
    db.execute("INSERT INTO roast_roasters (id, name) VALUES ('seed-cc', 'Cat & Cloud')")
    load_products(
        [_rec("https://www.catandcloud.com", "Juicy • Sweet • Clean", "Peru The Andes", "Coffee")],
        db,
    )
    rows = db.execute("SELECT id FROM roast_roasters WHERE name = 'Cat & Cloud'").fetchall()
    assert rows == [("seed-cc",)]


def test_canon_name_unit():
    from backend.ingest.products_loader import _canon_name

    assert _canon_name("Stumptown Coffee") == _canon_name("Stumptown Coffee Roasters")
    assert _canon_name("The Coffee Collective") == _canon_name("Coffee Collective")
    assert _canon_name("Black & White Coffee Roasters") == "black white"
    assert _canon_name("Onyx Coffee Lab") == "onyx"
    assert _canon_name("Verve Coffee") != _canon_name("Onyx Coffee Lab")  # stay distinct
    assert _canon_name("Coffee") == "coffee"  # never collapses to empty


def test_classify_keeps_filter_roast_coffee():
    # "Filter" is a roast designation, not equipment — must survive.
    assert classify_coffee("Ethiopia Guji Filter", "Coffee", []) is True
    assert classify_coffee("Three Africas Filter", None, []) is True
    # An actual filter accessory still drops (brand/sock token catches it).
    assert classify_coffee("Coffee Sock Reusable Travel Filter", "Coffee Filter", []) is False


def test_classify_drops_gifts_plural():
    assert classify_coffee("Holiday Gifts", "Gifts", []) is False


def test_classify_drops_cafe_supplies_and_merch():
    for junk in [
        "Milk Pitcher 500ml",
        "Bamboo Tongs",
        "Bar Whisk",
        "Group Head Brush",
        "Cup Lids - Hot",
        "Cup Sleeves",
        "Cambro Measuring Cup",
        "Shot Glass",
        "Rinza Tablets",
        "Washed Trucker Cap",
        "Denim Poodle Cap",
        "Summer Fun Beach Towel",
        "To-Go Barista Box",
        "Land Chocolate - 72% El Salvador Dark",
        "Askinosie Chocolate",
        "Matcha Latte RTD",
        "Public Cupping",
        "The Cupping Table",
        "Ruby Cupping Spoon",
    ]:
        assert classify_coffee(junk, None, []) is False, junk


def test_classify_keeps_chocolate_and_horchata_cold_brew():
    # Non-coffee beverages drop, but a cold brew is a coffee drink — keep it.
    assert classify_coffee("Chocolate Cold Brew with Oatly", "Coffee", []) is True
    assert classify_coffee("Horchata Cold Brew with Oatly", None, []) is True
    assert classify_coffee("Land Drinking Chocolate - Pouch", None, []) is False


def test_classify_keeps_coffees_with_collision_words():
    # Real coffees that contain a substring of a junk term must survive.
    assert classify_coffee("Brazil | #1 Cup of Excellence", "Coffee", []) is True
    assert classify_coffee("Honduras Las Capucas", "Coffee", []) is True  # not "cap"
    assert classify_coffee("El Matazano Pacamara Washed", "Coffee", []) is True  # not "mat"


def test_classify_drops_records_and_merch_by_type():
    # Roaster stores that double as record shops / merch (e.g. tandemcoffee.com:
    # 159 "Vinyl", 25 "Wearables", 6 "Kits") — the merchant's product_type is the
    # decisive signal even when the title carries no junk keyword.
    assert classify_coffee("Radiohead - OK Computer", "Vinyl", ["vinyl"]) is False
    assert classify_coffee("A Tribe Called Quest - Midnight Marauders", "Records", []) is False
    assert classify_coffee("Souvenir Pennant", "Wearables", []) is False  # title alone is clean
    assert classify_coffee("Holiday Pack", "Kits", []) is False
    assert classify_coffee("Field Recording Vol. 1", "Music", []) is False


def test_classify_drops_records_by_tag_when_type_blank():
    # Many records carry no product_type but a 'vinyl' tag — must still drop, even
    # though Shopify also auto-tags them into a 'coffees' collection.
    assert (
        classify_coffee(
            "Fela Kuti - Sorrow, Tears And Blood",
            None,
            ["cybermonday", "POS", "vinyl", "meta-related-collection-coffees"],
        )
        is False
    )
    assert classify_coffee("Some Tee", None, ["merch"]) is False
    # A real coffee tagged into a gift/subscription collection must NOT be dropped
    # by the tag screen (those words are type-only, never screened on tags).
    assert classify_coffee("Kenya Nyeri AA", "Coffee", ["gifts", "subscription"]) is True
    # A coffee product_type wins over a stray 'merch' tag (Cat & Cloud files its
    # "Instant Coffee 6 Pack" with product_type "Coffee" but also a 'merch' tag).
    assert classify_coffee("Instant Coffee 6 Pack", "Coffee", ["blends", "merch"]) is True
    # ...but a genuine merch item with no coffee product_type still drops.
    assert classify_coffee("Kitty Litter Crop", None, ["clothing", "crop top", "merch"]) is False


def test_classify_keeps_instant_coffee_type():
    # "Instant" is a coffee product_type (instant coffee) — must NOT be dropped
    # by the records/merch additions.
    assert classify_coffee("Instant Ethiopia Single Serve", "Instant", []) is True
    # A coffee whose title coincidentally reads like a record name still survives
    # as long as its type is coffee — the new terms are type-only in the loader.
    assert classify_coffee("Long Player Blend", "Coffee", []) is True
    assert classify_coffee("Instant Coffee - Galactic Standard", "Coffee", []) is True


def test_empty_records_no_crash(db):
    counts = load_products([], db)
    assert (counts.products, counts.roasters, counts.dropped_non_coffee) == (0, 0, 0)
    assert db.execute("SELECT COUNT(*) FROM prod_products").fetchone()[0] == 0
