"""Tests for backend/ingest/shop_scrapers/website_scraper.py — offline helpers.

The HTTP-fetching path is exercised by running the scraper manually; here we
cover the scope-slug logic that names the resumable log (regression for the
255-byte filename overflow with many cities) and the city-frontier reader that
drives the `descriptions` ingest stage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.ingest.shop_scrapers.website_scraper import (
    CITIES_FILE,
    MAX_SCOPE_SLUG_BYTES,
    _scope_slug,
    read_cities,
)


def test_scope_slug_short_list_is_readable():
    # A small city set stays human-readable and unhashed (backward compatible).
    assert _scope_slug([("New York", "US"), ("Brooklyn", "US")]) == "NewYork-US_Brooklyn-US"


def test_scope_slug_single_city():
    assert _scope_slug([("London", "GB")]) == "London-GB"


def test_scope_slug_long_list_is_bounded_and_filesystem_safe():
    cities = [(f"VeryLongCityName{i}", "US") for i in range(30)]
    slug = _scope_slug(cities)
    assert len(slug.encode("utf-8")) <= MAX_SCOPE_SLUG_BYTES
    # Whole filename (slug + timestamp + ext) must clear the 255-byte limit.
    assert len(f"{slug}__1781771319.jsonl".encode("utf-8")) < 255
    assert "and29more" in slug


def test_scope_slug_long_list_is_deterministic():
    # Same city set -> same slug, so re-runs still resume.
    cities = [(f"City{i}", "US") for i in range(40)]
    assert _scope_slug(cities) == _scope_slug(cities)


def test_scope_slug_distinguishes_different_long_sets():
    a = _scope_slug([(f"Alpha{i}", "US") for i in range(40)])
    b = _scope_slug([(f"Beta{i}", "US") for i in range(40)])
    assert a != b


def test_scope_slug_handles_unicode_city_names():
    # Accented names are multibyte; the byte-length guard must not overflow.
    cities = [("Montréal", "CA")] * 30
    slug = _scope_slug(cities)
    assert len(slug.encode("utf-8")) <= MAX_SCOPE_SLUG_BYTES


def test_read_cities_parses_and_skips_comments_and_blanks(tmp_path: Path):
    f = tmp_path / "cities.txt"
    f.write_text(
        "# a comment\n\nNew York,US\n  Montréal,CA  \n\n# trailing comment\nLondon,GB\n",
        encoding="utf-8",
    )
    assert read_cities(f) == [("New York", "US"), ("Montréal", "CA"), ("London", "GB")]


def test_read_cities_missing_file_returns_empty(tmp_path: Path):
    assert read_cities(tmp_path / "nope.txt") == []


def test_read_cities_rejects_malformed_line(tmp_path: Path):
    f = tmp_path / "cities.txt"
    f.write_text("New York,US\nBrokenLineNoCountry\n", encoding="utf-8")
    with pytest.raises(ValueError, match="City,CC"):
        read_cities(f)


def test_committed_city_frontier_is_valid():
    # The shipped frontier must parse and be non-trivial (it's the coverage list).
    cities = read_cities(CITIES_FILE)
    assert len(cities) >= 20
    assert all(c and co for c, co in cities)
    assert ("London", "GB") in cities
