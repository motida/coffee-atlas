"""Resolve graph edges for the products domain.

Two kinds of edge:

Content edges — match scraped product text against the populated entity tables:
  product → country / region   (origin named in title or description)
  product → variety            (e.g. Gesha, Bourbon, Pacas)
  product → flavor             (tasting notes in the description)
  product → roast_profile      (shared roast level)

Derived edges — structural, from FKs and the website graph:
  roaster → product            (prod_products.roaster_id)
  shop → roaster               (shop.website domain == roaster.website domain)
  shop → product               (shop → roaster → product)
  shop → variety               (shop → product → variety; finally fills the
                                long-empty edges_shop_variety)

Matching is deliberately conservative — word-boundary, length-floored, and
flavor restricted to non-root lexicon attributes (so generic category words
like "Roasted" don't match roast prose). Origin/variety are matched in title +
description (a blend legitimately names several origins); flavor only in the
description. Match rates are returned so callers can see coverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import duckdb

# Length floors keep short, ambiguous names from over-matching.
_MIN_COUNTRY = 4
_MIN_REGION = 4
_MIN_VARIETY = 3
_MIN_FLAVOR = 4

# Flavor names that collide with process/roast vocabulary in prose.
_FLAVOR_STOPWORDS = {"honey"}


# SQL: a website column normalized to its bare registrable-ish domain.
def _domain_sql(col: str) -> str:
    return (
        f"split_part(split_part(lower("
        f"regexp_replace({col}, '^https?://(www\\.)?', '')), '/', 1), '?', 1)"
    )


@dataclass
class EdgeCounts:
    product_country: int
    product_region: int
    product_variety: int
    product_flavor: int
    product_roast: int
    roaster_product: int
    shop_roaster: int
    shop_product: int
    shop_variety: int


def _compiled(pairs: list[tuple[str, str]], minlen: int, alias: bool = False):
    """(id, name) → (id, compiled word-boundary regex), filtered by length."""
    out = []
    for ent_id, name in pairs:
        if not name or len(name) < minlen:
            continue
        pattern = re.escape(name.lower())
        if alias and "geisha" in name.lower():
            pattern = pattern.replace("geisha", "g[ei]+sha")  # Gesha/Geisha
        out.append((ent_id, re.compile(rf"\b{pattern}\b")))
    return out


def _replace(
    conn: duckdb.DuckDBPyConnection, table: str, dst_col: str, rows: list[tuple[str, str, str]]
) -> None:
    """Clear an edge table and bulk-insert rows (DuckDB rejects an empty batch)."""
    conn.execute(f"DELETE FROM {table}")
    if rows:
        conn.executemany(f"INSERT INTO {table} (id, product_id, {dst_col}) VALUES (?, ?, ?)", rows)


def _content_edges(
    conn: duckdb.DuckDBPyConnection,
) -> tuple[int, int, int, int, int]:
    products = conn.execute(
        "SELECT id, lower(name), lower(COALESCE(description, '')) FROM prod_products"
    ).fetchall()

    countries = _compiled(
        conn.execute("SELECT id, name FROM org_countries").fetchall(), _MIN_COUNTRY
    )
    regions = _compiled(conn.execute("SELECT id, name FROM org_regions").fetchall(), _MIN_REGION)
    varieties = _compiled(
        conn.execute("SELECT id, name FROM var_varieties").fetchall(), _MIN_VARIETY, alias=True
    )
    flavors = _compiled(
        [
            (i, n)
            for i, n in conn.execute(
                "SELECT id, name FROM flav_attributes WHERE parent_id IS NOT NULL"
            ).fetchall()
            if n and n.lower() not in _FLAVOR_STOPWORDS
        ],
        _MIN_FLAVOR,
    )

    pc, pr, pv, pf = [], [], [], []
    for pid, name, desc in products:
        title_blob = f"{name} {desc}"
        for cid, rx in countries:
            if rx.search(title_blob):
                pc.append((f"pc:{pid}:{cid}", pid, cid))
        for rid, rx in regions:
            if rx.search(title_blob):
                pr.append((f"prg:{pid}:{rid}", pid, rid))
        for vid, rx in varieties:
            if rx.search(title_blob):
                pv.append((f"pv:{pid}:{vid}", pid, vid))
        for fid, rx in flavors:
            if rx.search(desc):
                pf.append((f"pf:{pid}:{fid}", pid, fid))

    _replace(conn, "edges_product_country", "country_id", pc)
    _replace(conn, "edges_product_region", "region_id", pr)
    _replace(conn, "edges_product_variety", "variety_id", pv)
    _replace(conn, "edges_product_flavor", "flavor_id", pf)

    # product → roast_profile: shared roast level (set-based; sparse).
    conn.execute("DELETE FROM edges_product_roast")
    conn.execute(
        """
        INSERT INTO edges_product_roast (id, product_id, profile_id)
        SELECT 'pro:' || p.id || ':' || rp.id, p.id, rp.id
        FROM prod_products p
        JOIN roast_profiles rp ON lower(p.roast_level) = lower(rp.roast_level)
        WHERE p.roast_level IS NOT NULL
        """
    )
    proast = _count(conn, "edges_product_roast")
    return len(pc), len(pr), len(pv), len(pf), proast


def _count(conn: duckdb.DuckDBPyConnection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return row[0]


def _derived_edges(conn: duckdb.DuckDBPyConnection) -> tuple[int, int, int, int]:
    # roaster → product (from the FK).
    conn.execute("DELETE FROM edges_roaster_product")
    conn.execute(
        """
        INSERT INTO edges_roaster_product (id, roaster_id, product_id)
        SELECT 'rp:' || roaster_id || ':' || id, roaster_id, id
        FROM prod_products WHERE roaster_id IS NOT NULL
        """
    )

    # shop → roaster (matching website domains).
    conn.execute("DELETE FROM edges_shop_roaster")
    conn.execute(
        f"""
        INSERT INTO edges_shop_roaster (id, shop_id, roaster_id)
        WITH s AS (
            SELECT id AS shop_id, {_domain_sql("website")} AS dom
            FROM shop_shops WHERE website IS NOT NULL AND website <> ''
        ), r AS (
            SELECT id AS roaster_id, {_domain_sql("website")} AS dom
            FROM roast_roasters WHERE website IS NOT NULL AND website <> ''
        )
        SELECT DISTINCT 'sr:' || s.shop_id || ':' || r.roaster_id, s.shop_id, r.roaster_id
        FROM s JOIN r ON s.dom = r.dom AND s.dom <> ''
        """
    )

    # shop → product (shop → roaster → product).
    conn.execute("DELETE FROM edges_shop_product")
    conn.execute(
        """
        INSERT INTO edges_shop_product (id, shop_id, product_id)
        SELECT DISTINCT 'sp:' || sr.shop_id || ':' || rp.product_id, sr.shop_id, rp.product_id
        FROM edges_shop_roaster sr
        JOIN edges_roaster_product rp ON sr.roaster_id = rp.roaster_id
        """
    )

    # shop → variety (shop → product → variety) — fills the long-empty table.
    conn.execute("DELETE FROM edges_shop_variety")
    conn.execute(
        """
        INSERT INTO edges_shop_variety (id, shop_id, variety_id)
        SELECT DISTINCT 'sv:' || sp.shop_id || ':' || pv.variety_id, sp.shop_id, pv.variety_id
        FROM edges_shop_product sp
        JOIN edges_product_variety pv ON sp.product_id = pv.product_id
        """
    )

    return (
        _count(conn, "edges_roaster_product"),
        _count(conn, "edges_shop_roaster"),
        _count(conn, "edges_shop_product"),
        _count(conn, "edges_shop_variety"),
    )


def resolve_product_edges(conn: duckdb.DuckDBPyConnection) -> EdgeCounts:
    """Populate all product content + derived edges. Returns per-edge counts."""
    pc, prg, pv, pf, pro = _content_edges(conn)
    rp, sr, sp, sv = _derived_edges(conn)
    return EdgeCounts(
        product_country=pc,
        product_region=prg,
        product_variety=pv,
        product_flavor=pf,
        product_roast=pro,
        roaster_product=rp,
        shop_roaster=sr,
        shop_product=sp,
        shop_variety=sv,
    )


if __name__ == "__main__":
    from backend.db.connection import get_connection

    conn = get_connection()
    try:
        counts = resolve_product_edges(conn)
    finally:
        conn.close()
    for field, value in counts.__dict__.items():
        print(f"  {field:18} {value}")
