"""Scrape roaster product catalogs.

Most specialty roasters run Shopify, which exposes a public ``/products.json``
endpoint returning structured product data (title, body_html, tags, vendor,
variants[].price/grams). That is the primary source here; a JSON-LD
``@type: Product`` extractor is the fallback for non-Shopify sites.

This stage only *fetches and normalizes* into ``ScrapedProduct`` records — it
does not touch the database. Resolving the scraped text to graph entities
(variety / origin / flavor / roast) and writing edges is the products_loader's
job (it needs the populated org_*/var_*/flav_* tables).

The pure extraction functions (extract_shopify, extract_jsonld, dedupe_products
and the _detect_* helpers) are unit-tested against a saved fixture
(tests/backend/fixtures/blackwhite_products.json) so the parsing logic is
exercised without hitting live sites.

Resumable via a JSONL log at data/cache/product_scrape/<run_id>.jsonl — re-runs
skip sites already recorded in any prior log for the same scope.

Run:
    uv run -m backend.ingest.shop_scrapers.product_scraper \
        --site https://www.blackwhiteroasters.com \
        --concurrency 4 --max-products 250 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass, field
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

USER_AGENT = "coffee-atlas-bot/0.1 (+https://huggingface.co/spaces/motidav/coffee-atlas-web)"
REQUEST_TIMEOUT = 15.0
MAX_DESCRIPTION_LEN = 1200
SHOPIFY_PAGE_SIZE = 250  # Shopify's max page size for /products.json
CACHE_DIR = Path("data/cache/product_scrape")
DEFAULT_SITES_FILE = Path("data/raw/roaster_sites.txt")

# Roast-level tags → canonical level. Matched case-insensitively against the
# product's Shopify tags (exact tag equality — tags are clean, freeform body
# text is not).
ROAST_LEVELS: dict[str, str] = {
    "light": "light",
    "lighter": "light",
    "blonde": "light",
    "medium": "medium",
    "med": "medium",
    "medium-light": "medium",
    "medium-dark": "medium",
    "dark": "dark",
    "darker": "dark",
    "french": "dark",
    "italian": "dark",
}

# Process tags → canonical process name.
PROCESSES: dict[str, str] = {
    "washed": "Washed",
    "fully washed": "Washed",
    "natural": "Natural",
    "dry": "Natural",
    "honey": "Honey",
    "black honey": "Honey",
    "red honey": "Honey",
    "yellow honey": "Honey",
    "white honey": "Honey",
    "anaerobic": "Anaerobic",
    "carbonic maceration": "Carbonic Maceration",
    "carbonic-maceration": "Carbonic Maceration",
    "co-ferment": "Co-ferment",
    "coferment": "Co-ferment",
    "co ferment": "Co-ferment",
    "wet hulled": "Wet Hulled",
    "wet-hulled": "Wet Hulled",
    "giling basah": "Wet Hulled",
    "semi washed": "Semi-Washed",
    "semi-washed": "Semi-Washed",
}

# Items that are clearly not bagged coffee — filtered out. Conservative on
# purpose: "filter" is omitted because it collides with filter-roast coffee.
_NON_COFFEE = re.compile(
    r"\b(gift\s*card|grinder|kettle|dripper|carafe|mug|tumbler|t-?shirt|apparel|"
    r"tote|beanie|hat|sticker|book|hoodie|crewneck|subscription)\b",
    re.I,
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Word-boundary so "unblended" (single-origin) is not read as a blend.
_BLEND_RE = re.compile(r"\bblend", re.I)
_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


@dataclass
class ScrapedProduct:
    """A normalized product, source-agnostic. Entity resolution is deferred."""

    roaster: str
    title: str
    url: str | None
    description: str
    tags: list[str] = field(default_factory=list)
    product_type: str | None = None
    channel: str = "retail"  # "retail" | "wholesale"
    price: float | None = None
    net_weight_grams: int | None = None
    roast_level: str | None = None
    process: str | None = None
    is_blend: bool = False
    source: str = "shopify"  # "shopify" | "jsonld"


# --------------------------------------------------------------------------
# Pure extraction (unit-tested against the saved fixture)
# --------------------------------------------------------------------------


def _clean_html(html_text: str | None) -> str:
    if not html_text:
        return ""
    text = unescape(_TAG_RE.sub(" ", html_text))
    return _WS_RE.sub(" ", text).strip()[:MAX_DESCRIPTION_LEN]


def _as_tag_list(tags: Any) -> list[str]:
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if str(t).strip()]
    return []


def _roaster_from_site(site_url: str) -> str:
    host = urlparse(site_url).netloc or site_url
    return host.removeprefix("www.")


def detect_roast_level(tags: list[str]) -> str | None:
    for t in tags:
        level = ROAST_LEVELS.get(t.strip().lower())
        if level:
            return level
    return None


def detect_process(tags: list[str]) -> str | None:
    for t in tags:
        proc = PROCESSES.get(t.strip().lower())
        if proc:
            return proc
    return None


def is_blend(title: str, product_type: str | None, tags: list[str]) -> bool:
    haystack = " ".join([title, product_type or "", *tags])
    return _BLEND_RE.search(haystack) is not None


def looks_like_coffee(title: str, product_type: str | None, tags: list[str]) -> bool:
    haystack = " ".join([title, product_type or "", *tags])
    return _NON_COFFEE.search(haystack) is None


def _channel(product_type: str | None, tags: list[str]) -> str:
    haystack = " ".join([product_type or "", *tags]).lower()
    return "wholesale" if "wholesale" in haystack else "retail"


def _variant_price(v: dict[str, Any]) -> float | None:
    raw = v.get("price")
    if raw is None:
        return None
    try:
        value = float(raw)
    except TypeError, ValueError:
        return None
    return value if value > 0 else None  # ignore $0 placeholders (add-ons, quote-only)


def _variant_grams(v: dict[str, Any]) -> int | None:
    g = v.get("grams")
    return int(g) if isinstance(g, (int, float)) and g > 0 else None


def _price_and_grams(variants: Any) -> tuple[float | None, int | None]:
    """Price and net weight of the cheapest real variant (the "from" size).

    Couples the two to one variant so add-on/sample variants — e.g. a $0, 3g
    "Brew Card" — can't donate a bogus weight to an otherwise-priced product.
    """
    priced = [(p, _variant_grams(v)) for v in variants or [] if (p := _variant_price(v))]
    if priced:
        price, grams = min(priced, key=lambda pg: pg[0])
        return price, grams
    # No real price anywhere — still surface a weight if one exists.
    weights = [g for v in variants or [] if (g := _variant_grams(v))]
    return None, (min(weights) if weights else None)


def parse_shopify_product(raw: dict[str, Any], site_url: str) -> ScrapedProduct | None:
    """Normalize one Shopify product dict. Returns None for non-coffee items."""
    title = (raw.get("title") or "").strip()
    if not title:
        return None
    product_type = raw.get("product_type") or None
    tags = _as_tag_list(raw.get("tags"))
    if not looks_like_coffee(title, product_type, tags):
        return None

    price, grams = _price_and_grams(raw.get("variants"))
    handle = (raw.get("handle") or "").strip()
    url = f"{site_url.rstrip('/')}/products/{handle}" if handle else None
    roaster = (raw.get("vendor") or "").strip() or _roaster_from_site(site_url)

    return ScrapedProduct(
        roaster=roaster,
        title=title,
        url=url,
        description=_clean_html(raw.get("body_html")),
        tags=tags,
        product_type=product_type,
        channel=_channel(product_type, tags),
        price=price,
        net_weight_grams=grams,
        roast_level=detect_roast_level(tags),
        process=detect_process(tags),
        is_blend=is_blend(title, product_type, tags),
        source="shopify",
    )


def extract_shopify(payload: dict[str, Any], site_url: str) -> list[ScrapedProduct]:
    """Normalize a Shopify /products.json payload into ScrapedProduct records."""
    out: list[ScrapedProduct] = []
    for raw in payload.get("products") or []:
        product = parse_shopify_product(raw, site_url)
        if product is not None:
            out.append(product)
    return out


def _search_text(text: str, mapping: dict[str, str]) -> str | None:
    """Substring match a canonical-value mapping against freeform text."""
    low = text.lower()
    for key, value in mapping.items():
        if key in low:
            return value
    return None


def _iter_jsonld_products(data: Any) -> list[dict[str, Any]]:
    """Yield every @type=Product object from a parsed JSON-LD blob."""
    out: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            out.extend(_iter_jsonld_products(item))
    elif isinstance(data, dict):
        if "@graph" in data:
            out.extend(_iter_jsonld_products(data["@graph"]))
        types = data.get("@type")
        type_set = {types} if isinstance(types, str) else set(types or [])
        if "Product" in type_set:
            out.append(data)
    return out


def _jsonld_price(offers: Any) -> float | None:
    offer = offers[0] if isinstance(offers, list) and offers else offers
    if not isinstance(offer, dict):
        return None
    raw = offer.get("price") or offer.get("lowPrice")
    try:
        return float(raw) if raw is not None else None
    except TypeError, ValueError:
        return None


def _parse_jsonld_product(obj: dict[str, Any], site_url: str) -> ScrapedProduct | None:
    title = (obj.get("name") or "").strip()
    if not title:
        return None
    description = _clean_html(obj.get("description"))
    if not looks_like_coffee(title, None, []):
        return None
    brand = obj.get("brand")
    roaster = ""
    if isinstance(brand, dict):
        roaster = (brand.get("name") or "").strip()
    elif isinstance(brand, str):
        roaster = brand.strip()
    text = f"{title} {description}"
    return ScrapedProduct(
        roaster=roaster or _roaster_from_site(site_url),
        title=title,
        url=obj.get("url") or site_url,
        description=description,
        tags=[],
        channel="retail",
        price=_jsonld_price(obj.get("offers")),
        roast_level=_search_text(text, ROAST_LEVELS),
        process=_search_text(text, PROCESSES),
        is_blend=_BLEND_RE.search(text) is not None,
        source="jsonld",
    )


def extract_jsonld(html_text: str, site_url: str) -> list[ScrapedProduct]:
    """Extract @type=Product JSON-LD from a single HTML page (Shopify fallback)."""
    out: list[ScrapedProduct] = []
    for match in _JSONLD_RE.finditer(html_text):
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        for obj in _iter_jsonld_products(data):
            product = _parse_jsonld_product(obj, site_url)
            if product is not None:
                out.append(product)
    return out


def _norm_title(title: str) -> str:
    return _WS_RE.sub(" ", title).strip().lower()


def dedupe_products(products: list[ScrapedProduct]) -> list[ScrapedProduct]:
    """Collapse the same product across channels, preferring the retail listing.

    Roasters list the same coffee under retail and wholesale variants; we keep
    one node per (roaster, title) and favor retail (consumer-facing price).
    """
    best: dict[tuple[str, str], ScrapedProduct] = {}
    for product in products:
        key = (product.roaster.lower(), _norm_title(product.title))
        current = best.get(key)
        if current is None or (current.channel == "wholesale" and product.channel == "retail"):
            best[key] = product
    return list(best.values())


# --------------------------------------------------------------------------
# Async fetch + CLI (network; validated via live --dry-run, not unit tests)
# --------------------------------------------------------------------------


@dataclass
class SiteResult:
    site_url: str
    status: str  # "ok" | "empty" | "http_error" | "fetch_error"
    products: list[ScrapedProduct]
    duration_ms: int
    error: str | None = None


def _normalize_site(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


async def _fetch_shopify(
    client: httpx.AsyncClient, site_url: str, max_products: int
) -> tuple[list[dict[str, Any]], int | None]:
    """Page through /products.json. Returns (raw_products, last_http_status)."""
    raw: list[dict[str, Any]] = []
    page = 1
    last_status: int | None = None
    while len(raw) < max_products:
        url = f"{site_url}/products.json?limit={SHOPIFY_PAGE_SIZE}&page={page}"
        resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        last_status = resp.status_code
        if resp.status_code >= 400:
            break
        try:
            batch = resp.json().get("products") or []
        except ValueError, json.JSONDecodeError:
            break
        if not batch:
            break
        raw.extend(batch)
        page += 1
    return raw[:max_products], last_status


async def scrape_site(
    client: httpx.AsyncClient,
    site_url: str,
    sem: asyncio.Semaphore,
    max_products: int,
) -> SiteResult:
    started = time.monotonic()
    async with sem:
        try:
            raw, http_status = await _fetch_shopify(client, site_url, max_products)
        except (httpx.HTTPError, OSError) as e:
            return SiteResult(
                site_url, "fetch_error", [], _ms(started), f"{type(e).__name__}: {e}"[:200]
            )

        if raw:
            products = dedupe_products(extract_shopify({"products": raw}, site_url))
            return SiteResult(site_url, "ok", products, _ms(started))

        # No Shopify catalog — fall back to JSON-LD on the homepage.
        try:
            resp = await client.get(site_url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        except (httpx.HTTPError, OSError) as e:
            return SiteResult(
                site_url, "fetch_error", [], _ms(started), f"{type(e).__name__}: {e}"[:200]
            )
        if resp.status_code >= 400:
            status = "http_error" if http_status and http_status >= 400 else "empty"
            return SiteResult(site_url, status, [], _ms(started))
        products = dedupe_products(extract_jsonld(resp.text[:500_000], site_url))
        return SiteResult(site_url, "ok" if products else "empty", products, _ms(started))


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _completed_sites(cache_dir: Path) -> set[str]:
    """Sites already recorded in any prior JSONL log (for resumability)."""
    done: set[str] = set()
    if not cache_dir.exists():
        return done
    for log in cache_dir.glob("*.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "_site_done" in rec:
                done.add(rec["_site_done"])
    return done


async def scrape(
    sites: list[str],
    *,
    concurrency: int,
    max_products: int,
    run_id: str,
    dry_run: bool,
) -> list[SiteResult]:
    targets = [_normalize_site(s) for s in sites]
    done = _completed_sites(CACHE_DIR)
    pending = [s for s in targets if s not in done]
    skipped = len(targets) - len(pending)
    if skipped:
        print(f"Skipping {skipped} already-scraped site(s).")

    out_path = CACHE_DIR / f"{run_id}.jsonl"
    if not dry_run:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(concurrency)
    results: list[SiteResult] = []
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        tasks = [scrape_site(client, s, sem, max_products) for s in pending]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            print(f"  [{result.status:11}] {len(result.products):4d} products  {result.site_url}")
            if not dry_run:
                _append_jsonl(out_path, result)

    total = sum(len(r.products) for r in results)
    print(f"\n{len(results)} site(s), {total} products" + ("" if dry_run else f" → {out_path}"))
    return results


def read_sites(path: str | Path = DEFAULT_SITES_FILE) -> list[str]:
    """Roaster site URLs from a text file; blank lines and # comments ignored."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def _append_jsonl(path: Path, result: SiteResult) -> None:
    with path.open("a", encoding="utf-8") as f:
        for product in result.products:
            f.write(json.dumps({"site": result.site_url, "product": asdict(product)}) + "\n")
        f.write(json.dumps({"_site_done": result.site_url, "status": result.status}) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape roaster product catalogs")
    parser.add_argument("--site", action="append", default=[], help="Roaster site URL (repeatable)")
    parser.add_argument(
        "--sites-file", help=f"File of site URLs, one per line (default: {DEFAULT_SITES_FILE})"
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-products", type=int, default=SHOPIFY_PAGE_SIZE)
    parser.add_argument("--run-id", default="run", help="JSONL log basename under the cache dir")
    parser.add_argument("--dry-run", action="store_true", help="Print results, write nothing")
    args = parser.parse_args()

    sites = list(args.site)
    if args.sites_file:
        sites += read_sites(args.sites_file)
    if not sites:  # neither --site nor --sites-file given → fall back to the curated list
        sites = read_sites()
    if not sites:
        parser.error("no sites: pass --site/--sites-file or populate the default sites file")

    asyncio.run(
        scrape(
            sites,
            concurrency=args.concurrency,
            max_products=args.max_products,
            run_id=args.run_id,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
