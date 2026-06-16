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

from backend.db.connection import get_connection

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
    r"mug|tumbler|tote|hoodie|t-?shirt|tee|beanie|candle|poster|sticker|"
    r"kanteen|bottle|sock|"
    r"sampler|bundle|gift|sample\s*set|tasting\s*set|filters?|cleaning|sets?)\b",
    re.I,
)

# Non-coffee product_type categories. These disqualify UNLESS the type string
# also mentions coffee (some stores file a coffee under "...,Gifts" collections).
_NON_COFFEE_TYPE = re.compile(
    r"\b(tea|machine|grinder|equipment|brewers?|brewing|gear|accessor\w*|"
    r"drinkware|merch\w*|apparel|logoware|supplies|warehouse|event|ticket|"
    r"subscription|carbon\s*offset|alt\s*beverage|cleaning|gift)\b",
    re.I,
)


@dataclass
class ProductCounts:
    roasters: int
    products: int
    dropped_non_coffee: int


def _slug(*parts: str) -> str:
    return ":".join(p.strip().lower() for p in parts if p)


def _uid(*parts: str) -> str:
    return str(uuid.uuid5(PRODUCT_NAMESPACE, _slug(*parts)))


def classify_coffee(title: str, product_type: str | None, tags: list[str]) -> bool:
    """A coffee product unless its title or type clearly says otherwise.

    Title hard-negatives (brewers, merch, filters, bundles/sets) always win.
    A non-coffee product_type disqualifies only when the type doesn't itself
    mention coffee — guards stores that file a coffee under e.g. "...,Gifts".
    """
    if _NON_COFFEE_TITLE.search(title):
        return False
    pt = product_type or ""
    if pt and _NON_COFFEE_TYPE.search(pt) and not re.search(r"coffee", pt, re.I):
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
            obj = json.loads(line)
            if "product" not in obj:  # skip _site_done markers
                continue
            product = dict(obj["product"])
            product["site"] = obj.get("site")
            records.append(product)
    return records


def _roaster_name_by_site(coffee_records: list[dict[str, Any]]) -> dict[str, str]:
    """Per site, the roaster name = modal vendor among its coffee products."""
    vendors: dict[str, Counter[str]] = {}
    for rec in coffee_records:
        site = rec.get("site") or ""
        vendor = (rec.get("roaster") or "").strip()
        if vendor:
            vendors.setdefault(site, Counter())[vendor] += 1
    names: dict[str, str] = {}
    for site, counter in vendors.items():
        names[site] = counter.most_common(1)[0][0]
    return names


def _name_from_domain(site: str) -> str:
    host = urlparse(site).netloc or site
    return host.removeprefix("www.")


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
    # Reuse an existing roaster row when the name already exists (e.g. from the
    # roasting seed) so we don't create a duplicate node under a fresh id.
    existing_roasters = {
        name: rid for rid, name in conn.execute("SELECT id, name FROM roast_roasters").fetchall()
    }

    roasters: dict[str, tuple[str, str, str | None]] = {}  # id -> (id, name, website)
    products: dict[str, tuple[Any, ...]] = {}
    for rec in coffee:
        site = rec.get("site") or ""
        roaster_name = site_roaster.get(site) or _name_from_domain(site)
        roaster_id = existing_roasters.get(roaster_name) or _uid("roaster", roaster_name)
        roasters[roaster_id] = (roaster_id, roaster_name, site or None)

        title = (rec.get("title") or "").strip()
        if not title:
            continue
        product_id = _uid("product", site, title)
        products[product_id] = (
            product_id,
            title,
            roaster_id,
            rec.get("roast_level"),
            rec.get("process"),
            rec.get("is_blend"),
            rec.get("price"),
            rec.get("net_weight_grams"),
            rec.get("url"),
            rec.get("description"),
        )

    # FK-safe write order: clear product-referencing edges, then products, then
    # upsert roasters (DO NOTHING — never clobber the roasting domain's rows).
    for table in (
        "edges_product_variety",
        "edges_product_region",
        "edges_product_country",
        "edges_product_flavor",
        "edges_product_roast",
        "edges_shop_product",
        "edges_roaster_product",
        "prod_products",
    ):
        conn.execute(f"DELETE FROM {table}")

    conn.executemany(
        """
        INSERT INTO roast_roasters (id, name, website) VALUES (?, ?, ?)
        ON CONFLICT (id) DO NOTHING
        """,
        [(rid, name, website) for rid, name, website in roasters.values()],
    )
    conn.executemany(
        """
        INSERT INTO prod_products
            (id, name, roaster_id, roast_level, process, is_blend, price,
             net_weight_grams, url, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)
    try:
        return load_products(records, conn)
    finally:
        if owns_conn:
            conn.close()


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
