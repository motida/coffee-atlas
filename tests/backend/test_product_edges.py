"""Tests for product edge resolution — content matching and derived chains."""

from backend.ingest.product_edges import resolve_product_edges


def _seed(db):
    db.execute(
        "INSERT INTO org_countries (id, name) VALUES ('c-et','Ethiopia'),('c-co','Colombia')"
    )
    db.execute(
        "INSERT INTO org_regions (id, name, country_id) VALUES ('r-yir','Yirgacheffe','c-et')"
    )
    # WCR spelling "Geisha"; products write "Gesha" — exercises the alias.
    db.execute("INSERT INTO var_varieties (id, name) VALUES ('v-ge','Geisha'),('v-bo','Bourbon')")
    # Flavor: a root category + leaves. Root 'Fruity' and stopword 'Honey' must
    # not produce edges; leaves 'Jasmine'/'Cherry' must.
    db.execute(
        """INSERT INTO flav_attributes (id, name, parent_id) VALUES
           ('f-fruity','Fruity',NULL),
           ('f-jasmine','Jasmine','f-fruity'),
           ('f-honey','Honey','f-fruity'),
           ('f-cherry','Cherry','f-fruity')"""
    )
    db.execute(
        "INSERT INTO roast_profiles (id, name, roast_level) VALUES ('rpf-l','Light','light')"
    )
    db.execute(
        "INSERT INTO roast_roasters (id, name, website) VALUES ('ro-verve','Verve','https://www.vervecoffee.com')"
    )
    db.execute(
        """INSERT INTO prod_products (id, name, roaster_id, roast_level, description) VALUES
           ('p1','Ethiopia Yirgacheffe Gesha','ro-verve','light','Fruity notes of jasmine and honey'),
           ('p2','Colombia Bourbon','ro-verve',NULL,'Bright cherry')"""
    )
    # One shop whose domain matches Verve, one that doesn't.
    db.execute(
        """INSERT INTO shop_shops (id, name, website) VALUES
           ('s-match','Verve SF','https://vervecoffee.com/pages/sf'),
           ('s-other','Random Cafe','https://example.com')"""
    )


def test_content_edges(db):
    _seed(db)
    c = resolve_product_edges(db)
    assert c.product_country == 2  # p1→Ethiopia, p2→Colombia
    assert c.product_region == 1  # p1→Yirgacheffe
    assert c.product_variety == 2  # p1→Geisha (via "Gesha" alias), p2→Bourbon
    assert c.product_roast == 1  # p1 light → Light profile


def test_flavor_excludes_root_and_stopwords(db):
    _seed(db)
    resolve_product_edges(db)
    flavors_p1 = {
        r[0]
        for r in db.execute(
            "SELECT flavor_id FROM edges_product_flavor WHERE product_id='p1'"
        ).fetchall()
    }
    assert flavors_p1 == {"f-jasmine"}  # 'Fruity' (root) and 'Honey' (stopword) excluded
    flavors_p2 = {
        r[0]
        for r in db.execute(
            "SELECT flavor_id FROM edges_product_flavor WHERE product_id='p2'"
        ).fetchall()
    }
    assert flavors_p2 == {"f-cherry"}


def test_derived_edges(db):
    _seed(db)
    c = resolve_product_edges(db)
    assert c.roaster_product == 2  # both products are Verve's
    assert c.shop_roaster == 1  # only the domain-matching shop
    assert c.shop_product == 2  # matching shop serves both Verve products
    assert c.shop_variety == 2  # via p1→Geisha, p2→Bourbon


def test_non_matching_shop_excluded(db):
    _seed(db)
    resolve_product_edges(db)
    shops = {r[0] for r in db.execute("SELECT DISTINCT shop_id FROM edges_shop_roaster").fetchall()}
    assert shops == {"s-match"}


def test_idempotent(db):
    _seed(db)
    first = resolve_product_edges(db)
    second = resolve_product_edges(db)
    assert first == second
    assert db.execute("SELECT COUNT(*) FROM edges_product_country").fetchone()[0] == 2
