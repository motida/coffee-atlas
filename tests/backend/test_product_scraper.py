"""Tests for the roaster product scraper's pure extraction logic.

Exercised against a saved real Shopify payload
(fixtures/blackwhite_products.json, captured from blackwhiteroasters.com) so
parsing is validated without hitting live sites.
"""

import json
from pathlib import Path

import pytest

from backend.ingest.shop_scrapers.product_scraper import (
    ScrapedProduct,
    dedupe_products,
    detect_process,
    detect_roast_level,
    extract_jsonld,
    extract_shopify,
    is_blend,
    looks_like_coffee,
)

SITE = "https://www.blackwhiteroasters.com"
FIXTURE = Path(__file__).parent / "fixtures" / "blackwhite_products.json"


@pytest.fixture
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def products(payload: dict) -> list[ScrapedProduct]:
    return extract_shopify(payload, SITE)


def _by_title(products: list[ScrapedProduct], needle: str) -> ScrapedProduct:
    matches = [p for p in products if needle in p.title]
    assert len(matches) == 1, f"expected 1 match for {needle!r}, got {len(matches)}"
    return matches[0]


def test_extract_count_and_roaster(products: list[ScrapedProduct]):
    assert len(products) == 8  # all 8 fixture items are coffee (incl. instant)
    assert {p.roaster for p in products} == {"Black & White Coffee Roasters"}


def test_url_built_from_handle(products: list[ScrapedProduct]):
    p = _by_title(products, "Bombe")  # uniquely titled in the fixture
    assert p.url is not None and p.url.startswith(f"{SITE}/products/")


def test_process_detected_from_tags(products: list[ScrapedProduct]):
    assert _by_title(products, "Bombe - Honey").process == "Honey"
    assert _by_title(products, "Arturo Paz").process == "Washed"
    assert _by_title(products, "Sebastian Ramirez").process == "Co-ferment"
    assert _by_title(products, "Oscar Hernandez").process == "Natural"


def test_roast_level_normalized(products: list[ScrapedProduct]):
    # B&W tags lighter roasts as "lighter" → canonical "light".
    assert _by_title(products, "Bombe - Honey").roast_level == "light"
    # No roast tag → None, not a guess.
    assert _by_title(products, "Oscar Hernandez").roast_level is None


def test_blend_flag_and_no_false_positive(products: list[ScrapedProduct]):
    assert _by_title(products, "Summer Slush").is_blend is True
    # "Unblended ... Instant Coffee" must NOT be read as a blend.
    assert _by_title(products, "Unblended").is_blend is False


def test_price_and_weight(products: list[ScrapedProduct]):
    el_burro_retail = [p for p in products if "El Burro" in p.title and p.channel == "retail"]
    assert len(el_burro_retail) == 1
    p = el_burro_retail[0]
    assert p.price == 32.0
    assert p.net_weight_grams == 113


def test_placeholder_variant_does_not_pollute_price_or_weight(products: list[ScrapedProduct]):
    # The wholesale El Burro has a $0 / 3g "Brew Card" add-on alongside real
    # sizes; price+weight must come from the cheapest *real* variant, not it.
    wholesale = [p for p in products if "El Burro" in p.title and p.channel == "wholesale"]
    assert len(wholesale) == 1
    assert wholesale[0].price == 27.75
    assert wholesale[0].net_weight_grams == 113


def test_dedupe_prefers_retail(products: list[ScrapedProduct]):
    deduped = dedupe_products(products)
    assert len(deduped) == 7  # El Burro retail + wholesale collapse to one
    el_burro = _by_title(deduped, "El Burro")
    assert el_burro.channel == "retail"
    assert el_burro.price == 32.0


def test_non_coffee_filtered():
    assert looks_like_coffee("Ethiopia Natural", "Retail SO", ["Natural"]) is True
    assert looks_like_coffee("Hario V60 Grinder", "Equipment", []) is False
    assert looks_like_coffee("Coffee Atlas Gift Card", None, []) is False
    assert looks_like_coffee("Logo Mug", "Merch", ["apparel"]) is False


def test_detectors_units():
    assert detect_roast_level(["Panama", "lighter"]) == "light"
    assert detect_roast_level(["Panama"]) is None
    assert detect_process(["Colombia", "Co-ferment"]) == "Co-ferment"
    assert detect_process(["Colombia"]) is None
    assert is_blend("House Blend", "Retail", []) is True
    assert is_blend("Unblended Origins", "Retail SO", []) is False


JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"Product","name":"Kenya AA",
 "description":"Bright blackcurrant. A washed coffee.",
 "brand":{"@type":"Brand","name":"Acme Roasters"},
 "offers":{"@type":"Offer","price":"21.00","priceCurrency":"USD"}}
</script>
</head><body>...</body></html>
"""


def test_jsonld_fallback():
    products = extract_jsonld(JSONLD_HTML, "https://acme.example")
    assert len(products) == 1
    p = products[0]
    assert p.title == "Kenya AA"
    assert p.roaster == "Acme Roasters"
    assert p.process == "Washed"  # from free-text description
    assert p.price == 21.0
    assert p.source == "jsonld"


def test_jsonld_graph_form():
    html = """
    <script type="application/ld+json">
    {"@graph":[{"@type":"WebSite"},
               {"@type":"Product","name":"Sumatra Dark Roast Blend",
                "offers":{"@type":"Offer","price":"15.50"}}]}
    </script>
    """
    products = extract_jsonld(html, "https://acme.example")
    assert len(products) == 1
    assert products[0].roast_level == "dark"
    assert products[0].is_blend is True
