"""Origin domain endpoints: producing countries, regions, and their map GeoJSON."""

from typing import Any

import duckdb
from fastapi import APIRouter, Depends, Query

from backend.db.connection import fetchall_dicts, get_db
from backend.db.geojson import feature_collection, point_feature
from backend.models.origins import CountryRead, RegionRead
from backend.routers._helpers import fetchone_or_404

router = APIRouter(prefix="/api/v1/origins", tags=["origins"])


@router.get("", response_model=list[CountryRead])
def list_origins(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[dict[str, Any]]:
    return fetchall_dicts(
        db.execute("SELECT * FROM org_countries LIMIT ? OFFSET ?", [limit, offset])
    )


@router.get("/geo")
def get_origins_geo(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    rows = fetchall_dicts(
        db.execute(
            "SELECT id, name, iso_code, latitude, longitude, production_volume "
            "FROM org_countries WHERE latitude IS NOT NULL"
        )
    )
    features = [point_feature(row["longitude"], row["latitude"], row) for row in rows]
    return feature_collection(features)


@router.get("/regions/geo")
def get_regions_geo(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    rows = fetchall_dicts(
        db.execute(
            """
            SELECT r.id, r.name, r.latitude, r.longitude,
                   c.name AS country_name, c.iso_code
            FROM org_regions r
            JOIN org_countries c ON r.country_id = c.id
            WHERE r.latitude IS NOT NULL
            """
        )
    )
    features = [point_feature(row["longitude"], row["latitude"], row) for row in rows]
    return feature_collection(features)


@router.get("/regions/{region_id}", response_model=RegionRead)
def get_region(region_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    return fetchone_or_404(
        db.execute("SELECT * FROM org_regions WHERE id = ?", [region_id]), "Region"
    )


@router.get("/{origin_id}", response_model=CountryRead)
def get_origin(origin_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict[str, Any]:
    return fetchone_or_404(
        db.execute("SELECT * FROM org_countries WHERE id = ?", [origin_id]), "Origin"
    )
