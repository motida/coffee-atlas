"""Load scraped roaster products into prod_products (+ roast_roasters).

Consumes the JSONL produced by
``backend.ingest.shop_scrapers.product_scraper`` (one record per product,
plus per-site markers) and populates the products domain:

1. Classify each scraped record as coffee or not. Roaster storefronts also
   sell tea, mugs, brewers, gift cards, etc.; Shopify's ``product_type`` is
   the decisive signal, so we drop anything matching a non-coffee type/title.
2. Attribute the roaster by SITE, not by Shopify ``vendor`` — vendor is the
   manufacturer, which for resold gear is "Fellow"/"Hario"/etc. The roaster of
   a site's coffee is the modal vendor among that site's coffee products.
3. Upsert roast_roasters (id is deterministic per roaster name) and insert
   prod_products with the roaster_id FK.

Edge resolution (product → variety / origin / flavor / roast, shop → product)
is deferred to a later stage; this loader only populates the product nodes.

Re-runs are idempotent: prod_products (and any product-referencing edges) are
delete+inserted (FK order), while roasters are inserted ON CONFLICT DO NOTHING
so the roasting domain's roasters are never clobbered.

Run:
    uv run -m backend.ingest.products_loader \
        --source data/cache/product_scrape/curated.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import duckdb

from backend.ingest._common import (
    deterministic_uuid,
    managed_connection,
    normalize_for_dedup,
)

PRODUCT_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000008")
DEFAULT_SOURCE = Path("data/cache/product_scrape")  # dir of scraper JSONL logs

# Non-coffee signal — matched against product_type, title and tags. Roaster
# stores carry tea, drinkware, brewers, merch, gift cards, etc. Tuned against
# the real catalogs in data/raw/roaster_sites.txt.
# Hard non-coffee signals in the TITLE — these always disqualify, regardless of
# product_type. Covers brewers/equipment (incl. brand names), merch, filters,
# trash, and multi-coffee bundles/sets that aren't a single product node.
_NON_COFFEE_TITLE = re.compile(
    r"\b(trash|brewers?|machine|maker|grinder|kettle|scale|frother|tamper|"
    r"portafilter|carafe|decanter|jug|dripper|french\s*press|kit|"
    r"moccamaster|technivorm|chemex|aeropress|kalita|hario|fellow|wilfa|"
    r"baratza|comandante|gooseneck|breville|gaggia|rancilio|profitec|lelit|"
    r"rocket\s*espresso|v60|"
    r"mug|tumbler|tote|hoodie|t-?shirts?|tees|beanies?|candle|posters?|stickers?|"
    r"kanteen|bottle|socks?|"
    # Apparel / drinkware / merch the singular \b terms missed — plurals that
    # escaped the word boundary ("Socks", "Tees", "Stickers") and genuinely
    # absent items (sweatshirts, jumpers, cup-and-saucer sets, keychains, enamel
    # pins, reusable cups, art prints). 2026-07 frontier QA. "sweater" is guarded
    # so it doesn't eat the real "Sweater Weather" seasonal espresso.
    r"sweat\s?shirts?|sweaters?(?!\s+weather)|jumpers?|cardigans?|crewnecks?|"
    r"keychains?|key\s?rings?|enamel\s+pins?|saucers?|reusable\s+cups?|"
    r"insulated\s+cups?|onesies?|art\s+prints?|"
    r"sampler|bundle|gifts?|sample\s*set|tasting\s*set|cleaning|sets?|"
    # café supplies, drinkware, apparel, cupping classes, non-coffee beverages
    r"pitcher|tongs|whisk|brush|funnel|spoon|towel|apron|magnet|opener|cambro|"
    r"glass\s?ware|shot\s+glass|measuring|lids?|sleeves?|"
    r"hot\s+cups?|cold\s+cups?|paper\s+cups?|tamp(?:ing)?\s+mat|drip\s+mat|"
    r"rinza|tablets?|to-?go|cap|hat|crewneck|long\s+sleeve|trucker|keep\s?cup|"
    r"gift\s+card|e-?gift|matcha|cupping|"
    # paper filters / filter baskets ("filter" alone is a roast style, so only
    # these compound forms are safe to hard-block)
    r"paper\s+filters?|filter\s+baskets?|filter\s+papers?|masking\s+tape|"
    # Norwegian gear/merch (Oslo roasters: KAFFA, Stockfleths, Lippe sell
    # machines, grinders and drinkware whose names never match the English
    # terms above). Stem-matched because Norwegian compounds: "espressomaskin",
    # "kaffekvern", "termokanne", "gjenbrukskopp", "presskanne".
    r"\w*maskin\w*|\w*kvern\w*|\w*kanner?|\w*kopps?|kaffefilter\w*|"
    r"gavekort|plakat\w*|n[øo]kkelring\w*|reservedel\w*|utstyr\w*|"
    r"rengj[øo]r\w*|avkalk\w*|teposer|l[øo]svekt-te|mandler|sjokolade\w*|"
    # Espresso-machine / grinder / barista-gear brand and part names (2026-07
    # frontier QA: roaster storefronts list machines, spare parts and scales
    # whose titles carry only the brand, so the generic equipment words above
    # never fire — e.g. "Jura E8", "Acaia Pearl", "La Marzocco Group Gasket").
    # NB: the Brazilian variety is spelled "Acaiá" and stays unblocked.
    r"la\s*marzocco|la\s*pavoni|acaia|jura|de.?longhi|nuova\s*simonelli|"
    r"mahlk[oö]nig|fiorenzato|macap|appartamento|gaskets?|percolator\w*|"
    r"dosing|reservoir|brewing\s+system|water\s+filters?|descal\w*|"
    r"milk\s+(?:system|container|pipe|cooler)|cool\s+control|cafiza|wdt|bwt|"
    r"コーヒーメーカー|"
    # Hebrew gear/merch (IL roasters sell machines, grinders, scales and
    # accessories alongside beans; stem-matched like the Norwegian block):
    # machine, grinder, frother, kettle, tablets, portafilter-handle, basket,
    # kit, jug, bottle, stand, lid, shirt, ring, cleaning, frothing, thermos,
    # water/paper filter, measuring cup, coffee scale.
    r"מכונ\w*|מטחנ\w*|מקציף\w*|קומקום\w*|טבליות|ידית\w*|סלסל\w*|ערכת|"
    r"כד|בקבוק\w*|מעמד\w*|מכסה|חולצ\w*|טבעת|ניקוי|הקצפה|תרמוס|"
    r"פילטר\s+מים|פילטרים\s+נייר|ניירות\s+פילטר|כוס\s+(?:מדידה|שקילה)|"
    r"משקל\s+(?:קפה|למדידת))\b",
    re.I,
)

# Non-coffee beverages that share a name with a coffee drink: a plain
# "Chocolate"/"Horchata" item is merch, but a "Chocolate Cold Brew" is coffee.
_NON_COFFEE_BEVERAGE = re.compile(r"\b(chocolate|horchata)\b", re.I)
_COFFEE_DRINK = re.compile(r"\bcold\s*brew\b", re.I)

# Hard non-coffee product_type categories: physical equipment, merch, and
# record-shop media that is never bagged coffee even when the type string ALSO
# says "coffee". Fuglen Tokyo files brewers and paper filters under "Coffee
# Equipment", and tandemcoffee.com files records under "Vinyl"/"Wearables" — the
# merchant's own category is the decisive signal. These override the
# coffee-keyword positive below, unlike the soft categories (gifts/tea/
# subscription), which a real coffee can legitimately carry.
_HARD_NON_COFFEE_TYPE = re.compile(
    r"\b(equipment|gear|accessor\w*|drinkware|machine|grinder|brewers?|"
    r"merch\w*|apparel|wearables?|logoware|vinyl|records?|albums?|music|cds?|books?)\b",
    re.I,
)

# Soft non-coffee product_type categories. These disqualify UNLESS the type
# string also mentions coffee — some stores file a coffee under "...,Gifts"
# collections, or sell it under "Coffee & Tea" — so they yield to the
# coffee-keyword positive below.
_NON_COFFEE_TYPE = re.compile(
    r"\b(tea|brewing|supplies|warehouse|event|ticket|"
    r"subscription|carbon\s*offset|alt\s*beverage|cleaning|gifts?|media|kits?)\b",
    re.I,
)

# Unambiguous non-coffee category TAGS. Record-shop / merch storefronts tag
# items 'vinyl' / 'merch' even when product_type is blank (tandemcoffee.com has
# 23 records with no product_type but a 'vinyl' tag). Kept deliberately narrow —
# unlike product_type, tags also carry coffee collections (e.g. the same records
# are tagged 'meta-related-collection-coffees'), so this must not screen on
# 'gifts'/'subscription'/etc. that legitimately tag a coffee.
_NON_COFFEE_TAG = re.compile(r"\b(vinyl|merch\w*|wearables?)\b", re.I)

# Japanese non-coffee product_type values from JP roaster storefronts (Onibus
# files coffee under コーヒー豆 and everything else under these). CJK has no \b
# word boundaries, so these are matched by substring, not regex:
#   グッズ=goods/merch, フード=food, ギフト=gift bundle, ドリンク=drink, ウェア=apparel.
_NON_COFFEE_TYPE_JA = ("グッズ", "フード", "ギフト", "ドリンク", "ウェア")
# Japanese product_type that IS coffee — "coffee beans".
_COFFEE_TYPE_JA = "コーヒー豆"


@dataclass
class ProductCounts:
    roasters: int
    products: int
    dropped_non_coffee: int


def _uid(*parts: str) -> str:
    return deterministic_uuid(PRODUCT_NAMESPACE, *parts)


# Every product-domain table, in FK-safe delete order (everything that
# references prod_products and the shared parent tables comes before
# prod_products itself). Parent-table loaders that refresh a table the product
# domain FK-references — e.g. roasting_loader's DELETE FROM roast_roasters,
# which prod_products.roaster_id points at — must call clear_products() first
# or their DELETE raises a ConstraintException on a re-run.
PRODUCT_TABLES = (
    "edges_product_variety",
    "edges_product_region",
    "edges_product_country",
    "edges_product_farm",
    "edges_product_flavor",
    "edges_product_roast",
    "edges_shop_product",
    "edges_roaster_product",
    "edges_shop_roaster",
    "prod_products",
)


def clear_products(conn: duckdb.DuckDBPyConnection) -> None:
    """Delete all product-domain rows in FK-safe order."""
    for table in PRODUCT_TABLES:
        conn.execute(f"DELETE FROM {table}")


def classify_coffee(title: str, product_type: str | None, tags: list[str]) -> bool:
    """A coffee product unless its title or type clearly says otherwise.

    Title hard-negatives (brewers, merch, filters, bundles/sets) always win.
    A non-coffee product_type disqualifies only when the type doesn't itself
    mention coffee — guards stores that file a coffee under e.g. "...,Gifts".
    """
    if _NON_COFFEE_TITLE.search(title):
        return False
    # Chocolate/horchata are non-coffee — except as a cold-brew coffee drink.
    if _NON_COFFEE_BEVERAGE.search(title) and not _COFFEE_DRINK.search(title):
        return False
    pt = product_type or ""
    # Hard non-coffee categories (equipment/merch/media) disqualify even when the
    # type also says "coffee" — a "Coffee Equipment" item is a brewer, not beans.
    if pt and _HARD_NON_COFFEE_TYPE.search(pt):
        return False
    # An explicit coffee product_type is a strong positive — trust it over the
    # soft tag/type screens below. Stores mis-tag real coffee 'merch' (Cat &
    # Cloud's "Instant Coffee 6 Pack", product_type "Coffee", carries a 'merch'
    # tag), and some file a coffee under a "...,Gifts" collection type. Japanese
    # storefronts use コーヒー豆 ("coffee beans") for the same role.
    if pt and (re.search(r"coffee", pt, re.I) or _COFFEE_TYPE_JA in pt):
        return True
    # A 'vinyl'/'merch' category tag is decisive when product_type doesn't claim
    # coffee (records with no product_type but a 'vinyl' tag).
    if any(_NON_COFFEE_TAG.search(t) for t in tags):
        return False
    if pt and _NON_COFFEE_TYPE.search(pt):
        return False
    # Japanese non-coffee product_types (goods/food/gift/drink/apparel) — matched
    # by substring since CJK text has no regex word boundaries.
    if pt and any(j in pt for j in _NON_COFFEE_TYPE_JA):
        return False
    return True


def read_scraped(path: str | Path) -> list[dict[str, Any]]:
    """Read product records from scraper JSONL, flattening site onto each.

    Accepts a single .jsonl file or a directory of them (all *.jsonl are read,
    so resumable scrapes split across run files are picked up together).
    """
    p = Path(path)
    files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
    records: list[dict[str, Any]] = []
    for file in files:
        if not file.exists():
            continue
        for line in file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate a truncated/partial line from an interrupted scrape
            if "product" not in obj:  # skip _site_done markers
                continue
            product = dict(obj["product"])
            product["site"] = obj.get("site")
            records.append(product)
    return records


def _norm_name(name: str) -> str:
    """Case/whitespace-insensitive key (used for per-site vendor grouping)."""
    return normalize_for_dedup(name)


# Generic words a roaster's name may or may not carry — stripped (from the end,
# plus a leading "the") to derive an identity key. Lets "Stumptown Coffee",
# "Stumptown Coffee Roasters" and "The Stumptown Roastery" collapse to one node.
_GENERIC_ROASTER_WORDS = frozenset(
    {
        "coffee",
        "coffees",
        "roaster",
        "roasters",
        "roastery",
        "roasteries",
        "roasting",
        "company",
        "co",
        "lab",
        "labs",
        "specialty",
    }
)


def _canon_name(name: str) -> str:
    """Aggressive identity key for roaster dedup matching.

    Case-folds, drops punctuation, removes a leading "the" and any trailing
    generic coffee words. Conservative: never strips the final token, so two
    genuinely distinct names aren't merged into an empty key.
    """
    toks = re.sub(r"[^a-z0-9 ]+", " ", name.casefold()).split()
    if toks[:1] == ["the"]:
        toks = toks[1:]
    while len(toks) > 1 and toks[-1] in _GENERIC_ROASTER_WORDS:
        toks.pop()
    return " ".join(toks) or _norm_name(name)


# Shopify `vendor` abbreviations → canonical roaster display name. Applied to the
# resolved roaster name BEFORE dedup, so the node both displays a friendly name
# and a future re-scrape maps the abbreviation to the same canonical row instead
# of spawning a separate one (e.g. birdrockcoffee.com's vendor "BRCR Roasting").
# Keyed by _norm_name(vendor).
_VENDOR_ALIASES: dict[str, str] = {
    "brcr roasting": "Bird Rock Coffee Roasters",
}

# Sites whose Shopify `vendor` field is NOT the roaster name, so the modal-vendor
# attribution can't recover it. catandcloud.com files each coffee's tasting notes
# as the vendor ("Lavender • Raspberry • Green Tea") and only puts "Cat & Cloud"
# on merch — so once merch is filtered out, no product names the roaster. Keyed
# by the www-stripped domain (see _name_from_domain); the override always wins.
_SITE_ROASTER_OVERRIDES: dict[str, str] = {
    "catandcloud.com": "Cat & Cloud",
    # Prolog files single-origin coffees under origin-country "vendors" (Peru,
    # Colombia, …) and puts "Prolog Coffee" mostly on merch/subscriptions, so once
    # merch is filtered the modal coffee vendor is an origin, not the roaster.
    "prologcoffee.com": "Prolog Coffee",
    # Same origin-as-modal-vendor failure ("Colombia").
    "obtr-coffee.com": "Oubaitouri Coffee Roasters",
    # WooCommerce stores whose Store API exposes no `brands`, so the scraper falls
    # back to the host and the roaster would display as a bare domain. Mapped to the
    # proper name (from the discovery POI annotations / known base-list roasters).
    "ancoats-coffee.co.uk": "Ancoats Coffee Co",
    "armadilloroasters.com": "Armadillo Coffee Roasters",
    "armisticecoffeeco.com": "Armistice Coffee Roasters",
    "barringtoncoffee.com": "Barrington Coffee Roasting Company",
    "brewedawakenings.us": "Brewed Life Coffee Co",
    "bristol-twenty.co.uk": "Bristol Twenty Coffee Company",
    "cartelroasting.co": "Cartel Roasting Co.",
    "cityleaguecoffee.com": "City League Coffee Roasters",
    "copenhagencoffeelab.com": "Copenhagen Coffee Lab",
    "florcoffee.com": "Flor de Café International Coffee Company",
    "heartandgraft.co.uk": "Heart and Graft Coffee Roastery",
    "kaladicoffee.com": "Kaladi Coffee Roasters",
    "lineacaffe.com": "Linea Coffee Roasting + Caffe",
    "lucecoffeeroasters.com": "Luce Ave Coffee Roasters",
    "nogocoffee.com": "No Go Coffee Co.",
    "ritualcoffee.com": "Ritual Coffee Roasters",
    # ritualcoffee.org is a DIFFERENT roaster (Cheltenham, UK) the scraper also
    # names "Ritual Coffee Roasters" — qualify it so the two don't collide.
    "ritualcoffee.org": "Ritual Coffee Roasters (Cheltenham)",
    # Tokyo (added 2026-06-30, verified live). The Shopify `vendor` isn't the
    # roaster name: Light Up files coffees under its location "三鷹" (Mitaka);
    # Single O Japan and Passage smash the brand into a lowercase token; Woodberry
    # shouts it in all caps. Map each to its proper display name.
    "lightupcoffee.com": "Light Up Coffee",
    "singleo.jp": "Single O Japan",
    "passagecoffee.com": "Passage Coffee",
    "woodberrycoffee.com": "Woodberry Coffee Roasters",
    # Oslo (added 2026-07-14). Stockfleths is WooCommerce with no `brands` in
    # the Store API, so without this it would display as a bare domain.
    # Tim Wendelboe files most coffees under the vendor slug "tim-wendelboe-no",
    # so the modal vendor is the slug, not the brand.
    "stockfleths.no": "Stockfleths",
    "timwendelboe.no": "Tim Wendelboe",
    # WooCommerce-no-brands (would fall back to the bare domain).
    "lippe.no": "Lippe Coffee Roastery",
    "nordoslo.no": "Norð Oslo Brenneri",
    # 2026-07 frontier QA (PR #83's promoted sites, loaded 2026-07-14): sites
    # whose modal vendor resolved to a bare domain (Woo-no-brands / Shopify
    # vendor unset), a placeholder ("vendor-unknown", "N/A"), a vendor slug, an
    # origin country ("Colombia"), or a company legal name ("Gifize spa").
    # Display names verified against each site's og:site_name / <title> on
    # 2026-07-17.
    "310coffee-store.com": "Ginza 310 Coffee",
    "alchemycoffee.co.uk": "Alchemy Coffee",
    "andytownsf.com": "Andytown Coffee Roasters",
    "ascensiondallas.com": "Ascension Coffee",
    "birdsandbeans.ca": "Birds and Beans Coffee Roasters",
    "bruleriesfaro.com": "Brûleries FARO",
    "buycoffeecanada.com": "Buy Coffee Canada",
    "cafegransasso.com": "Café Gran Sasso",
    "cafemoto.com": "Cafe Moto",
    "cafepista.com": "Café Pista",
    "caffecalabria.com": "Caffè Calabria",
    "cakeandculture.co.uk": "Cake & Culture",
    "canardcafe.com": "Canard Café",
    "chiccodicaffe.co.il": "Chicco di Caffè",
    "coffeeam.com": "CoffeeAM",
    "coffeeorg.co": "Coffee Organization",
    "coffeerepub.com": "Coffee Republic",
    "cuveecoffee.com": "Cuvée Coffee",
    "cyclingespresso.cc": "Cycling Espresso",
    "delanyscoffee.com": "Delany's Coffee House",
    "filicorizecchini.com": "Filicori Zecchini",
    # Mid-rebrand: redirects to slowandsteady.coffee (in maintenance when
    # checked); named for the historical brand until the new one is confirmed.
    "graphcoffee.com": "Graph Coffee",
    "graysferrycoffee.com": "Grays Ferry Coffee",
    "greatpricedcoffee.co.uk": "Great Priced Coffee",
    # Rebranded: guilttripcoffee.com now redirects to guilty.coffee.
    "guilttripcoffee.com": "Guilty Coffee",
    "holeinthewallcoffeeco.com": "Hole In The Wall Coffee Co",
    "imperialcoffee.com": "Imperial Coffee",
    "impresso.coffee": "Impresso Coffee",
    "infuzedcafe.com": "Infuzed Cafe",
    "jera-coffee.co.il": "Jera Coffee Shop",
    "johnnybeans.com": "Johnny Beans Coffee",
    "lacuissoncafe.com": "La Cussion Cafe",
    "leodiscoffee.co.uk": "Leodis Coffee",
    "meastelo.com": "Meastelo",
    "minuto.co.il": "Minuto Coffee",
    "moco575.com": "Moco 575",
    "mokanco.com": "Moka & Co",
    "mreion.com": "Mr Eion Coffee Roaster",
    "mrphin.com": "Mr. Phin",
    "nibblenq.com": "Nibble NQ",
    "northstarroast.com": "North Star Coffee Roasters",
    "novocoffee.com": "Novo Coffee",
    "pabloscoffee.com": "Pablo's Coffee",
    "papertrailbikecafe.com": "PAPERtrail Bike Cafe",
    "patera.ca": "Patera Coffee Roasters",
    "peppino-coffee.com": "Peppino Coffee Roaster",
    "philoscreations5.com": "Kurios Coffee Roasting Co.",
    "quarterhorsecoffee.com": "Quarterhorse Coffee",
    "rwandabean.com": "Rwanda Bean",
    "scrop-coffee-roasters.com": "Scrop Coffee Roasters",
    "servantcoffee.com": "Servant Coffee",
    "silverskincoffee.ie": "Silverskin Coffee Roasters",
    "sols-coffee.com": "Sol's Coffee",
    "speckledax.com": "Speckled Ax",
    "tallioscoffee.com": "Tallio's Coffee & Tea",
    "terracoffee.co.uk": "Terra Coffee",
    "theartofcoffee.ie": "The Art of Coffee",
    "thomsonscoffee.com": "Thomson's Coffee",
    "trulyscrummy.com": "Truly Scrummy",
    "tsukcafe.co.il": "Tsukcafe",
    "weaverscoffee.com": "Weaver's Coffee & Tea",
}


def _roaster_name_by_site(coffee_records: list[dict[str, Any]]) -> dict[str, str]:
    """Per site, the roaster name = modal vendor among its coffee products.

    Vendors are grouped case/whitespace-insensitively so "Onyx Coffee Lab" and
    "Onyx coffee lab" count as one; the most common raw spelling is the display.
    """
    by_site: dict[str, dict[str, Counter[str]]] = {}
    for rec in coffee_records:
        site = rec.get("site") or ""
        vendor = (rec.get("roaster") or "").strip()
        if vendor:
            by_site.setdefault(site, {}).setdefault(_norm_name(vendor), Counter())[vendor] += 1
    names: dict[str, str] = {}
    for site, groups in by_site.items():
        best = max(groups.values(), key=lambda c: sum(c.values()))
        names[site] = best.most_common(1)[0][0]
    return names


def _name_from_domain(site: str) -> str:
    host = urlparse(site).netloc or site
    return host.removeprefix("www.")


# Country-code TLD → ISO 4217 currency, for scrape-cache records that predate
# the scraper's `currency` field (the cache is resumable, so old records are
# re-loaded verbatim and never re-scraped). A store on a ccTLD sells in that
# country's currency; generic TLDs (.com/.coffee/...) stay None — unknown, not
# assumed USD. Keyed by the final domain label, so .co.uk → "uk", .co.il → "il".
_TLD_CURRENCY: dict[str, str] = {
    "us": "USD",
    "ca": "CAD",
    "uk": "GBP",
    "ie": "EUR",
    "de": "EUR",
    "fr": "EUR",
    "nl": "EUR",
    "be": "EUR",
    "at": "EUR",
    "es": "EUR",
    "it": "EUR",
    "pt": "EUR",
    "fi": "EUR",
    "no": "NOK",
    "se": "SEK",
    "dk": "DKK",
    "ch": "CHF",
    "il": "ILS",
    "jp": "JPY",
    "au": "AUD",
    "nz": "NZD",
}


def _currency_from_site(site: str) -> str | None:
    tld = _name_from_domain(site).rsplit(".", 1)[-1].lower()
    return _TLD_CURRENCY.get(tld)


def load_products(
    records: list[dict[str, Any]],
    conn: duckdb.DuckDBPyConnection,
) -> ProductCounts:
    """Classify, attribute roasters, and insert product nodes. See module docs."""
    coffee = [
        r
        for r in records
        if classify_coffee(r.get("title", ""), r.get("product_type"), r.get("tags") or [])
    ]
    dropped = len(records) - len(coffee)

    site_roaster = _roaster_name_by_site(coffee)

    # Build roaster + product rows keyed by deterministic id (dedupes repeats).
    # Reuse an existing roaster row whose canonical name matches (e.g. the
    # roasting seed's "Stumptown Coffee Roasters" vs a scraped "Stumptown
    # Coffee") so we don't create a duplicate node under a fresh id. Oldest row
    # wins ownership of a canonical key, and new roasters are registered as we
    # go so two sites for the same roaster collapse within a single batch.
    canon_to_id: dict[str, str] = {}
    for rid, name in conn.execute(
        "SELECT id, name FROM roast_roasters ORDER BY created_at"
    ).fetchall():
        canon_to_id.setdefault(_canon_name(name), rid)

    roasters: dict[str, tuple[str, str, str | None]] = {}  # id -> (id, name, website)
    products: dict[str, tuple[Any, ...]] = {}
    for rec in coffee:
        title = (rec.get("title") or "").strip()
        if not title:
            continue  # skip before registering a roaster, so no product-less roaster node
        site = rec.get("site") or ""
        domain = _name_from_domain(site)
        roaster_name = _SITE_ROASTER_OVERRIDES.get(domain) or site_roaster.get(site) or domain
        roaster_name = _VENDOR_ALIASES.get(_norm_name(roaster_name), roaster_name)
        canon = _canon_name(roaster_name)
        roaster_id = canon_to_id.get(canon)
        if roaster_id is None:
            roaster_id = _uid("roaster", roaster_name)
            canon_to_id[canon] = roaster_id
        roasters[roaster_id] = (roaster_id, roaster_name, site or None)

        product_id = _uid("product", site, title)
        price = rec.get("price")
        # Scraper-declared currency wins; legacy cache records fall back to the
        # site's ccTLD. No price → no currency to denominate.
        currency = (rec.get("currency") or _currency_from_site(site)) if price is not None else None
        products[product_id] = (
            product_id,
            title,
            roaster_id,
            rec.get("roast_level"),
            rec.get("process"),
            rec.get("is_blend"),
            price,
            currency,
            rec.get("net_weight_grams"),
            rec.get("url"),
            rec.get("description"),
        )

    # FK-safe teardown of the whole product domain, then re-insert below.
    # Roasters are upserted DO NOTHING so the roasting domain's rows are never
    # clobbered.
    clear_products(conn)

    if roasters:
        conn.executemany(
            """
            INSERT INTO roast_roasters (id, name, website) VALUES (?, ?, ?)
            ON CONFLICT (id) DO NOTHING
            """,
            list(roasters.values()),
        )
    if products:
        conn.executemany(
            """
            INSERT INTO prod_products
                (id, name, roaster_id, roast_level, process, is_blend, price,
                 currency, net_weight_grams, url, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            list(products.values()),
        )

    return ProductCounts(
        roasters=len(roasters),
        products=len(products),
        dropped_non_coffee=dropped,
    )


def load_from_file(
    source_path: str | Path = DEFAULT_SOURCE,
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> ProductCounts:
    records = read_scraped(source_path)
    with managed_connection(db_path, conn) as conn:
        return load_products(records, conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load scraped roaster products")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Scraper JSONL path")
    args = parser.parse_args()
    counts = load_from_file(args.source)
    print(
        f"Loaded {counts.products} products from {counts.roasters} roasters "
        f"({counts.dropped_non_coffee} non-coffee records dropped)"
    )


if __name__ == "__main__":
    main()
