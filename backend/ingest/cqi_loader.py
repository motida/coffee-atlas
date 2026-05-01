"""Load Coffee Quality Institute (CQI) cupping data into origins + processing tables.

Source: data/raw/cqi_arabica.csv, data/raw/cqi_robusta.csv — mirrored from
github.com/jldbc/coffee-quality-database (originally Coffee Quality Institute).

Populates org_countries, org_regions, org_farms, proc_methods. Coordinates
are not populated here; the geocode stage fills them in afterwards.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import duckdb
import polars as pl

from backend.db.connection import get_connection

ORIGIN_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000003")
PROC_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000004")

DEFAULT_ARABICA = Path("data/raw/cqi_arabica.csv")
DEFAULT_ROBUSTA = Path("data/raw/cqi_robusta.csv")

SOURCE_COLUMNS = {
    "Country.of.Origin": "country",
    "Region": "region",
    "Farm.Name": "farm",
    "altitude_mean_meters": "altitude",
    "Processing.Method": "processing",
}

# Maps the free-text "Processing.Method" values CQI uses into a coarse category.
PROCESSING_CATEGORIES: dict[str, str] = {
    "washed / wet": "wet",
    "natural / dry": "dry",
    "pulped natural / honey": "honey",
    "semi-washed / semi-pulped": "semi-washed",
    "other": "other",
}


@dataclass
class IngestCounts:
    countries: int
    regions: int
    farms: int
    methods: int

    def total(self) -> int:
        return self.countries + self.regions + self.farms + self.methods


def _slug(*parts: str) -> str:
    return ":".join(p.strip().lower() for p in parts if p)


def _uid(namespace: uuid.UUID, *parts: str) -> str:
    return str(uuid.uuid5(namespace, _slug(*parts)))


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a", "na"}:
        return None
    return text


def _read_cqi(arabica: Path, robusta: Path) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for path in (arabica, robusta):
        if not path.exists():
            continue
        df = pl.read_csv(path, infer_schema_length=2000, ignore_errors=True)
        present = {src: dst for src, dst in SOURCE_COLUMNS.items() if src in df.columns}
        df = df.select([pl.col(src).alias(dst) for src, dst in present.items()])
        for _, dst in SOURCE_COLUMNS.items():
            if dst not in df.columns:
                df = df.with_columns(pl.lit(None).alias(dst))
        frames.append(df.select(list(SOURCE_COLUMNS.values())))
    if not frames:
        return pl.DataFrame(schema={c: pl.Utf8 for c in SOURCE_COLUMNS.values()})
    return pl.concat(frames, how="vertical_relaxed")


def _build_rows(
    df: pl.DataFrame,
) -> tuple[list[tuple], list[tuple], list[tuple], list[tuple]]:
    countries: dict[str, tuple] = {}
    regions: dict[str, tuple] = {}
    farms: dict[str, tuple] = {}
    methods: dict[str, tuple] = {}

    for row in df.iter_rows(named=True):
        country = _clean(row.get("country"))
        if not country:
            continue
        country_id = _uid(ORIGIN_NAMESPACE, "country", country)
        countries.setdefault(country_id, (country_id, country, None))

        region = _clean(row.get("region"))
        region_id: str | None = None
        if region:
            region_id = _uid(ORIGIN_NAMESPACE, "region", country, region)
            regions.setdefault(region_id, (region_id, region, country_id))

        farm = _clean(row.get("farm"))
        if farm:
            altitude_raw = row.get("altitude")
            altitude = (
                int(altitude_raw)
                if isinstance(altitude_raw, (int, float))
                and altitude_raw == altitude_raw  # NaN check
                else None
            )
            farm_id = _uid(ORIGIN_NAMESPACE, "farm", country, region or "", farm)
            farms.setdefault(farm_id, (farm_id, farm, region_id, altitude))

        method = _clean(row.get("processing"))
        if method:
            method_id = _uid(PROC_NAMESPACE, "method", method)
            category = PROCESSING_CATEGORIES.get(method.lower(), "other")
            methods.setdefault(method_id, (method_id, method, category))

    return (
        list(countries.values()),
        list(regions.values()),
        list(farms.values()),
        list(methods.values()),
    )


def load_cqi_data(
    db_path: str | None = None,
    arabica_path: str | Path = DEFAULT_ARABICA,
    robusta_path: str | Path = DEFAULT_ROBUSTA,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> IngestCounts:
    """Populate origins + processing tables from CQI cupping CSVs.

    Idempotent: deletes existing rows in dependency order before re-inserting.
    Pass `conn` for in-memory test connections; otherwise a connection is opened
    against `db_path` or the configured default.
    """
    df = _read_cqi(Path(arabica_path), Path(robusta_path))
    countries, regions, farms, methods = _build_rows(df)

    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)

    try:
        for table in (
            "edges_farm_variety",
            "edges_region_variety",
            "edges_country_variety",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM org_farms")
        conn.execute("DELETE FROM org_regions")
        conn.execute("DELETE FROM org_countries")
        conn.execute("DELETE FROM proc_methods")

        if countries:
            conn.executemany(
                "INSERT INTO org_countries (id, name, iso_code) VALUES (?, ?, ?)",
                countries,
            )
        if regions:
            conn.executemany(
                "INSERT INTO org_regions (id, name, country_id) VALUES (?, ?, ?)",
                regions,
            )
        if farms:
            conn.executemany(
                "INSERT INTO org_farms (id, name, region_id, altitude) VALUES (?, ?, ?, ?)",
                farms,
            )
        if methods:
            conn.executemany(
                "INSERT INTO proc_methods (id, name, category) VALUES (?, ?, ?)",
                methods,
            )
    finally:
        if owns_conn:
            conn.close()

    return IngestCounts(
        countries=len(countries),
        regions=len(regions),
        farms=len(farms),
        methods=len(methods),
    )


if __name__ == "__main__":
    counts = load_cqi_data()
    print(
        f"Loaded {counts.countries} countries, {counts.regions} regions, "
        f"{counts.farms} farms, {counts.methods} processing methods"
    )
