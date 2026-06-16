EXPECTED_TABLES = [
    "var_varieties",
    "org_countries",
    "org_regions",
    "org_farms",
    "proc_methods",
    "roast_profiles",
    "roast_roasters",
    "flav_attributes",
    "dist_importers",
    "dist_trade_routes",
    "dist_certifications",
    "shop_shops",
    "prod_products",
    "edges_variety_flavor",
    "edges_country_variety",
    "edges_region_variety",
    "edges_farm_variety",
    "edges_shop_variety",
    "edges_variety_processing",
    "edges_roast_variety",
    "edges_processing_flavor",
    "edges_country_region",
    "edges_region_farm",
    "edges_product_variety",
    "edges_product_region",
    "edges_product_country",
    "edges_product_flavor",
    "edges_product_roast",
    "edges_shop_product",
    "edges_roaster_product",
    "edges_shop_roaster",
    "ontology_triples",
]


def test_all_tables_created(db):
    tables = [row[0] for row in db.execute("SHOW TABLES").fetchall()]
    for expected in EXPECTED_TABLES:
        assert expected in tables, f"Missing table: {expected}"


def test_table_count(db):
    tables = db.execute("SHOW TABLES").fetchall()
    assert len(tables) == len(EXPECTED_TABLES)
