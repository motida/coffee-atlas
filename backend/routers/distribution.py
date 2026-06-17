"""Distribution domain endpoints: importers, certifications, trade routes.

The trade-route geo endpoint returns LineString features connecting
exporter and importer country centroids — the data source for the
animated trade-flow arcs layer on the landing map.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import fetchall_dicts, get_db
from backend.db.geojson import feature_collection, linestring_feature
from backend.models.distribution import CertificationRead, ImporterRead, TradeRouteRead

router = APIRouter(prefix="/api/v1/distribution", tags=["distribution"])


@router.get("/importers", response_model=list[ImporterRead])
def list_importers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute(
            """
            SELECT i.*, c.name AS country_name
            FROM dist_importers i
            LEFT JOIN org_countries c ON i.country_id = c.id
            ORDER BY i.name
            LIMIT ? OFFSET ?
            """,
            [limit, offset],
        )
    )


@router.get("/certifications", response_model=list[CertificationRead])
def list_certifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute(
            "SELECT * FROM dist_certifications ORDER BY name LIMIT ? OFFSET ?",
            [limit, offset],
        )
    )


@router.get("/trade-routes", response_model=list[TradeRouteRead])
def list_trade_routes(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute(
            """
            SELECT r.*, e.name AS exporter_name, i.name AS importer_name
            FROM dist_trade_routes r
            LEFT JOIN org_countries e ON r.exporter_country_id = e.id
            LEFT JOIN org_countries i ON r.importer_country_id = i.id
            ORDER BY exporter_name, importer_name
            LIMIT ? OFFSET ?
            """,
            [limit, offset],
        )
    )


@router.get("/trade-routes/geo")
def get_trade_routes_geo(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    """Trade routes as GeoJSON LineStrings (exporter → importer centroids)."""
    rows = fetchall_dicts(
        db.execute(
            """
            SELECT r.id, r.annual_volume, r.year,
                   e.id AS exporter_id, e.name AS exporter_name,
                   e.longitude AS exporter_lon, e.latitude AS exporter_lat,
                   i.id AS importer_id, i.name AS importer_name,
                   i.longitude AS importer_lon, i.latitude AS importer_lat
            FROM dist_trade_routes r
            JOIN org_countries e ON r.exporter_country_id = e.id
            JOIN org_countries i ON r.importer_country_id = i.id
            WHERE e.latitude IS NOT NULL AND e.longitude IS NOT NULL
              AND i.latitude IS NOT NULL AND i.longitude IS NOT NULL
            """
        )
    )
    features = [
        linestring_feature(
            [
                [row["exporter_lon"], row["exporter_lat"]],
                [row["importer_lon"], row["importer_lat"]],
            ],
            {
                "id": row["id"],
                "exporter_id": row["exporter_id"],
                "exporter_name": row["exporter_name"],
                "importer_id": row["importer_id"],
                "importer_name": row["importer_name"],
                "annual_volume": row["annual_volume"],
                "year": row["year"],
            },
        )
        for row in rows
    ]
    return feature_collection(features)
