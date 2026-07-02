"""Tests for the distribution loader — country ensure, idempotency, unresolved skips."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.ingest._common import deterministic_uuid
from backend.ingest.cqi_loader import ORIGIN_NAMESPACE
from backend.ingest.distribution_loader import load_distribution


@pytest.fixture
def seed_file(tmp_path: Path) -> Path:
    seed = {
        "import_countries": ["Germany"],
        "certifications": [
            {"name": "Organic", "description": "Certified organic"},
            {"name": "Fair Trade"},
        ],
        "importers": [
            {"name": "Beans GmbH", "country": "Germany", "website": "https://beans.example"},
        ],
        "trade_routes": [
            {"exporter": "Ethiopia", "importer": "Germany"},
            {"exporter": "Ethiopia", "importer": "Japan"},
        ],
    }
    p = tmp_path / "seed.json"
    p.write_text(json.dumps(seed), encoding="utf-8")
    return p


def test_inserts_missing_countries_with_deterministic_ids(db, seed_file):
    counts = load_distribution(conn=db, source_path=seed_file)
    # Ethiopia, Germany, Japan all absent -> all inserted.
    assert counts.countries_added == 3
    row = db.execute("SELECT id FROM org_countries WHERE name = 'Germany'").fetchone()
    # Same ORIGIN_NAMESPACE scheme as the cqi loader, so a later cqi rebuild
    # (or an earlier cqi run) produces identical ids and references heal.
    assert row == (deterministic_uuid(ORIGIN_NAMESPACE, "country", "Germany"),)


def test_reuses_existing_countries(db, seed_file):
    db.execute("INSERT INTO org_countries (id, name, latitude) VALUES ('c-eth', 'Ethiopia', 9.1)")
    counts = load_distribution(conn=db, source_path=seed_file)
    assert counts.countries_added == 2  # Germany + Japan only
    exporter = db.execute("SELECT DISTINCT exporter_country_id FROM dist_trade_routes").fetchall()
    assert exporter == [("c-eth",)]  # routes reference the pre-existing row


def test_counts_and_rows(db, seed_file):
    counts = load_distribution(conn=db, source_path=seed_file)
    assert counts.certifications == 2
    assert counts.importers == 1
    assert counts.trade_routes == 2
    assert counts.unresolved == []
    assert db.execute("SELECT count(*) FROM dist_certifications").fetchone() == (2,)


def test_idempotent_rerun(db, seed_file):
    load_distribution(conn=db, source_path=seed_file)
    counts = load_distribution(conn=db, source_path=seed_file)
    assert counts.countries_added == 0
    assert db.execute("SELECT count(*) FROM dist_trade_routes").fetchone() == (2,)
    assert db.execute("SELECT count(*) FROM dist_importers").fetchone() == (1,)
    assert db.execute("SELECT count(*) FROM org_countries").fetchone() == (3,)
