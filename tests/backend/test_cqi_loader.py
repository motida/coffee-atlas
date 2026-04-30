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
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters"\n'
        '"Ethiopia","Yirgacheffe","Kochere","Washed / Wet",1900\n'
        '"Ethiopia","Yirgacheffe","Kochere","Washed / Wet",1900\n'
        '"Ethiopia","Sidamo","Bensa","Natural / Dry",2000\n'
        '"Colombia","Huila","La Esperanza","Washed / Wet",1700\n'
        '"Colombia",,"Anonymous","Other",\n'
        ',"Unknown","Ghost","Other",1500\n'
    )
    robusta = tmp_path / "robusta.csv"
    robusta.write_text(
        '"Country.of.Origin","Region","Farm.Name","Processing.Method","altitude_mean_meters"\n'
        '"Vietnam","Central Highlands","Buon Ma Thuot","Natural / Dry",600\n'
    )
    return arabica, robusta


def test_dedupes_and_normalizes(db, fixture_csvs):
    arabica, robusta = fixture_csvs
    counts = load_cqi_data(conn=db, arabica_path=arabica, robusta_path=robusta)
    assert counts.countries == 3  # Ethiopia, Colombia, Vietnam (rowless country skipped)
    assert counts.regions == 4  # Yirgacheffe, Sidamo, Huila, Central Highlands
    assert counts.farms == 5  # Kochere(dedup), Bensa, La Esperanza, Anonymous, Buon Ma Thuot
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
    assert countries == 3


@needs_data
def test_real_csvs_load(db):
    counts = load_cqi_data(conn=db, arabica_path=ARABICA, robusta_path=ROBUSTA)
    assert counts.countries > 30
    assert counts.regions > 100
    assert counts.farms > 200
    assert counts.methods >= 4
