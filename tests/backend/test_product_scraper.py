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
    _woo_grams,
    _woo_price,
    dedupe_products,
    detect_process,
    detect_roast_level,
    extract_jsonld,
    extract_shopify,
    extract_woocommerce,
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


def test_jsonld_prefers_specific_process():
    html = (
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Sumatra","description":"a semi washed lot"}</script>'
    )
    p = extract_jsonld(html, "https://x.example")[0]
    assert p.process == "Semi-Washed"  # longest-key wins over the substring "washed"


def test_jsonld_rejects_non_http_url():
    html = (
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Kenya AA","url":"javascript:alert(1)"}</script>'
    )
    p = extract_jsonld(html, "https://acme.example")[0]
    assert p.url == "https://acme.example"  # falls back to site_url, never javascript:


# --------------------------------------------------------------------------
# WooCommerce — real Store API payloads from two stores that file the signal
# differently: Ritual tags it (tags[]), Barrington categorizes it (categories[]).
# --------------------------------------------------------------------------

RITUAL_SITE = "https://www.ritualcoffee.com"
BARRINGTON_SITE = "https://www.barringtoncoffee.com"
RITUAL_FIXTURE = Path(__file__).parent / "fixtures" / "ritual_woocommerce.json"
BARRINGTON_FIXTURE = Path(__file__).parent / "fixtures" / "barrington_woocommerce.json"


@pytest.fixture
def ritual() -> list[ScrapedProduct]:
    return extract_woocommerce(json.loads(RITUAL_FIXTURE.read_text(encoding="utf-8")), RITUAL_SITE)


@pytest.fixture
def barrington() -> list[ScrapedProduct]:
    return extract_woocommerce(
        json.loads(BARRINGTON_FIXTURE.read_text(encoding="utf-8")), BARRINGTON_SITE
    )


def test_woo_counts_roaster_and_source(ritual, barrington):
    assert len(ritual) == 8
    assert len(barrington) == 8
    # brands[] is empty on both → roaster falls back to the site host.
    assert {p.roaster for p in ritual} == {"ritualcoffee.com"}
    assert {p.roaster for p in barrington} == {"barringtoncoffee.com"}
    assert {p.source for p in ritual + barrington} == {"woocommerce"}


def test_woo_title_html_entities_unescaped(ritual):
    # The API returns this name as "&#8220;ACE&#8221; Carrizal, Guatemala".
    assert any("“ACE” Carrizal" in p.title for p in ritual)
    assert not any("&#" in p.title for p in ritual)


def test_woo_price_from_minor_units(ritual, barrington):
    # cents → dollars, via the variable product's price_range.min_amount.
    assert _by_title(ritual, "Gregario Zelada").price == 24.0
    assert _by_title(ritual, "Goth Summer").price == 23.0
    # Barrington has no price_range → falls back to prices.price.
    assert _by_title(barrington, "San Diego Anaerobic").price == 20.45
    assert _by_title(barrington, "Costa Rica Micro-lot").price == 37.0


def test_woo_weight_from_formatted_weight(ritual, barrington):
    assert _by_title(barrington, "Costa Rica Micro-lot").net_weight_grams == 680  # 1.5 lbs
    assert _by_title(barrington, "San Diego Anaerobic").net_weight_grams == 340  # 0.75 lbs
    assert _by_title(barrington, "Dark Roast Sampler").net_weight_grams == 1021  # 2.25 lbs
    # Ritual reports formatted_weight "N/A" → no guess.
    assert all(p.net_weight_grams is None for p in ritual)


def test_woo_roast_from_category(barrington):
    # Roast is a "<level> Roast" category, not a bare tag.
    assert _by_title(barrington, "San Diego Anaerobic").roast_level == "medium"
    assert _by_title(barrington, "Mahiga Double").roast_level == "light"
    assert _by_title(barrington, "Dark Roast Sampler").roast_level == "dark"


def test_woo_flavor_tag_not_misread_as_roast(ritual):
    # "dark chocolate" is a flavor note — it must never be read as a dark roast.
    gregario = _by_title(ritual, "Gregario Zelada")
    assert "dark chocolate" in gregario.tags
    assert gregario.roast_level is None
    assert all(p.roast_level is None for p in ritual)  # Ritual tags no roast at all


def test_woo_process_from_title(barrington):
    assert _by_title(barrington, "San Diego Anaerobic").process == "Anaerobic"
    assert _by_title(barrington, "Las Lajas Honey").process == "Honey"
    assert _by_title(barrington, "Kalle Natural").process == "Natural"
    assert _by_title(barrington, "Mahiga Double").process is None  # no process word


def test_woo_tag_pool_merges_categories(barrington):
    # categories[] objects are folded into the flat tag list detection sees.
    tags = _by_title(barrington, "San Diego Anaerobic").tags
    assert "Medium Roast" in tags
    assert "Americas" in tags


def test_woo_grams_units():
    assert _woo_grams("1.5 lbs") == 680
    assert _woo_grams("0.75 lbs") == 340
    assert _woo_grams("12 oz") == 340
    assert _woo_grams("250 g") == 250
    assert _woo_grams("1 kg") == 1000
    assert _woo_grams("N/A") is None  # WooCommerce's unit-less placeholder
    assert _woo_grams(None) is None


def test_woo_price_units():
    assert _woo_price({"price": "2400", "currency_minor_unit": 2}) == 24.0
    # price_range.min_amount (the "from" price) wins over the top-level price.
    assert (
        _woo_price(
            {"price": "2400", "price_range": {"min_amount": "1800"}, "currency_minor_unit": 2}
        )
        == 18.0
    )
    assert _woo_price({"price": "0", "currency_minor_unit": 2}) is None  # $0 placeholder
    assert _woo_price({}) is None
