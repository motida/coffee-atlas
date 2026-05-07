"""Tests for backend/ingest/overture_shops_loader.py — helpers only.

The S3-hitting integration path is verified by running `just ingest shops`
manually; not exercised here to keep tests offline and fast.
"""

from __future__ import annotations


import pytest

from backend.ingest.overture_shops_loader import (
    DEFAULT_BBOX,
    _category_predicate,
    _resolve_bbox,
)


def test_resolve_bbox_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OVERTURE_BBOX", raising=False)
    assert _resolve_bbox() == DEFAULT_BBOX


def test_resolve_bbox_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERTURE_BBOX", "-10.5,30.0,40.25,60.5")
    assert _resolve_bbox() == (-10.5, 30.0, 40.25, 60.5)


def test_resolve_bbox_rejects_malformed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERTURE_BBOX", "1,2,3")
    with pytest.raises(ValueError, match="must be"):
        _resolve_bbox()


def test_category_predicate_quotes_categories():
    pred = _category_predicate()
    assert "categories.primary IN" in pred
    assert "'coffee_shop'" in pred
    assert "'cafe'" in pred


def test_category_predicate_safe_against_basic_injection():
    """The category list is a module constant, not user input. Sanity check
    that nothing exotic slipped in."""
    pred = _category_predicate()
    assert ";" not in pred
    assert "--" not in pred
    assert "/*" not in pred
