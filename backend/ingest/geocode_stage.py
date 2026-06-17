"""Geocode org_countries and org_regions in place.

Countries are resolved against the bundled ISO 3166 centroid table; regions are
resolved via Nominatim (rate-limited, on-disk cached). Both passes are
idempotent — only rows missing lat/lng are touched.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from backend.ingest._common import managed_connection
from backend.services.geocoding import (
    Geocoder,
    NominatimGeocoder,
    load_country_centroids,
    resolve_country,
)


@dataclass
class GeocodeCounts:
    countries_resolved: int
    countries_unresolved: int
    regions_resolved: int
    regions_unresolved: int


def geocode_countries(conn: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    centroids = load_country_centroids()
    rows = conn.execute(
        "SELECT id, name FROM org_countries WHERE latitude IS NULL OR longitude IS NULL"
    ).fetchall()
    resolved = 0
    unresolved: list[str] = []
    for cid, name in rows:
        pt = resolve_country(name, centroids)
        if pt is None:
            unresolved.append(name)
            continue
        conn.execute(
            "UPDATE org_countries SET latitude = ?, longitude = ?, iso_code = ? WHERE id = ?",
            [pt.latitude, pt.longitude, pt.iso_code, cid],
        )
        resolved += 1
    if unresolved:
        print(f"  Unresolved countries: {', '.join(unresolved)}")
    return resolved, len(unresolved)


def geocode_regions(
    conn: duckdb.DuckDBPyConnection,
    geocoder: Geocoder,
    limit: int | None = None,
) -> tuple[int, int]:
    sql = """
        SELECT r.id, r.name, c.name AS country_name, c.iso_code
        FROM org_regions r
        JOIN org_countries c ON r.country_id = c.id
        WHERE r.latitude IS NULL OR r.longitude IS NULL
    """
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    resolved = 0
    unresolved = 0
    for rid, name, country_name, iso in rows:
        query = f"{name}, {country_name}"
        pt = geocoder.lookup(query, country_iso=iso)
        if pt is None:
            unresolved += 1
            continue
        conn.execute(
            "UPDATE org_regions SET latitude = ?, longitude = ? WHERE id = ?",
            [pt.latitude, pt.longitude, rid],
        )
        resolved += 1
    return resolved, unresolved


def run_geocode(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
    geocoder: Geocoder | None = None,
    region_limit: int | None = None,
) -> GeocodeCounts:
    """Run both geocode passes. Pass `geocoder` to inject a fake in tests."""
    with managed_connection(db_path, conn) as conn:
        owns_geocoder = geocoder is None
        if geocoder is None:
            geocoder = NominatimGeocoder()
        try:
            c_ok, c_miss = geocode_countries(conn)
            r_ok, r_miss = geocode_regions(conn, geocoder, limit=region_limit)
        finally:
            if owns_geocoder and isinstance(geocoder, NominatimGeocoder):
                geocoder.close()

    return GeocodeCounts(
        countries_resolved=c_ok,
        countries_unresolved=c_miss,
        regions_resolved=r_ok,
        regions_unresolved=r_miss,
    )


if __name__ == "__main__":
    counts = run_geocode()
    print(
        f"Countries: {counts.countries_resolved} resolved, "
        f"{counts.countries_unresolved} unresolved | "
        f"Regions: {counts.regions_resolved} resolved, "
        f"{counts.regions_unresolved} unresolved"
    )
