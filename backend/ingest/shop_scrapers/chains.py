"""Coffee-shop chain lists, shared across the scraper and specialty scoring.

Two lists, deliberately separate:

- ``NONSPECIALTY_CHAINS`` — mass-market chains we *exclude* from the specialty
  map (and skip when scraping descriptions, since they yield no useful copy).
- ``SPECIALTY_CHAINS`` — multi-location *specialty* chains we *force-include*.
  A shop being a chain does not make it non-specialty: Blue Bottle, Stumptown,
  Intelligentsia et al. are chains we want to keep. This allowlist overrides the
  blocklist.

Matching is normalized and prefix-aware (word-boundary), so "Blue Bottle",
"Blue Bottle Coffee" and "Starbucks Reserve" all match their brand key, while
"Costa Rica Coffee Roasters" does *not* match "Costa Coffee". Both lists are
curation surfaces — extend them as coverage grows, especially outside the US.

Outside the US, the *name* signal degrades: Overture stores many shop names in
non-Latin scripts (e.g. Hebrew "קפה קפה"), which fold to an empty string and so
slip the name lists. For those markets the website *domain* is the reliable
chain fingerprint (every "Cafe Cafe" branch links to ``cafecafe.co.il``), so
``NONSPECIALTY_CHAIN_DOMAINS`` complements the name blocklist.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

# Distinctive brand *cores*, normalized into match sets at import time. Matching
# is "name equals core, or name starts with core + space", so a short core like
# "blue bottle" matches "Blue Bottle" and "Blue Bottle Coffee" while "costa
# coffee" does NOT match "Costa Rica Coffee Roasters".
_NONSPECIALTY_CHAIN_NAMES: tuple[str, ...] = (
    "Starbucks",
    "Tim Hortons",
    "Dunkin",
    "Dutch Bros",
    "McCafe",
    "Panera",
    "Caribou Coffee",
    "Scooter's Coffee",
    "7 Brew",
    "Costa Coffee",
    "Peets",
    "Coffee Bean & Tea Leaf",
    "Caffe Nero",
    "Pret A Manger",
    "Greggs",
    "Gloria Jean's",
    "Second Cup",
    "Tully's",
    # Global brand boutiques (not specialty cafés)
    "Nespresso",
    # Israeli chains (Tel Aviv coverage). Many branches carry only a Hebrew name
    # in Overture and are caught by domain (see NONSPECIALTY_CHAIN_DOMAINS); the
    # Latin/parenthetical forms below cover the rest.
    "Aroma",
    "Arcaffe",
    "Cafe Greg",
    "Greg Cafe",
    "Cofix",
    "Landwer",
    "Cafe Landwer",
    "Roladin",
    "Cafe Cafe",
    "Cafécafé",
)

_SPECIALTY_CHAIN_NAMES: tuple[str, ...] = (
    "Blue Bottle",
    "Stumptown",
    "Intelligentsia",
    "Verve Coffee",
    "La Colombe",
    "Onyx Coffee",
    "Philz",
    "Gregorys Coffee",
    "Bluestone Lane",
    "Joe Coffee",
    "Devocion",
    "Sightglass",
    "Ritual Coffee",
    "George Howell",
    "Coava",
    "Heart Coffee",
    "Sey Coffee",
    "Partners Coffee",
    "Counter Culture",
    # Israeli specialty roaster-cafés (multi-location, kept on the map).
    "Cafelix",
    "Nahat",
)

# Mass-market chain website domains. A chain's domain is a far more reliable
# fingerprint than its (often Hebrew, word-order-variable) display name, so this
# complements the name blocklist — every branch of a chain links to one domain.
# Bare registrable-ish form (no scheme/www/path); see ``_domain``.
_NONSPECIALTY_CHAIN_DOMAINS: tuple[str, ...] = (
    # Israel — top café chains by branch count in the Overture POI set.
    "aroma.co.il",
    "aromatlv.com",
    "cafecafe.co.il",
    "gregcafe.co.il",
    "landwercafe.co.il",
    "arcaffe.co.il",
    "cofix.co.il",
    "roladin.co.il",
    "joe.co.il",
    # Japan — Tokyo coverage. Overture stores these chains' names in katakana/
    # kanji, which _norm folds to "" and so slips the name list; the franchise
    # HQ domain is the reliable fingerprint. Exact-host match, so subdomains the
    # POI set actually uses (store./shop.) are listed alongside the apex.
    "starbucks.co.jp",
    "store.starbucks.co.jp",
    "doutor.co.jp",
    "shop.doutor.co.jp",
    "pronto.co.jp",
    "c-united.co.jp",  # Cafe Veloce / カフェ・ベローチェ operator
    "hoshinocoffee.com",  # 星乃珈琲店
    "tullys.co.jp",
    "saint-marc-hd.com",  # サンマルクカフェ
    "ueshima-coffee-ten.jp",  # 上島珈琲店 (UCC)
    "komeda.co.jp",  # コメダ珈琲店
    "kaldi.co.jp",  # カルディコーヒーファーム — import retailer chain
    "segafredo.jp",
    "ginza-renoir.co.jp",  # 喫茶室ルノアール
    "gongcha.co.jp",  # bubble-tea chain
    "deandeluca.co.jp",
    "italiantomato.co.jp",
)

# Social / review-aggregator / blog platforms. When a shop's only listed
# "website" is one of these, a description scraped from it is NOT the shop's own
# homepage copy, so it must not count as the specialty *description* signal (see
# shop_specialty). Suffix-matched: every subdomain (r.gnavi.co.jp, m.facebook.com)
# is equally non-homepage, unlike the exact-host chain domains above.
_SOCIAL_AGGREGATOR_DOMAINS: tuple[str, ...] = (
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "tabelog.com",
    "ameblo.jp",
    "note.com",
    "retty.me",
    "gnavi.co.jp",
    "hotpepper.jp",
    "linktr.ee",
    "lin.ee",
    "line.me",
    "youtube.com",
    "tiktok.com",
)


def _norm(name: str) -> str:
    """Fold accents, lowercase, drop apostrophes, reduce other punctuation to spaces.

    "Caffè Nero" -> "caffe nero"; "Peet's Coffee & Tea" -> "peets coffee tea";
    "Blue Bottle" -> "blue bottle". Accent folding matters: without it an accented
    chain name (Caffè Nero) wouldn't match its ASCII key and would slip the filter.
    """
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.casefold().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


NONSPECIALTY_CHAINS: frozenset[str] = frozenset(_norm(n) for n in _NONSPECIALTY_CHAIN_NAMES)
SPECIALTY_CHAINS: frozenset[str] = frozenset(_norm(n) for n in _SPECIALTY_CHAIN_NAMES)


def _matches(name: str, keys: frozenset[str]) -> bool:
    """True if `name`, normalized, equals or starts with (word-boundary) a key."""
    norm = _norm(name)
    if not norm:
        return False
    return any(norm == key or norm.startswith(key + " ") for key in keys)


def is_specialty_chain(name: str) -> bool:
    """A known multi-location specialty chain (kept on the map)."""
    return _matches(name, SPECIALTY_CHAINS)


def is_nonspecialty_chain(name: str) -> bool:
    """A mass-market chain (excluded), unless also a specialty chain."""
    return _matches(name, NONSPECIALTY_CHAINS) and not is_specialty_chain(name)


def _domain(website: str | None) -> str:
    """Bare registrable-ish domain: scheme, ``www.``, path and port stripped, lowercased.

    Mirrors the SQL normalization in ``backend.ingest.product_edges._domain_sql``
    closely enough that a name-list and the domain join agree on what a chain is.
    """
    if not website:
        return ""
    url = website.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


NONSPECIALTY_CHAIN_DOMAINS: frozenset[str] = frozenset(
    _domain(d) for d in _NONSPECIALTY_CHAIN_DOMAINS
)


def is_nonspecialty_domain(website: str | None) -> bool:
    """True if the shop's website domain is a known mass-market chain domain."""
    return _domain(website) in NONSPECIALTY_CHAIN_DOMAINS


def is_social_or_aggregator_domain(website: str | None) -> bool:
    """True if the website is a social/review/blog platform, not the shop's own
    homepage — so a description scraped from it is not a reliable specialty signal.

    Unlike the exact-host chain blocklist, this is suffix-matched: any subdomain
    (``r.gnavi.co.jp``, ``m.facebook.com``) is equally non-homepage.
    """
    host = _domain(website)
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in _SOCIAL_AGGREGATOR_DOMAINS)
