"""Graph traversal and shortest-path endpoints over the edge tables.

The traversal does a BFS in Python, querying the edge tables directly
(rather than relying on DuckPGQ MATCH) so the API works regardless of
whether the property graph definition succeeded. /path searches
bidirectionally — one frontier from each endpoint, meeting in the middle —
so high-degree hub nodes don't blow the search budget.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db.connection import get_db
from backend.db.entities import CONTENT_ENTITY_TABLES
from backend.models.graph import GraphEdge, GraphNode, PathResult, TraversalResult

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

# Every content entity is a vertex in the knowledge graph.
VERTEX_TABLES = CONTENT_ENTITY_TABLES


@dataclass(frozen=True)
class EdgeDef:
    table: str
    edge_type: str
    src_type: str
    src_col: str
    dst_type: str
    dst_col: str


EDGES: list[EdgeDef] = [
    EdgeDef(
        table="edges_country_region",
        edge_type="country_region",
        src_type="country",
        src_col="country_id",
        dst_type="region",
        dst_col="region_id",
    ),
    EdgeDef(
        table="edges_region_farm",
        edge_type="region_farm",
        src_type="region",
        src_col="region_id",
        dst_type="farm",
        dst_col="farm_id",
    ),
    EdgeDef(
        table="edges_variety_flavor",
        edge_type="variety_flavor",
        src_type="variety",
        src_col="variety_id",
        dst_type="flavor",
        dst_col="flavor_id",
    ),
    # Origin -> variety edges (populated by the CQI loader). These bridge the
    # geographic hierarchy to the variety/flavor cluster, so the graph is a
    # single connected component rather than two islands.
    EdgeDef(
        table="edges_country_variety",
        edge_type="country_variety",
        src_type="country",
        src_col="country_id",
        dst_type="variety",
        dst_col="variety_id",
    ),
    EdgeDef(
        table="edges_region_variety",
        edge_type="region_variety",
        src_type="region",
        src_col="region_id",
        dst_type="variety",
        dst_col="variety_id",
    ),
    EdgeDef(
        table="edges_farm_variety",
        edge_type="farm_variety",
        src_type="farm",
        src_col="farm_id",
        dst_type="variety",
        dst_col="variety_id",
    ),
    EdgeDef(
        table="edges_variety_processing",
        edge_type="variety_processing",
        src_type="variety",
        src_col="variety_id",
        dst_type="processing",
        dst_col="method_id",
    ),
    # ProcessingMethod -> enhances/diminishes -> FlavorAttribute (curated seed,
    # populated by the processing_flavor stage).
    EdgeDef(
        table="edges_processing_flavor",
        edge_type="processing_flavor",
        src_type="processing",
        src_col="method_id",
        dst_type="flavor",
        dst_col="flavor_id",
    ),
    # RoastProfile -> suitableFor -> Variety (populated by the roasting loader
    # from each profile's suitable_for rule).
    EdgeDef(
        table="edges_roast_variety",
        edge_type="roast_variety",
        src_type="roast_profile",
        src_col="profile_id",
        dst_type="variety",
        dst_col="variety_id",
    ),
    # Products domain (populated by backend.ingest.product_edges). These bring
    # shops and roasters into the connected graph for the first time.
    EdgeDef(
        table="edges_product_variety",
        edge_type="product_variety",
        src_type="product",
        src_col="product_id",
        dst_type="variety",
        dst_col="variety_id",
    ),
    EdgeDef(
        table="edges_product_region",
        edge_type="product_region",
        src_type="product",
        src_col="product_id",
        dst_type="region",
        dst_col="region_id",
    ),
    EdgeDef(
        table="edges_product_country",
        edge_type="product_country",
        src_type="product",
        src_col="product_id",
        dst_type="country",
        dst_col="country_id",
    ),
    EdgeDef(
        table="edges_product_flavor",
        edge_type="product_flavor",
        src_type="product",
        src_col="product_id",
        dst_type="flavor",
        dst_col="flavor_id",
    ),
    EdgeDef(
        table="edges_product_roast",
        edge_type="product_roast",
        src_type="product",
        src_col="product_id",
        dst_type="roast_profile",
        dst_col="profile_id",
    ),
    EdgeDef(
        table="edges_roaster_product",
        edge_type="roaster_product",
        src_type="roaster",
        src_col="roaster_id",
        dst_type="product",
        dst_col="product_id",
    ),
    EdgeDef(
        table="edges_shop_roaster",
        edge_type="shop_roaster",
        src_type="shop",
        src_col="shop_id",
        dst_type="roaster",
        dst_col="roaster_id",
    ),
    EdgeDef(
        table="edges_shop_product",
        edge_type="shop_product",
        src_type="shop",
        src_col="shop_id",
        dst_type="product",
        dst_col="product_id",
    ),
    EdgeDef(
        table="edges_shop_variety",
        edge_type="shop_variety",
        src_type="shop",
        src_col="shop_id",
        dst_type="variety",
        dst_col="variety_id",
    ),
    # Provenance edges (populated by backend.ingest.product_edges): a farm
    # named in a product's text, and the derived shop -> farm sourcing chain.
    EdgeDef(
        table="edges_product_farm",
        edge_type="product_farm",
        src_type="product",
        src_col="product_id",
        dst_type="farm",
        dst_col="farm_id",
    ),
    EdgeDef(
        table="edges_shop_farm",
        edge_type="shop_farm",
        src_type="shop",
        src_col="shop_id",
        dst_type="farm",
        dst_col="farm_id",
    ),
]

# Server-side work budget. Depth alone doesn't bound cost: the shop/product
# edge tables fan a depth-5 sweep from a well-connected country out to ~7k
# nodes / 122k edges (~20 MB JSON, ~40k sequential queries) on this public,
# unauthenticated endpoint. The UI requests depth 1-2; these caps keep any
# single request bounded while leaving normal traversals untouched.
MAX_TRAVERSE_NODES = 1000
MAX_TRAVERSE_EDGES = 5000
MAX_PATH_VISITED = 20_000


def _lookup_node(conn: duckdb.DuckDBPyConnection, node_id: str) -> GraphNode | None:
    """Find which vertex table owns this id; return a GraphNode or None."""
    for entity_type, table in VERTEX_TABLES.items():
        row = conn.execute(f"SELECT id, name FROM {table} WHERE id = ?", [node_id]).fetchone()
        if row:
            return GraphNode(id=row[0], entity_type=entity_type, label=row[1])
    return None


def _neighbors(
    conn: duckdb.DuckDBPyConnection,
    node_id: str,
    entity_type: str,
    edge_types: set[str] | None,
) -> list[tuple[GraphNode, GraphEdge]]:
    """All edges incident on (node_id, entity_type), treated as undirected."""
    out: list[tuple[GraphNode, GraphEdge]] = []
    for edef in EDGES:
        if edge_types is not None and edef.edge_type not in edge_types:
            continue

        if edef.src_type == entity_type:
            dst_table = VERTEX_TABLES[edef.dst_type]
            rows = conn.execute(
                f"""
                SELECT v.id, v.name
                FROM {edef.table} e
                JOIN {dst_table} v ON e.{edef.dst_col} = v.id
                WHERE e.{edef.src_col} = ?
                """,
                [node_id],
            ).fetchall()
            for vid, vname in rows:
                neighbor = GraphNode(id=vid, entity_type=edef.dst_type, label=vname)
                edge = GraphEdge(
                    source_id=node_id,
                    target_id=vid,
                    edge_type=edef.edge_type,
                )
                out.append((neighbor, edge))

        if edef.dst_type == entity_type:
            src_table = VERTEX_TABLES[edef.src_type]
            rows = conn.execute(
                f"""
                SELECT v.id, v.name
                FROM {edef.table} e
                JOIN {src_table} v ON e.{edef.src_col} = v.id
                WHERE e.{edef.dst_col} = ?
                """,
                [node_id],
            ).fetchall()
            for vid, vname in rows:
                neighbor = GraphNode(id=vid, entity_type=edef.src_type, label=vname)
                edge = GraphEdge(
                    source_id=vid,
                    target_id=node_id,
                    edge_type=edef.edge_type,
                )
                out.append((neighbor, edge))

    return out


@router.get("/traverse", response_model=TraversalResult)
def traverse_graph(
    start_id: str = Query(..., description="Vertex id to start from"),
    max_depth: int = Query(2, ge=1, le=5),
    edge_types: list[str] = Query(default=[]),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> TraversalResult:
    start = _lookup_node(db, start_id)
    if start is None:
        raise HTTPException(status_code=404, detail="start_id not found")

    filter_set = set(edge_types) if edge_types else None
    visited: dict[str, GraphNode] = {start.id: start}
    seen_edges: set[tuple[str, str, str]] = set()
    edges_out: list[GraphEdge] = []
    frontier: deque[tuple[GraphNode, int]] = deque([(start, 0)])

    truncated = False
    while frontier and not truncated:
        current, depth = frontier.popleft()
        if depth >= max_depth:
            continue
        for neighbor, edge in _neighbors(db, current.id, current.entity_type, filter_set):
            if len(visited) >= MAX_TRAVERSE_NODES or len(edges_out) >= MAX_TRAVERSE_EDGES:
                truncated = True
                break
            edge_key = (edge.source_id, edge.target_id, edge.edge_type)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges_out.append(edge)
            if neighbor.id not in visited:
                visited[neighbor.id] = neighbor
                frontier.append((neighbor, depth + 1))

    return TraversalResult(nodes=list(visited.values()), edges=edges_out, truncated=truncated)


@dataclass
class _SearchSide:
    """One frontier of the bidirectional path search."""

    visited: dict[str, GraphNode]
    depth_of: dict[str, int]
    parents: dict[str, tuple[str, GraphEdge]]
    frontier: list[GraphNode]
    depth: int = 0


def _expand_level(
    conn: duckdb.DuckDBPyConnection,
    side: _SearchSide,
    other: _SearchSide,
    edge_types: set[str] | None,
) -> tuple[str | None, bool]:
    """Advance `side` one full BFS level; returns (meeting node id, truncated).

    The whole level is expanded before committing to a meeting node so that,
    among the meets this level produced, the one closest to the other side
    wins — keeping the joined path shortest.
    """
    next_frontier: list[GraphNode] = []
    best_meet: str | None = None
    for node in side.frontier:
        for neighbor, edge in _neighbors(conn, node.id, node.entity_type, edge_types):
            if neighbor.id in side.visited:
                continue
            if len(side.visited) + len(other.visited) >= MAX_PATH_VISITED:
                return best_meet, True
            side.visited[neighbor.id] = neighbor
            side.depth_of[neighbor.id] = side.depth + 1
            side.parents[neighbor.id] = (node.id, edge)
            if neighbor.id in other.visited and (
                best_meet is None or other.depth_of[neighbor.id] < other.depth_of[best_meet]
            ):
                best_meet = neighbor.id
            next_frontier.append(neighbor)
    side.frontier = next_frontier
    side.depth += 1
    return best_meet, False


@router.get("/path", response_model=PathResult)
def find_path(
    start_id: str = Query(...),
    end_id: str = Query(...),
    max_depth: int = Query(6, ge=1, le=10),
    edge_types: list[str] = Query(default=[]),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> PathResult:
    """Shortest path via bidirectional BFS.

    Growing a frontier from each endpoint and meeting in the middle keeps the
    search out of the super-hub explosion (country and flavor nodes fan out to
    thousands of neighbors at depth 3+) that used to exhaust MAX_PATH_VISITED
    on pairs that are actually connected. `edge_types` restricts which edge
    tables the path may use — e.g. only supply-chain edges for a farm→shop
    provenance trace.
    """
    start = _lookup_node(db, start_id)
    if start is None:
        raise HTTPException(status_code=404, detail="start_id not found")
    end = _lookup_node(db, end_id)
    if end is None:
        raise HTTPException(status_code=404, detail="end_id not found")

    if start_id == end_id:
        return PathResult(path=[start], edges=[], total_weight=0)

    filter_set = set(edge_types) if edge_types else None
    fwd = _SearchSide(
        visited={start.id: start}, depth_of={start.id: 0}, parents={}, frontier=[start]
    )
    bwd = _SearchSide(visited={end.id: end}, depth_of={end.id: 0}, parents={}, frontier=[end])

    truncated = False
    while fwd.frontier and bwd.frontier and fwd.depth + bwd.depth < max_depth:
        # Expanding the smaller frontier keeps the visited sets balanced and
        # the total work near the geometric minimum.
        side, other = (fwd, bwd) if len(fwd.frontier) <= len(bwd.frontier) else (bwd, fwd)
        meet, truncated = _expand_level(db, side, other, filter_set)
        if meet is not None:
            return _join_paths(start_id, end_id, meet, fwd, bwd)
        if truncated:
            break

    detail = "no path found within the search budget" if truncated else "no path found"
    raise HTTPException(status_code=404, detail=detail)


def _join_paths(
    start_id: str,
    end_id: str,
    meet_id: str,
    fwd: _SearchSide,
    bwd: _SearchSide,
) -> PathResult:
    """Stitch the two half-paths together at the meeting node."""
    path_ids = [meet_id]
    edges: list[GraphEdge] = []
    while path_ids[-1] != start_id:
        prev_id, edge = fwd.parents[path_ids[-1]]
        edges.append(edge)
        path_ids.append(prev_id)
    path_ids.reverse()
    edges.reverse()

    cur = meet_id
    while cur != end_id:
        prev_id, edge = bwd.parents[cur]
        edges.append(edge)
        path_ids.append(prev_id)
        cur = prev_id

    nodes = {**bwd.visited, **fwd.visited}
    return PathResult(
        path=[nodes[nid] for nid in path_ids],
        edges=edges,
        total_weight=float(len(edges)),
    )
