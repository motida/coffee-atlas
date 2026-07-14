"""Tests for the shop-description scraper's resume bookkeeping."""

from __future__ import annotations

import json

import backend.ingest.shop_scrapers.website_scraper as ws


def _write_log(cache_dir, scope, records):
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{scope}__run1.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_load_done_ids_retries_transient_failures(tmp_path, monkeypatch):
    """Shops whose last attempt failed transiently (network blip, 5xx) must
    stay eligible on resume; permanent outcomes stay done. Regression for
    fetch_error shops being skipped forever."""
    monkeypatch.setattr(ws, "CACHE_DIR", tmp_path)
    _write_log(
        tmp_path,
        "tokyo-jp",
        [
            {"shop_id": "s-ok", "status": "ok"},
            {"shop_id": "s-empty", "status": "empty"},
            {"shop_id": "s-junk", "status": "junk"},
            {"shop_id": "s-skip", "status": "skip"},
            {"shop_id": "s-fetch", "status": "fetch_error"},
            {"shop_id": "s-http", "status": "http_error"},
        ],
    )
    done = ws.load_done_ids("tokyo-jp")
    assert done == {"s-ok", "s-empty", "s-junk", "s-skip"}


def test_load_done_ids_transient_then_ok(tmp_path, monkeypatch):
    """A shop that failed once and succeeded on a later run counts as done."""
    monkeypatch.setattr(ws, "CACHE_DIR", tmp_path)
    _write_log(
        tmp_path,
        "tokyo-jp",
        [
            {"shop_id": "s1", "status": "fetch_error"},
            {"shop_id": "s1", "status": "ok"},
        ],
    )
    assert ws.load_done_ids("tokyo-jp") == {"s1"}


def test_extract_description_norwegian_coffee_terms():
    """Norwegian descriptions must pass the coffee-keyword filter. Regression:
    the Oslo scrape dropped real specialty copy ("kaffebarkjede", "Kaffebønner
    brent i Oslo") as junk because only English/Hebrew/Japanese/Thai terms
    matched. Norwegian compounds extend the stem, so the match is suffix-open."""
    cases = [
        "Stockfleths er en lokal kaffebarkjede med kvalitetsfokus og lang historie",
        "Solberg & Hansen kjøper kaffe av svært høy kvalitet direkte fra bønder",
        "Et lite kaffebrenneri på Grünerløkka med egne kaffebønner",
        "Håndverksbakeriet med konditori i sentrum",
        "Vi selger espressomaskiner og bryggeutstyr",
    ]
    for text in cases:
        html = f'<meta name="description" content="{text}">'
        assert ws.extract_description(html, "Some Shop") == text, text


def test_extract_description_still_drops_non_coffee():
    """The Norwegian stems must not let non-coffee businesses through."""
    for text in [
        "Pizza levering din favoritt pizza i Oslo, overtidsmat og takeaway",
        "En bar og arena for arkitektur og bykultur i 12. etasje i bygningen",
    ]:
        html = f'<meta name="description" content="{text}">'
        assert ws.extract_description(html, "Some Shop") is None, text
