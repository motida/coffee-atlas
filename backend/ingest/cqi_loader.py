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

from backend.ingest._common import deterministic_uuid, managed_connection

ORIGIN_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000003")
PROC_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000004")
EDGE_NAMESPACE = uuid.UUID("6f9b3a0e-1b4c-4e5a-9f3d-c0ffee000005")

DEFAULT_ARABICA = Path("data/raw/cqi_arabica.csv")
DEFAULT_ROBUSTA = Path("data/raw/cqi_robusta.csv")

SOURCE_COLUMNS = {
    "Country.of.Origin": "country",
    "Region": "region",
    "Farm.Name": "farm",
    "altitude_mean_meters": "altitude",
    "Processing.Method": "processing",
    "Variety": "variety",
}

# Synonyms / typo fixes mapping CQI free-text values to WCR canonical names.
# Lowercase keys, lowercase values; consulted before direct lookup.
VARIETY_SYNONYMS: dict[str, str] = {
    "gesha": "geisha (panama)",
    "geisha": "geisha (panama)",
    "marigojipe": "maragogipe",
    "pache comun": "pache",
    "yellow bourbon": "bourbon",
    "catimor": "catimor 129",
}

# CQI rows that aren't varieties (regions, processing styles, bean shapes, or
# umbrella terms with no clean WCR mapping). Skip silently.
VARIETY_BLACKLIST: frozenset[str] = frozenset(
    {
        "",
        "other",
        "peaberry",
        "moka peaberry",
        "ethiopian heirlooms",
        "ethiopian yirgacheffe",
        "blue mountain",
        "hawaiian kona",
        "sumatra",
        "sumatra lintong",
        "mandheling",
        "sulawesi",
        "arusha",
    }
)

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
    country_variety_edges: int = 0
    region_variety_edges: int = 0
    farm_variety_edges: int = 0
    variety_processing_edges: int = 0
    unmatched_varieties: int = 0

    def total(self) -> int:
        return self.countries + self.regions + self.farms + self.methods


def _resolve_variety(raw: str, name_to_id: dict[str, str]) -> str | None:
    """Map a CQI Variety string to a WCR variety_id, or None if unmatched."""
    key = raw.strip().lower()
    if key in VARIETY_BLACKLIST:
        return None
    canonical = VARIETY_SYNONYMS.get(key, key)
    return name_to_id.get(canonical)


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a", "na"}:
        return None
    return text


def _parse_altitude(value: object) -> int | None:
    """Parse a CQI altitude cell to integer meters, or None.

    The source `altitude_mean_meters` column contains "NA" literals, so Polars
    types the whole column as String — meaning even genuinely numeric values
    arrive here as strings. Parse defensively instead of gating on
    isinstance(int | float), which silently dropped every altitude.
    """
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


# Columns on origin/processing tables populated by stages OTHER than this one
# (geocoded coordinates, iso_code, embeddings, manual curation). The CQI rebuild
# uses delete+insert in FK order — DuckDB's ON CONFLICT DO UPDATE can't touch
# FK-referenced rows — so we snapshot these before the delete and restore them by
# id afterward, keeping a standalone `--stage cqi` re-run non-destructive.
_ENRICHMENT_COLUMNS: dict[str, tuple[str, ...]] = {
    "org_countries": ("latitude", "longitude", "iso_code", "production_volume"),
    "org_regions": ("latitude", "longitude", "altitude_min", "altitude_max"),
    "org_farms": ("latitude", "longitude", "soil_type", "owner"),
    "proc_methods": (
        "description",
        "fermentation_duration",
        "drying_duration",
        "description_embedding",
    ),
}


def _snapshot_enrichment(conn: duckdb.DuckDBPyConnection) -> None:
    """Copy enrichment columns into temp tables before the rebuild deletes them.

    Stays entirely inside DuckDB so FLOAT[3072] embeddings are preserved without
    a Python round-trip.
    """
    for table, cols in _ENRICHMENT_COLUMNS.items():
        col_list = ", ".join(("id", *cols))
        conn.execute(
            f"CREATE OR REPLACE TEMP TABLE _enrich_{table} AS SELECT {col_list} FROM {table}"
        )


def _restore_enrichment(conn: duckdb.DuckDBPyConnection) -> None:
    """Re-apply snapshotted enrichment to rebuilt rows, matched by id.

    Rows that dropped out of the source aren't re-created, so they simply don't
    match; new rows have no snapshot entry and keep their NULL enrichment.
    """
    for table, cols in _ENRICHMENT_COLUMNS.items():
        set_clause = ", ".join(f"{c} = e.{c}" for c in cols)
        conn.execute(
            f"UPDATE {table} SET {set_clause} FROM _enrich_{table} AS e WHERE {table}.id = e.id"
        )
        conn.execute(f"DROP TABLE _enrich_{table}")


# Whole ROWS owned by other stages that the FK-ordered rebuild nonetheless
# deletes: importer-only countries inserted by the distribution stage, and the
# edge tables seeded by the processing_flavor and graph stages. Unlike
# enrichment columns (restored by UPDATE onto re-created rows), these rows are
# never re-created by this stage, so they are snapshotted whole and re-inserted.
# Each edge table maps to the parent-exists filter its restore must satisfy —
# parents that dropped out of the CQI source stay gone, and their edges with
# them (product/flavor parents live in tables this stage never touches).
_FOREIGN_EDGE_TABLES: dict[str, str] = {
    "edges_processing_flavor": "method_id IN (SELECT id FROM proc_methods)",
    "edges_product_region": "region_id IN (SELECT id FROM org_regions)",
    "edges_product_country": "country_id IN (SELECT id FROM org_countries)",
    "edges_product_farm": "farm_id IN (SELECT id FROM org_farms)",
    "edges_shop_farm": "farm_id IN (SELECT id FROM org_farms)",
}


def _snapshot_foreign_rows(conn: duckdb.DuckDBPyConnection) -> None:
    """Copy other stages' rows into temp tables before the FK-ordered delete."""
    for table in ("org_countries", *_FOREIGN_EDGE_TABLES):
        conn.execute(f"CREATE OR REPLACE TEMP TABLE _foreign_{table} AS SELECT * FROM {table}")


def _restore_foreign_rows(conn: duckdb.DuckDBPyConnection) -> None:
    """Re-insert other stages' rows the rebuild did not re-create itself.

    Countries first, so restored importer-only countries satisfy the
    edges_product_country parent filter.
    """
    conn.execute(
        "INSERT INTO org_countries SELECT * FROM _foreign_org_countries "
        "WHERE id NOT IN (SELECT id FROM org_countries)"
    )
    conn.execute("DROP TABLE _foreign_org_countries")
    for table, parent_filter in _FOREIGN_EDGE_TABLES.items():
        conn.execute(f"INSERT INTO {table} SELECT * FROM _foreign_{table} WHERE {parent_filter}")
        conn.execute(f"DROP TABLE _foreign_{table}")


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


@dataclass
class _BuiltRows:
    countries: list[tuple]
    regions: list[tuple]
    farms: list[tuple]
    methods: list[tuple]
    country_variety: list[tuple]
    region_variety: list[tuple]
    farm_variety: list[tuple]
    variety_processing: list[tuple]
    unmatched_count: int


def _build_rows(df: pl.DataFrame, name_to_id: dict[str, str]) -> _BuiltRows:
    countries: dict[str, tuple] = {}
    regions: dict[str, tuple] = {}
    farms: dict[str, tuple] = {}
    methods: dict[str, tuple] = {}
    cv_edges: dict[str, tuple] = {}
    rv_edges: dict[str, tuple] = {}
    fv_edges: dict[str, tuple] = {}
    vp_edges: dict[str, tuple] = {}
    unmatched = 0

    for row in df.iter_rows(named=True):
        country = _clean(row.get("country"))
        if not country:
            continue
        country_id = deterministic_uuid(ORIGIN_NAMESPACE, "country", country)
        countries.setdefault(country_id, (country_id, country))

        region = _clean(row.get("region"))
        region_id: str | None = None
        if region:
            region_id = deterministic_uuid(ORIGIN_NAMESPACE, "region", country, region)
            regions.setdefault(region_id, (region_id, region, country_id))

        farm = _clean(row.get("farm"))
        farm_id: str | None = None
        if farm:
            altitude = _parse_altitude(row.get("altitude"))
            farm_id = deterministic_uuid(ORIGIN_NAMESPACE, "farm", country, region or "", farm)
            farms.setdefault(farm_id, (farm_id, farm, region_id, altitude))

        method = _clean(row.get("processing"))
        method_id: str | None = None
        if method:
            method_id = deterministic_uuid(PROC_NAMESPACE, "method", method)
            category = PROCESSING_CATEGORIES.get(method.lower(), "other")
            methods.setdefault(method_id, (method_id, method, category))

        variety_raw = _clean(row.get("variety"))
        if variety_raw:
            variety_id = _resolve_variety(variety_raw, name_to_id)
            if variety_id is None:
                if variety_raw.strip().lower() not in VARIETY_BLACKLIST:
                    unmatched += 1
            else:
                cv_id = deterministic_uuid(EDGE_NAMESPACE, "cv", country_id, variety_id)
                cv_edges.setdefault(cv_id, (cv_id, country_id, variety_id))
                if region_id is not None:
                    rv_id = deterministic_uuid(EDGE_NAMESPACE, "rv", region_id, variety_id)
                    rv_edges.setdefault(rv_id, (rv_id, region_id, variety_id))
                if farm_id is not None:
                    fv_id = deterministic_uuid(EDGE_NAMESPACE, "fv", farm_id, variety_id)
                    fv_edges.setdefault(fv_id, (fv_id, farm_id, variety_id))
                # variety <-> processing co-occurrence: this sample's variety was
                # prepared with this processing method.
                if method_id is not None:
                    vp_id = deterministic_uuid(EDGE_NAMESPACE, "vp", variety_id, method_id)
                    vp_edges.setdefault(vp_id, (vp_id, variety_id, method_id))

    return _BuiltRows(
        countries=list(countries.values()),
        regions=list(regions.values()),
        farms=list(farms.values()),
        methods=list(methods.values()),
        country_variety=list(cv_edges.values()),
        region_variety=list(rv_edges.values()),
        farm_variety=list(fv_edges.values()),
        variety_processing=list(vp_edges.values()),
        unmatched_count=unmatched,
    )


def load_cqi_data(
    db_path: str | None = None,
    arabica_path: str | Path = DEFAULT_ARABICA,
    robusta_path: str | Path = DEFAULT_ROBUSTA,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> IngestCounts:
    """Populate origins + processing tables from CQI cupping CSVs.

    Idempotent: edges and origin/processing rows are rebuilt via delete+insert in
    FK order (DuckDB's ON CONFLICT DO UPDATE can't update FK-referenced rows).
    Everything other stages own that the rebuild disturbs is snapshotted before
    the delete and restored afterward — enrichment columns (geocoded coordinates,
    iso_code, embeddings) by id-matched UPDATE, and whole foreign rows
    (importer-only countries from the distribution stage, the processing_flavor /
    graph stages' edge tables) by re-insert — so a standalone re-run is
    non-destructive.
    Pass `conn` for in-memory test connections; otherwise a connection is opened
    against `db_path` or the configured default.
    """
    df = _read_cqi(Path(arabica_path), Path(robusta_path))

    with managed_connection(db_path, conn) as conn:
        name_to_id = {
            name.lower(): vid
            for vid, name in conn.execute("SELECT id, name FROM var_varieties").fetchall()
        }
        built = _build_rows(df, name_to_id)

        _snapshot_enrichment(conn)
        _snapshot_foreign_rows(conn)

        for table in (
            "edges_farm_variety",
            "edges_region_variety",
            "edges_country_variety",
            "edges_region_farm",
            "edges_country_region",
            "edges_variety_processing",
            "edges_processing_flavor",
            "edges_product_region",
            "edges_product_country",
            "edges_product_farm",
            "edges_shop_farm",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM org_farms")
        conn.execute("DELETE FROM org_regions")
        conn.execute("DELETE FROM org_countries")
        conn.execute("DELETE FROM proc_methods")

        if built.countries:
            conn.executemany(
                "INSERT INTO org_countries (id, name) VALUES (?, ?)",
                built.countries,
            )
        if built.regions:
            conn.executemany(
                "INSERT INTO org_regions (id, name, country_id) VALUES (?, ?, ?)",
                built.regions,
            )
        if built.farms:
            conn.executemany(
                "INSERT INTO org_farms (id, name, region_id, altitude) VALUES (?, ?, ?, ?)",
                built.farms,
            )
        if built.methods:
            conn.executemany(
                "INSERT INTO proc_methods (id, name, category) VALUES (?, ?, ?)",
                built.methods,
            )

        _restore_enrichment(conn)
        _restore_foreign_rows(conn)

        if built.country_variety:
            conn.executemany(
                "INSERT INTO edges_country_variety (id, country_id, variety_id) VALUES (?, ?, ?)",
                built.country_variety,
            )
        if built.region_variety:
            conn.executemany(
                "INSERT INTO edges_region_variety (id, region_id, variety_id) VALUES (?, ?, ?)",
                built.region_variety,
            )
        if built.farm_variety:
            conn.executemany(
                "INSERT INTO edges_farm_variety (id, farm_id, variety_id) VALUES (?, ?, ?)",
                built.farm_variety,
            )
        if built.variety_processing:
            conn.executemany(
                "INSERT INTO edges_variety_processing (id, variety_id, method_id) VALUES (?, ?, ?)",
                built.variety_processing,
            )

    return IngestCounts(
        countries=len(built.countries),
        regions=len(built.regions),
        farms=len(built.farms),
        methods=len(built.methods),
        country_variety_edges=len(built.country_variety),
        region_variety_edges=len(built.region_variety),
        farm_variety_edges=len(built.farm_variety),
        variety_processing_edges=len(built.variety_processing),
        unmatched_varieties=built.unmatched_count,
    )


if __name__ == "__main__":
    counts = load_cqi_data()
    print(
        f"Loaded {counts.countries} countries, {counts.regions} regions, "
        f"{counts.farms} farms, {counts.methods} processing methods"
    )
    print(
        f"Variety edges → country: {counts.country_variety_edges}, "
        f"region: {counts.region_variety_edges}, farm: {counts.farm_variety_edges}, "
        f"processing: {counts.variety_processing_edges} "
        f"({counts.unmatched_varieties} unmatched)"
    )
