"""Tests for the CQI cupping data loader."""

from pathlib import Path

import pytest

from backend.ingest.cqi_loader import load_cqi_data

ARABICA = Path("data/raw/cqi_arabica.csv")
ROBUSTA = Path("data/raw/cqi_robusta.csv")

needs_data = pytest.mark.skipif(
    not ARABICA.exists(),
    reason="CQI source CSVs not present in data/raw/",
)


@pytest.fixture
def fixture_csvs(tmp_path: Path) -> tuple[Path, Path]:
    arabica = tmp_path / "arabica.csv"
    arabica.write_text(
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters","Variety"\n'
        '"Ethiopia","Yirgacheffe","Kochere","Washed / Wet",1900,"Gesha"\n'
        '"Ethiopia","Yirgacheffe","Kochere","Washed / Wet",1900,"Gesha"\n'
        '"Ethiopia","Sidamo","Bensa","Natural / Dry",2000,"Bourbon"\n'
        '"Colombia","Huila","La Esperanza","Washed / Wet",1700,"Caturra"\n'
        '"Colombia",,"Anonymous","Other",,"Other"\n'
        ',"Unknown","Ghost","Other",1500,"Typica"\n'
        '"Brazil","Cerrado","Fazenda X","Natural / Dry",1100,"Marigojipe"\n'
    )
    robusta = tmp_path / "robusta.csv"
    robusta.write_text(
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters","Variety"\n'
        '"Vietnam","Central Highlands","Buon Ma Thuot","Natural / Dry",600,""\n'
    )
    return arabica, robusta


@pytest.fixture
def seeded_db(db):
    """db fixture with a handful of WCR varieties so the matcher has targets."""
    db.executemany(
        "INSERT INTO var_varieties (id, name) VALUES (?, ?)",
        [
            ("vid-bourbon", "Bourbon"),
            ("vid-caturra", "Caturra"),
            ("vid-typica", "Typica"),
            ("vid-geisha", "Geisha (Panama)"),
            ("vid-maragogipe", "Maragogipe"),
        ],
    )
    return db


def test_dedupes_and_normalizes(db, fixture_csvs):
    arabica, robusta = fixture_csvs
    counts = load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    assert counts.countries == 4  # Ethiopia, Colombia, Brazil, Vietnam (rowless country skipped)
    assert counts.regions == 5  # Yirgacheffe, Sidamo, Huila, Cerrado, Central Highlands
    assert (
        counts.farms == 6
    )  # Kochere(dedup), Bensa, La Esperanza, Anonymous, Fazenda X, Buon Ma Thuot
    assert counts.methods == 3  # Washed/Wet, Natural/Dry, Other


def test_region_links_to_country(db, fixture_csvs):
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    row = db.execute(
        """
        SELECT c.name FROM org_regions r
        JOIN org_countries c ON r.country_id = c.id
        WHERE r.name = 'Yirgacheffe'
        """
    ).fetchone()
    assert row == ("Ethiopia",)


def test_farm_carries_altitude(db, fixture_csvs):
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    altitude = db.execute("SELECT altitude FROM org_farms WHERE name = 'Kochere'").fetchone()
    assert altitude == (1900,)


def test_altitude_parses_when_column_is_string(db, tmp_path):
    """The real CQI altitude column contains 'NA' literals, so Polars types it as
    String and numeric values arrive as strings. Numeric strings must still parse;
    'NA' must become NULL. Regression for the dropped-altitude bug."""
    arabica = tmp_path / "arabica.csv"
    arabica.write_text(
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters","Variety"\n'
        '"Ethiopia","Yirgacheffe","HasAltitude","Washed / Wet","1850","Bourbon"\n'
        '"Ethiopia","Yirgacheffe","NoAltitude","Washed / Wet","NA","Bourbon"\n'
    )
    robusta = tmp_path / "robusta.csv"
    robusta.write_text(
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters","Variety"\n'
    )
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    assert db.execute("SELECT altitude FROM org_farms WHERE name = 'HasAltitude'").fetchone() == (
        1850,
    )
    assert db.execute("SELECT altitude FROM org_farms WHERE name = 'NoAltitude'").fetchone() == (
        None,
    )


def test_reingest_preserves_enrichment(db, fixture_csvs):
    """A standalone cqi re-run must not wipe enrichment added by later stages:
    geocoded coords/iso_code on countries + regions, and embeddings on methods.
    Regression for the destructive delete+insert (DB-2/DB-3)."""
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)

    # Simulate later stages enriching rows in place.
    db.execute(
        "UPDATE org_countries SET latitude = 9.0, longitude = 38.0, iso_code = 'ET' "
        "WHERE name = 'Ethiopia'"
    )
    db.execute("UPDATE org_regions SET latitude = 6.1, longitude = 38.2 WHERE name = 'Yirgacheffe'")
    db.execute(
        "UPDATE proc_methods SET description = 'desc', "
        "description_embedding = ?::FLOAT[3072] WHERE name = 'Washed / Wet'",
        [[0.5] * 3072],
    )

    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)

    assert db.execute(
        "SELECT latitude, longitude, iso_code FROM org_countries WHERE name = 'Ethiopia'"
    ).fetchone() == (9.0, 38.0, "ET")
    assert db.execute(
        "SELECT latitude, longitude FROM org_regions WHERE name = 'Yirgacheffe'"
    ).fetchone() == (6.1, 38.2)
    desc, embedding = db.execute(
        "SELECT description, description_embedding FROM proc_methods WHERE name = 'Washed / Wet'"
    ).fetchone()
    assert desc == "desc"
    assert embedding is not None
    assert len(embedding) == 3072


def test_reingest_preserves_other_stages_rows(db, fixture_csvs):
    """A standalone cqi re-run must not destroy whole rows owned by other
    stages: importer-only countries from the distribution stage, and the
    processing_flavor / graph stages' edge tables (deleted for FK order but
    never rebuilt here). Regression for the org_countries wipe that left
    dist_importers/dist_trade_routes referencing deleted rows."""
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)

    # Simulate the distribution stage adding an importer-only country, and the
    # processing_flavor / graph stages seeding their edge tables.
    db.execute(
        "INSERT INTO org_countries (id, name, latitude, longitude) "
        "VALUES ('c-de', 'Germany', 51.16, 10.45)"
    )
    db.execute("INSERT INTO flav_attributes (id, name) VALUES ('f1', 'Floral')")
    db.execute("INSERT INTO prod_products (id, name) VALUES ('p1', 'Yirgacheffe Lot 1')")
    db.execute("INSERT INTO shop_shops (id, name) VALUES ('s1', 'Cafe')")
    method_id = db.execute("SELECT id FROM proc_methods WHERE name = 'Washed / Wet'").fetchone()[0]
    country_id = db.execute("SELECT id FROM org_countries WHERE name = 'Ethiopia'").fetchone()[0]
    region_id = db.execute("SELECT id FROM org_regions WHERE name = 'Yirgacheffe'").fetchone()[0]
    farm_id = db.execute("SELECT id FROM org_farms WHERE name = 'Kochere'").fetchone()[0]
    db.execute(
        "INSERT INTO edges_processing_flavor (id, method_id, flavor_id, effect) "
        "VALUES ('e1', ?, 'f1', 'enhances')",
        [method_id],
    )
    db.execute(
        "INSERT INTO edges_product_country (id, product_id, country_id) VALUES ('e2', 'p1', ?)",
        [country_id],
    )
    db.execute(
        "INSERT INTO edges_product_region (id, product_id, region_id) VALUES ('e3', 'p1', ?)",
        [region_id],
    )
    db.execute(
        "INSERT INTO edges_product_farm (id, product_id, farm_id) VALUES ('e4', 'p1', ?)",
        [farm_id],
    )
    db.execute(
        "INSERT INTO edges_shop_farm (id, shop_id, farm_id) VALUES ('e5', 's1', ?)",
        [farm_id],
    )

    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)

    assert db.execute(
        "SELECT name, latitude, longitude FROM org_countries WHERE id = 'c-de'"
    ).fetchone() == ("Germany", 51.16, 10.45)
    assert db.execute(
        "SELECT method_id, flavor_id, effect FROM edges_processing_flavor WHERE id = 'e1'"
    ).fetchone() == (method_id, "f1", "enhances")
    assert db.execute(
        "SELECT product_id, country_id FROM edges_product_country WHERE id = 'e2'"
    ).fetchone() == ("p1", country_id)
    assert db.execute(
        "SELECT product_id, region_id FROM edges_product_region WHERE id = 'e3'"
    ).fetchone() == ("p1", region_id)
    assert db.execute(
        "SELECT product_id, farm_id FROM edges_product_farm WHERE id = 'e4'"
    ).fetchone() == ("p1", farm_id)
    assert db.execute(
        "SELECT shop_id, farm_id FROM edges_shop_farm WHERE id = 'e5'"
    ).fetchone() == ("s1", farm_id)


def test_processing_method_categorized(db, fixture_csvs):
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    rows = dict(db.execute("SELECT name, category FROM proc_methods").fetchall())
    assert rows["Washed / Wet"] == "wet"
    assert rows["Natural / Dry"] == "dry"
    assert rows["Other"] == "other"


def test_idempotent(db, fixture_csvs):
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    countries = db.execute("SELECT COUNT(*) FROM org_countries").fetchone()[0]
    assert countries == 4


def test_variety_edges_populate(seeded_db, fixture_csvs):
    arabica, robusta = fixture_csvs
    counts = load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    # Ethiopia: Gesha→Geisha (Panama), Bourbon (2 rows: Gesha dedupes with farm)
    # Colombia: Caturra
    # "Unknown country" row: Typica (skipped — no country)
    # Brazil: Marigojipe→Maragogipe
    assert counts.country_variety_edges >= 4

    eth_varieties = {
        row[0]
        for row in seeded_db.execute(
            """
            SELECT v.name FROM edges_country_variety e
            JOIN var_varieties v ON v.id = e.variety_id
            JOIN org_countries c ON c.id = e.country_id
            WHERE c.name = 'Ethiopia'
            """
        ).fetchall()
    }
    assert eth_varieties == {"Geisha (Panama)", "Bourbon"}


def test_variety_synonyms_resolve(seeded_db, fixture_csvs):
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    # "Gesha" → Geisha (Panama); "Marigojipe" → Maragogipe.
    geisha_links = seeded_db.execute(
        "SELECT COUNT(*) FROM edges_country_variety WHERE variety_id = 'vid-geisha'"
    ).fetchone()[0]
    maragogipe_links = seeded_db.execute(
        "SELECT COUNT(*) FROM edges_country_variety WHERE variety_id = 'vid-maragogipe'"
    ).fetchone()[0]
    assert geisha_links >= 1
    assert maragogipe_links >= 1


def test_variety_blacklist_skipped(seeded_db, fixture_csvs):
    arabica, robusta = fixture_csvs
    counts = load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    # The "Other" Variety row should not register as unmatched.
    assert counts.unmatched_varieties == 0


def test_unmatched_varieties_counted(seeded_db, tmp_path):
    arabica = tmp_path / "arabica.csv"
    arabica.write_text(
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters","Variety"\n'
        '"Honduras","Copan","Finca Y","Washed / Wet",1500,"Centroamericano"\n'
    )
    robusta = tmp_path / "robusta.csv"
    robusta.write_text(
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters","Variety"\n'
    )
    counts = load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    assert counts.unmatched_varieties == 1
    assert counts.country_variety_edges == 0


def test_variety_edges_idempotent(seeded_db, fixture_csvs):
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    first = seeded_db.execute("SELECT COUNT(*) FROM edges_country_variety").fetchone()[0]
    load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    second = seeded_db.execute("SELECT COUNT(*) FROM edges_country_variety").fetchone()[0]
    assert first == second
    assert first > 0


def test_region_and_farm_variety_edges(seeded_db, fixture_csvs):
    arabica, robusta = fixture_csvs
    counts = load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    assert counts.region_variety_edges > 0
    assert counts.farm_variety_edges > 0

    # Yirgacheffe should link to Geisha (Panama) and Bourbon via region edges.
    yirg_varieties = {
        row[0]
        for row in seeded_db.execute(
            """
            SELECT v.name FROM edges_region_variety e
            JOIN var_varieties v ON v.id = e.variety_id
            JOIN org_regions r ON r.id = e.region_id
            WHERE r.name = 'Yirgacheffe'
            """
        ).fetchall()
    }
    assert "Geisha (Panama)" in yirg_varieties


def test_variety_processing_edges(seeded_db, fixture_csvs):
    arabica, robusta = fixture_csvs
    counts = load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    # Co-occurrence pairs: Geisha/Washed, Bourbon/Natural, Caturra/Washed,
    # Maragogipe/Natural — four distinct variety<->processing edges.
    assert counts.variety_processing_edges == 4

    # Bourbon was a Natural / Dry sample.
    bourbon_methods = {
        row[0]
        for row in seeded_db.execute(
            """
            SELECT m.name FROM edges_variety_processing e
            JOIN var_varieties v ON v.id = e.variety_id
            JOIN proc_methods m ON m.id = e.method_id
            WHERE v.name = 'Bourbon'
            """
        ).fetchall()
    }
    assert bourbon_methods == {"Natural / Dry"}


def test_variety_processing_edges_idempotent(seeded_db, fixture_csvs):
    arabica, robusta = fixture_csvs
    load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    first = seeded_db.execute("SELECT COUNT(*) FROM edges_variety_processing").fetchone()[0]
    load_cqi_data(conn=seeded_db, arabica_path=arabica, robusta_path=robusta)
    second = seeded_db.execute("SELECT COUNT(*) FROM edges_variety_processing").fetchone()[0]
    assert first == second
    assert first > 0


@needs_data
def test_real_csvs_load(db):
    counts = load_cqi_data(conn=db, arabica_path=ARABICA, robusta_path=ROBUSTA)
    assert counts.countries > 30
    assert counts.regions > 100
    assert counts.farms > 200
    assert counts.methods >= 4
