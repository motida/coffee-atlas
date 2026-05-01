"""Tests for the geocode stage — country lookup + region geocoder integration."""

from __future__ import annotations

import pytest

from backend.ingest.geocode_stage import (
    geocode_countries,
    geocode_regions,
    run_geocode,
)
from backend.services.geocoding import GeoPoint


class FakeGeocoder:
    """Records every lookup; returns a configured response per query."""

    def __init__(self, responses: dict[str, GeoPoint | None]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str | None]] = []

    def lookup(self, query: str, country_iso: str | None = None) -> GeoPoint | None:
        self.calls.append((query, country_iso))
        return self.responses.get(query)


def _seed_origins(db) -> tuple[str, str]:
    cid = "country-eth"
    rid = "region-yirg"
    db.execute(
        "INSERT INTO org_countries (id, name) VALUES (?, ?)",
        [cid, "Ethiopia"],
    )
    db.execute(
        "INSERT INTO org_regions (id, name, country_id) VALUES (?, ?, ?)",
        [rid, "Yirgacheffe", cid],
    )
    return cid, rid


def test_country_lookup_fills_lat_lng_iso(db):
    cid, _ = _seed_origins(db)
    resolved, unresolved = geocode_countries(db)
    assert resolved == 1
    assert unresolved == 0
    row = db.execute(
        "SELECT latitude, longitude, iso_code FROM org_countries WHERE id = ?",
        [cid],
    ).fetchone()
    assert row is not None
    assert row[0] is not None and row[1] is not None
    assert row[2] == "ET"


def test_country_alias_resolves(db):
    db.execute("INSERT INTO org_countries (id, name) VALUES (?, ?)", ["c-vn", "Vietnam"])
    resolved, _ = geocode_countries(db)
    assert resolved == 1
    iso = db.execute("SELECT iso_code FROM org_countries WHERE id = 'c-vn'").fetchone()
    assert iso == ("VN",)


def test_country_unresolved_reported(db):
    db.execute("INSERT INTO org_countries (id, name) VALUES (?, ?)", ["c-x", "Atlantis"])
    resolved, unresolved = geocode_countries(db)
    assert resolved == 0
    assert unresolved == 1


def test_country_skips_already_geocoded(db):
    db.execute(
        "INSERT INTO org_countries (id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
        ["c-eth", "Ethiopia", 9.0, 38.0],
    )
    resolved, _ = geocode_countries(db)
    assert resolved == 0


def test_region_geocoded_via_geocoder(db):
    cid, rid = _seed_origins(db)
    geocode_countries(db)  # populate iso_code so query is country-scoped
    fake = FakeGeocoder({"Yirgacheffe, Ethiopia": GeoPoint(latitude=6.16, longitude=38.21)})
    resolved, unresolved = geocode_regions(db, fake)
    assert resolved == 1
    assert unresolved == 0
    assert fake.calls == [("Yirgacheffe, Ethiopia", "ET")]
    row = db.execute("SELECT latitude, longitude FROM org_regions WHERE id = ?", [rid]).fetchone()
    assert row == pytest.approx((6.16, 38.21))


def test_region_unresolved_increments_counter(db):
    cid, _ = _seed_origins(db)
    fake = FakeGeocoder({})
    resolved, unresolved = geocode_regions(db, fake)
    assert resolved == 0
    assert unresolved == 1


def test_run_geocode_idempotent(db):
    cid, rid = _seed_origins(db)
    fake = FakeGeocoder({"Yirgacheffe, Ethiopia": GeoPoint(6.16, 38.21)})
    counts1 = run_geocode(conn=db, geocoder=fake)
    assert counts1.regions_resolved == 1
    counts2 = run_geocode(conn=db, geocoder=fake)
    # Second pass: nothing left to resolve.
    assert counts2.countries_resolved == 0
    assert counts2.regions_resolved == 0
