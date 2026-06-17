"""Load coffee shops from Overture Maps Places.

Queries the Overture `places` theme directly from the public S3 bucket via
DuckDB's `httpfs` + `spatial` extensions, filters to coffee-related
categories, and populates `shop_shops`.

No API key required — Overture is ODbL public data.

The default Overture release is pinned for reproducible bootstraps. To bump
to a newer release, set `OVERTURE_RELEASE` in the environment, e.g.:

    OVERTURE_RELEASE=2026-04-15.0 just ingest shops

Release history: https://docs.overturemaps.org/release/

Bbox filter: a global scan of Overture places (~10 GB across 16 parquet
files) is impractical over residential networks. We filter on the parquet
`bbox` column so DuckDB can skip row groups that fall entirely outside the
target box via parquet statistics. The default bbox covers the contiguous
US, expandable via `OVERTURE_BBOX` (`xmin,ymin,xmax,ymax`) or programmatic
override.

Notes:
- This stage is **not** part of `just bootstrap` / `just ingest-all`. It hits
  S3; even with a bbox filter expect several minutes for a country-sized
  region. Run it explicitly with `just ingest shops`.
- Quality varies; `confidence` is used as a coarse filter and downstream
  curation is expected.
"""

from __future__ import annotations

import os
import re
import urllib.request
from dataclasses import dataclass

import duckdb

from backend.ingest._common import managed_connection

OVERTURE_RELEASE = os.environ.get("OVERTURE_RELEASE", "2026-04-15.0")
OVERTURE_BUCKET = "overturemaps-us-west-2"
OVERTURE_PLACES_PREFIX = f"release/{OVERTURE_RELEASE}/theme=places/type=place/"

COFFEE_CATEGORIES: tuple[str, ...] = ("coffee_shop", "cafe")
DEFAULT_MIN_CONFIDENCE = 0.3

# Contiguous US — broad enough to be a meaningful demo, tight enough to
# pull through a residential connection in a few minutes.
DEFAULT_BBOX = (-125.0, 24.0, -66.0, 50.0)


def _resolve_bbox() -> tuple[float, float, float, float]:
    raw = os.environ.get("OVERTURE_BBOX")
    if not raw:
        return DEFAULT_BBOX
    parts = [float(x) for x in raw.split(",")]
    if len(parts) != 4:
        raise ValueError(f"OVERTURE_BBOX must be 'xmin,ymin,xmax,ymax', got: {raw!r}")
    return (parts[0], parts[1], parts[2], parts[3])


@dataclass
class ShopIngestCounts:
    fetched: int
    inserted: int


def _ensure_extensions(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    conn.execute("INSTALL spatial;")
    conn.execute("LOAD spatial;")
    conn.execute("SET s3_region='us-west-2';")


def _list_overture_files(prefix: str = OVERTURE_PLACES_PREFIX) -> list[str]:
    """List parquet files under a prefix via S3 REST. DuckDB's `*` glob over
    httpfs hangs on this dataset; an explicit file list sidesteps it."""
    url = f"https://{OVERTURE_BUCKET}.s3.us-west-2.amazonaws.com/?prefix={prefix}"
    xml = urllib.request.urlopen(url, timeout=30).read().decode()
    keys = re.findall(r"<Key>([^<]+)</Key>", xml)
    files = [f"s3://{OVERTURE_BUCKET}/{k}" for k in keys if k.endswith(".parquet")]
    if not files:
        raise RuntimeError(f"No parquet files found under s3://{OVERTURE_BUCKET}/{prefix}")
    return files


def _category_predicate() -> str:
    quoted = ", ".join(f"'{c}'" for c in COFFEE_CATEGORIES)
    return f"categories.primary IN ({quoted})"


def _bbox_predicate(bboxes: list[tuple[float, float, float, float]]) -> str:
    clauses = [
        f"(bbox.xmin >= {xmin} AND bbox.xmax <= {xmax} "
        f"AND bbox.ymin >= {ymin} AND bbox.ymax <= {ymax})"
        for xmin, ymin, xmax, ymax in bboxes
    ]
    return "(" + " OR ".join(clauses) + ")"


def _merge_shops(conn: duckdb.DuckDBPyConnection) -> None:
    """Upsert candidate rows from the `_overture_shops` temp table into shop_shops.

    Source-owned columns (name, coordinates, address, website) are refreshed, but
    curated enrichment — rating, roasts_in_house, description, description_embedding
    — and created_at are preserved on rows that already exist. New rows get NULL
    enrichment. This replaces a prior INSERT OR REPLACE that nulled enrichment and
    reset created_at on every overlapping re-run.
    """
    conn.execute(
        """
        INSERT INTO shop_shops (
            id, name, latitude, longitude, address, city, country, website
        )
        SELECT id, name, latitude, longitude, address, city, country, website
        FROM _overture_shops
        QUALIFY row_number() OVER (PARTITION BY id ORDER BY confidence DESC) = 1
        ON CONFLICT (id) DO UPDATE SET
            name = excluded.name,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            address = excluded.address,
            city = excluded.city,
            country = excluded.country,
            website = excluded.website,
            updated_at = now()
        """
    )


def load_overture_shops(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
    files: list[str] | None = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    bbox: tuple[float, float, float, float] | None = None,
    bboxes: list[tuple[float, float, float, float]] | None = None,
) -> ShopIngestCounts:
    """Pull coffee shops from Overture into shop_shops. Additive and idempotent.

    Existing rows with the same Overture `id` are upserted in place — source
    fields refresh while curated enrichment (rating, description, etc.) and
    created_at are preserved (see `_merge_shops`); rows outside the supplied
    bboxes are left untouched. Pass `bboxes` (multiple regions in one S3 scan)
    or `bbox` (single region, backward-compat).
    """
    if bboxes is None:
        bboxes = [bbox] if bbox is not None else [_resolve_bbox()]

    with managed_connection(db_path, conn) as conn:
        _ensure_extensions(conn)

        if files is None:
            files = _list_overture_files()
        print(
            f"Overture release {OVERTURE_RELEASE}: {len(files)} parquet files, "
            f"{len(bboxes)} bbox(es)={bboxes}"
        )

        conn.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE _overture_shops AS
            SELECT
                id,
                names.primary AS name,
                ST_X(geometry) AS longitude,
                ST_Y(geometry) AS latitude,
                addresses[1].freeform AS address,
                addresses[1].locality AS city,
                addresses[1].country AS country,
                websites[1] AS website,
                confidence
            FROM read_parquet({files!r})
            WHERE {_bbox_predicate(bboxes)}
              AND {_category_predicate()}
              AND names.primary IS NOT NULL
              AND geometry IS NOT NULL
              AND confidence >= {min_confidence}
            """
        )

        row = conn.execute("SELECT COUNT(*) FROM _overture_shops").fetchone()
        assert row is not None
        fetched = int(row[0])
        print(f"Fetched {fetched} candidate rows from Overture")

        _merge_shops(conn)

        row = conn.execute("SELECT COUNT(*) FROM shop_shops").fetchone()
        assert row is not None
        inserted = int(row[0])

    return ShopIngestCounts(fetched=fetched, inserted=inserted)


if __name__ == "__main__":
    counts = load_overture_shops()
    print(f"Inserted {counts.inserted} shops from {counts.fetched} candidates")
