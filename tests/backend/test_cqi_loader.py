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


@needs_data
def test_real_csvs_load(db):
    counts = load_cqi_data(conn=db, arabica_path=ARABICA, robusta_path=ROBUSTA)
    assert counts.countries > 30
    assert counts.regions > 100
    assert counts.farms > 200
    assert counts.methods >= 4
