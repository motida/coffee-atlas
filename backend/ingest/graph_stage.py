"""Build graph edges from populated source tables.

This stage materializes the edges that are derived rather than ingested:

1. country -> region (from org_regions.country_id)
2. region -> farm   (from org_farms.region_id)
3. variety <-> flavor (top-K matches via embedding cosine similarity)

The origin -> variety edges (country/region/farm -> variety) and the
variety <-> processing edges are populated upstream by the CQI loader from
cupping-sample co-occurrence; the property graph below stitches them
together with the edges above into a single connected graph that links the
geographic hierarchy to the variety/flavor/processing clusters.

Edges still blocked on data we don't yet have: shop -> variety (shop data
carries no variety references), roast -> variety (no roasting loader yet),
and processing -> flavor (no source linking the two).

A DuckPGQ PROPERTY GRAPH is defined for parity with the architecture
spec, but the HTTP endpoints do not depend on it — they query the edge
tables directly so the API still works if the extension is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from backend.db.connection import get_connection

VARIETY_FLAVOR_TOP_K: int = 5
VARIETY_FLAVOR_THRESHOLD: float = 0.4


@dataclass(frozen=True)
class GraphCounts:
    country_region: int
    region_farm: int
    variety_flavor: int
    property_graph_ok: bool


def _count(conn: duckdb.DuckDBPyConnection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return row[0]


def populate_geo_edges(conn: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    """Materialize country->region and region->farm from FK columns."""
    conn.execute("DELETE FROM edges_country_region")
    conn.execute(
        """
        INSERT INTO edges_country_region (id, country_id, region_id)
        SELECT 'cr:' || country_id || ':' || id, country_id, id
        FROM org_regions
        WHERE country_id IS NOT NULL
        """
    )
    cr = _count(conn, "edges_country_region")

    conn.execute("DELETE FROM edges_region_farm")
    conn.execute(
        """
        INSERT INTO edges_region_farm (id, region_id, farm_id)
        SELECT 'rf:' || region_id || ':' || id, region_id, id
        FROM org_farms
        WHERE region_id IS NOT NULL
        """
    )
    rf = _count(conn, "edges_region_farm")

    return cr, rf


def populate_variety_flavor_edges(
    conn: duckdb.DuckDBPyConnection,
    top_k: int = VARIETY_FLAVOR_TOP_K,
    threshold: float = VARIETY_FLAVOR_THRESHOLD,
) -> int:
    """Top-K flavor matches per variety via embedding cosine similarity."""
    conn.execute("DELETE FROM edges_variety_flavor")
    conn.execute(
        """
        WITH sims AS (
            SELECT
                v.id AS variety_id,
                f.id AS flavor_id,
                array_cosine_similarity(v.name_embedding, f.name_embedding) AS sim
            FROM var_varieties v
            CROSS JOIN flav_attributes f
            WHERE v.name_embedding IS NOT NULL
              AND f.name_embedding IS NOT NULL
        ),
        ranked AS (
            SELECT
                variety_id, flavor_id, sim,
                ROW_NUMBER() OVER (PARTITION BY variety_id ORDER BY sim DESC) AS rn
            FROM sims
            WHERE sim >= ?
        )
        INSERT INTO edges_variety_flavor (id, variety_id, flavor_id, strength)
        SELECT 'vf:' || variety_id || ':' || flavor_id, variety_id, flavor_id, sim
        FROM ranked
        WHERE rn <= ?
        """,
        [threshold, top_k],
    )
    return _count(conn, "edges_variety_flavor")


CREATE_PROPERTY_GRAPH_SQL = """
CREATE PROPERTY GRAPH coffee_graph
  VERTEX TABLES (
    var_varieties,
    org_countries,
    org_regions,
    org_farms,
    flav_attributes,
    proc_methods
  )
  EDGE TABLES (
    edges_country_region
      SOURCE KEY (country_id) REFERENCES org_countries (id)
      DESTINATION KEY (region_id) REFERENCES org_regions (id),
    edges_region_farm
      SOURCE KEY (region_id) REFERENCES org_regions (id)
      DESTINATION KEY (farm_id) REFERENCES org_farms (id),
    edges_variety_flavor
      SOURCE KEY (variety_id) REFERENCES var_varieties (id)
      DESTINATION KEY (flavor_id) REFERENCES flav_attributes (id),
    edges_country_variety
      SOURCE KEY (country_id) REFERENCES org_countries (id)
      DESTINATION KEY (variety_id) REFERENCES var_varieties (id),
    edges_region_variety
      SOURCE KEY (region_id) REFERENCES org_regions (id)
      DESTINATION KEY (variety_id) REFERENCES var_varieties (id),
    edges_farm_variety
      SOURCE KEY (farm_id) REFERENCES org_farms (id)
      DESTINATION KEY (variety_id) REFERENCES var_varieties (id),
    edges_variety_processing
      SOURCE KEY (variety_id) REFERENCES var_varieties (id)
      DESTINATION KEY (method_id) REFERENCES proc_methods (id)
  )
"""


def create_property_graph(conn: duckdb.DuckDBPyConnection) -> bool:
    """Best-effort DuckPGQ property graph. Returns True if it succeeded.

    Re-runs are tolerated: if the graph already exists the CREATE fails and
    we report not-ok; the underlying edge tables (and thus the API) are
    unaffected.
    """
    try:
        conn.execute(CREATE_PROPERTY_GRAPH_SQL)
        return True
    except Exception:
        return False


def run_graph_stage(
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
    top_k: int = VARIETY_FLAVOR_TOP_K,
    threshold: float = VARIETY_FLAVOR_THRESHOLD,
) -> GraphCounts:
    """Populate all derivable edges. Pass `conn` for tests (in-memory DB)."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection() if db_path is None else duckdb.connect(db_path)

    try:
        cr, rf = populate_geo_edges(conn)
        vf = populate_variety_flavor_edges(conn, top_k=top_k, threshold=threshold)
        ok = create_property_graph(conn)
    finally:
        if owns_conn:
            conn.close()

    return GraphCounts(
        country_region=cr,
        region_farm=rf,
        variety_flavor=vf,
        property_graph_ok=ok,
    )


if __name__ == "__main__":
    counts = run_graph_stage()
    print(
        f"country->region: {counts.country_region}, "
        f"region->farm: {counts.region_farm}, "
        f"variety<->flavor: {counts.variety_flavor}, "
        f"property_graph: {'ok' if counts.property_graph_ok else 'skipped'}"
    )
