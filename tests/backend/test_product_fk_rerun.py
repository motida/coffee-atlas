"""Regression for PR #19 review blocker: the product domain FK-references the
shared parent tables (var_varieties, flav_attributes, org_*, roast_*), so a
`pipeline --all` re-run must be able to DELETE those parents without hitting a
ConstraintException. Guards clear_products() (used by roasting_loader) and the
per-parent edge clears added to the lexicon/varieties/cqi loaders.
"""

import pytest

from backend.ingest.products_loader import PRODUCT_TABLES, clear_products


def _seed_full(db):
    db.execute("INSERT INTO roast_roasters (id, name, website) VALUES ('ro', 'R', 'https://r.com')")
    db.execute(
        "INSERT INTO roast_profiles (id, name, roast_level) VALUES ('rpf', 'Light', 'light')"
    )
    db.execute("INSERT INTO var_varieties (id, name) VALUES ('v', 'Gesha')")
    db.execute("INSERT INTO flav_attributes (id, name, parent_id) VALUES ('f', 'Jasmine', 'root')")
    db.execute("INSERT INTO org_countries (id, name) VALUES ('c', 'Ethiopia')")
    db.execute("INSERT INTO org_regions (id, name) VALUES ('rg', 'Guji')")
    db.execute("INSERT INTO shop_shops (id, name, website) VALUES ('s', 'S', 'https://r.com')")
    db.execute("INSERT INTO prod_products (id, name, roaster_id) VALUES ('p', 'P', 'ro')")
    db.execute(
        "INSERT INTO edges_product_variety (id, product_id, variety_id) VALUES ('e1','p','v')"
    )
    db.execute(
        "INSERT INTO edges_product_region (id, product_id, region_id) VALUES ('e2','p','rg')"
    )
    db.execute(
        "INSERT INTO edges_product_country (id, product_id, country_id) VALUES ('e3','p','c')"
    )
    db.execute("INSERT INTO edges_product_flavor (id, product_id, flavor_id) VALUES ('e4','p','f')")
    db.execute(
        "INSERT INTO edges_product_roast (id, product_id, profile_id) VALUES ('e5','p','rpf')"
    )
    db.execute("INSERT INTO edges_shop_product (id, shop_id, product_id) VALUES ('e6','s','p')")
    db.execute(
        "INSERT INTO edges_roaster_product (id, roaster_id, product_id) VALUES ('e7','ro','p')"
    )
    db.execute("INSERT INTO edges_shop_roaster (id, shop_id, roaster_id) VALUES ('e8','s','ro')")


def test_clear_products_full_teardown_then_parents_deletable(db):
    _seed_full(db)
    clear_products(db)
    for table in PRODUCT_TABLES:
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    # roasting_loader calls clear_products before these; they must not raise.
    db.execute("DELETE FROM roast_roasters")
    db.execute("DELETE FROM roast_profiles")


@pytest.mark.parametrize(
    "parent, edge",
    [
        ("var_varieties", "edges_product_variety"),
        ("flav_attributes", "edges_product_flavor"),
        ("org_regions", "edges_product_region"),
        ("org_countries", "edges_product_country"),
        ("roast_profiles", "edges_product_roast"),
    ],
)
def test_parent_deletable_after_its_product_edge_cleared(db, parent, edge):
    # Mirrors each parent loader's responsibility: clear the product edge that
    # references the parent, then DELETE FROM <parent> must succeed.
    _seed_full(db)
    db.execute(f"DELETE FROM {edge}")
    db.execute(f"DELETE FROM {parent}")  # raised ConstraintException before the fix
