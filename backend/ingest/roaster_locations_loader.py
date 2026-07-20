"""Fill roast_roasters.location from two sources, curated-first.

Most roasters enter the database through the products scrape
(backend/ingest/products_loader), which records only name + website — so they
arrive with location = NULL and land in the "Other" bucket on the frontend
Roasters page (which groups by the country segment of `location`).

Two stages fill it, in precedence order:

1. ``backfill_roaster_locations`` — the curated override. Matches roaster *name*
   against data/raw/roaster_locations.json ("City, Country" with full country
   names). Authoritative, so it runs first.
2. ``derive_roaster_locations_from_shops`` — automatic, no curation. A roaster's
   ``website`` host usually also appears as a ``shop_shops.website`` (the
   roaster's own cafe, loaded from Overture). That shop carries a ``city`` and an
   ISO ``country`` code; we normalize the code to a full country name via
   data/raw/country_centroids.json and write "City, Country". This fills the
   long tail of scraped roasters the curated map never named — so the frontier
   can grow without hand-maintaining a location per roaster.

Both only ever issue UPDATEs keyed on a roaster id they matched (never insert or
delete — roaster ids are FK-referenced by the product tables, so a delete+insert
would be unsafe), and both fill blanks only by default (pass overwrite=True to
correct existing values). Running curated-first then derive means the curated
value wins and derivation only touches what is still blank.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from backend.ingest._common import managed_connection, site_host

DEFAULT_SOURCE = Path("data/raw/roaster_locations.json")
DEFAULT_CENTROIDS = Path("data/raw/country_centroids.json")


@dataclass
class LocationBackfillCounts:
    updated: int = 0
    already_set: int = 0
    unmatched: list[str] = field(default_factory=list)


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def backfill_roaster_locations(
    db_path: str | None = None,
    source_path: str | Path = DEFAULT_SOURCE,
    conn: duckdb.DuckDBPyConnection | None = None,
    overwrite: bool = False,
) -> LocationBackfillCounts:
    seed = json.loads(Path(source_path).read_text(encoding="utf-8"))
    mapping: dict[str, str] = seed["locations"]

    counts = LocationBackfillCounts()
    with managed_connection(db_path, conn) as conn:
        for name, location in mapping.items():
            rows = conn.execute(
                "SELECT id, location FROM roast_roasters WHERE name = ?", [name]
            ).fetchall()
            if not rows:
                counts.unmatched.append(name)
                continue
            for roaster_id, existing in rows:
                if not _is_blank(existing) and not overwrite:
                    counts.already_set += 1
                    continue
                conn.execute(
                    "UPDATE roast_roasters SET location = ?, updated_at = now() WHERE id = ?",
                    [location, roaster_id],
                )
                counts.updated += 1

    return counts


# --------------------------------------------------------------------------
# Source 2: derive location from the roaster's own Overture shop
# --------------------------------------------------------------------------


@dataclass
class LocationDeriveCounts:
    derived: int = 0
    already_set: int = 0  # skipped: roaster already had a location
    unmatched: int = 0  # roaster has a website but no shop shares its host


def _iso_to_name(centroids_path: str | Path = DEFAULT_CENTROIDS) -> dict[str, str]:
    """alpha-2 ISO code → full country name, from the bundled ISO 3166 file."""
    raw = json.loads(Path(centroids_path).read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for entry in raw["ref_country_codes"]:
        code = (entry.get("alpha2") or "").strip().upper()
        name = (entry.get("country") or "").strip()
        if code and name:
            out[code] = name
    return out


def _country_name(value: str | None, iso_to_name: dict[str, str]) -> str | None:
    """Resolve a shop_shops.country value to a display country name.

    Overture stores the ISO alpha-2 code ("US"), which we map to the full name
    ("United States") so it groups with the curated locations on the frontend.
    A value that isn't a known code (already a full name, or unknown) passes
    through unchanged.
    """
    v = (value or "").strip()
    if not v:
        return None
    return iso_to_name.get(v.upper(), v)


def _index_shop_locations(shop_rows: list[tuple], iso_to_name: dict[str, str]) -> dict[str, str]:
    """host → "City, Country" from shops, choosing the dominant value per host.

    A roaster can have several shops on one host (multiple cafes); we take the
    most common country, then the most common city within it, so one stray
    mis-tagged row can't decide the location.
    """
    by_host: dict[str, list[tuple[str | None, str]]] = {}
    for website, city, country in shop_rows:
        host = site_host(website)
        if host is None:
            continue
        name = _country_name(country, iso_to_name)
        if not name:
            continue
        by_host.setdefault(host, []).append(((city or "").strip() or None, name))

    out: dict[str, str] = {}
    for host, pairs in by_host.items():
        country = Counter(c for _, c in pairs).most_common(1)[0][0]
        cities = [city for city, c in pairs if c == country and city]
        city = Counter(cities).most_common(1)[0][0] if cities else None
        out[host] = f"{city}, {country}" if city else country
    return out


def derive_roaster_locations_from_shops(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
    centroids_path: str | Path = DEFAULT_CENTROIDS,
    overwrite: bool = False,
) -> LocationDeriveCounts:
    """Fill blank roaster locations by matching their website host to a shop."""
    counts = LocationDeriveCounts()
    with managed_connection(db_path, conn) as conn:
        iso_to_name = _iso_to_name(centroids_path)
        shop_rows = conn.execute(
            """
            SELECT website, city, country
            FROM shop_shops
            WHERE website IS NOT NULL AND trim(website) != ''
              AND country IS NOT NULL AND trim(country) != ''
            """
        ).fetchall()
        host_loc = _index_shop_locations(shop_rows, iso_to_name)

        roasters = conn.execute(
            "SELECT id, website, location FROM roast_roasters "
            "WHERE website IS NOT NULL AND trim(website) != ''"
        ).fetchall()
        for roaster_id, website, existing in roasters:
            if not _is_blank(existing) and not overwrite:
                counts.already_set += 1
                continue
            host = site_host(website)
            location = host_loc.get(host) if host else None
            if location is None:
                counts.unmatched += 1
                continue
            conn.execute(
                "UPDATE roast_roasters SET location = ?, updated_at = now() WHERE id = ?",
                [location, roaster_id],
            )
            counts.derived += 1

    return counts


# --------------------------------------------------------------------------
# Source 3: derive product currency from the roaster's location country
# --------------------------------------------------------------------------

# Full country name (the last comma segment of roast_roasters.location, as the
# curated map / ISO-normalized derive write it) → ISO 4217 currency. Only the
# countries the frontier actually spans; an unlisted country leaves currency
# NULL rather than guessing.
_COUNTRY_CURRENCY: dict[str, str] = {
    "United States": "USD",
    "Canada": "CAD",
    "United Kingdom": "GBP",
    "Ireland": "EUR",
    "Germany": "EUR",
    "France": "EUR",
    "Netherlands": "EUR",
    "Belgium": "EUR",
    "Austria": "EUR",
    "Spain": "EUR",
    "Italy": "EUR",
    "Portugal": "EUR",
    "Finland": "EUR",
    "Denmark": "DKK",
    "Norway": "NOK",
    "Sweden": "SEK",
    "Switzerland": "CHF",
    "Israel": "ILS",
    "Japan": "JPY",
    "Australia": "AUD",
    "New Zealand": "NZD",
}


def backfill_product_currency(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Set prod_products.currency from the roaster's location country.

    Scraped storefront prices are denominated in the store's own currency; the
    scraper records it where the platform declares it, and the products loader
    falls back to the site's ccTLD — but records scraped before the currency
    field existed on a generic TLD (.com/.coffee) still land NULL. A roaster in
    Japan prices in JPY, so its location country (filled by the two sources
    above, which is why this runs third) closes most of that gap.

    UPDATE-only and blank-filling: never overwrites a scraper-declared currency,
    so a re-run after a fresh scrape is a no-op for those rows. Returns the
    number of products updated.
    """
    with managed_connection(db_path, conn) as conn:
        updated = 0
        for country, currency in _COUNTRY_CURRENCY.items():
            row = conn.execute(
                """
                UPDATE prod_products SET currency = ?, updated_at = now()
                WHERE currency IS NULL AND price IS NOT NULL
                  AND roaster_id IN (
                      SELECT id FROM roast_roasters
                      WHERE trim(split_part(location, ',', -1)) = ?
                  )
                """,
                [currency, country],
            ).fetchone()
            updated += int(row[0]) if row else 0
    return updated


if __name__ == "__main__":
    curated = backfill_roaster_locations()
    print(f"Curated: filled {curated.updated} ({curated.already_set} already set)")
    if curated.unmatched:
        print(f"  Unmatched names (no roaster row): {curated.unmatched}")
    derived = derive_roaster_locations_from_shops()
    print(
        f"Derived from shops: filled {derived.derived} "
        f"({derived.already_set} already set, {derived.unmatched} unmatched)"
    )
    currencies = backfill_product_currency()
    print(f"Currency from roaster location: filled {currencies} products")
