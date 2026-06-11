"""Graph traversal and shortest-path endpoints over the edge tables.

The traversal does a BFS in Python, querying the edge tables directly
(rather than relying on DuckPGQ MATCH) so the API works regardless of
whether the property graph definition succeeded.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db.connection import get_db
from backend.models.graph import GraphEdge, GraphNode, PathResult, TraversalResult

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

VERTEX_TABLES: dict[str, str] = {
    "variety": "var_varieties",
    "country": "org_countries",
    "region": "org_regions",
    "farm": "org_farms",
    "flavor": "flav_attributes",
    "processing": "proc_methods",
    "roast_profile": "roast_profiles",
}


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
]


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

    while frontier:
        current, depth = frontier.popleft()
        if depth >= max_depth:
            continue
        for neighbor, edge in _neighbors(db, current.id, current.entity_type, filter_set):
            edge_key = (edge.source_id, edge.target_id, edge.edge_type)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges_out.append(edge)
            if neighbor.id not in visited:
                visited[neighbor.id] = neighbor
                frontier.append((neighbor, depth + 1))

    return TraversalResult(nodes=list(visited.values()), edges=edges_out)


@router.get("/path", response_model=PathResult)
def find_path(
    start_id: str = Query(...),
    end_id: str = Query(...),
    max_depth: int = Query(6, ge=1, le=10),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> PathResult:
    start = _lookup_node(db, start_id)
    if start is None:
        raise HTTPException(status_code=404, detail="start_id not found")
    end = _lookup_node(db, end_id)
    if end is None:
        raise HTTPException(status_code=404, detail="end_id not found")

    if start_id == end_id:
        return PathResult(path=[start], edges=[], total_weight=0)

    parents: dict[str, tuple[str, GraphEdge]] = {}
    nodes_seen: dict[str, GraphNode] = {start.id: start}
    frontier: deque[tuple[GraphNode, int]] = deque([(start, 0)])

    while frontier:
        current, depth = frontier.popleft()
        if depth >= max_depth:
            continue
        for neighbor, edge in _neighbors(db, current.id, current.entity_type, None):
            if neighbor.id in nodes_seen:
                continue
            nodes_seen[neighbor.id] = neighbor
            parents[neighbor.id] = (current.id, edge)
            if neighbor.id == end_id:
                return _reconstruct_path(start_id, end_id, parents, nodes_seen)
            frontier.append((neighbor, depth + 1))

    raise HTTPException(status_code=404, detail="no path found")


def _reconstruct_path(
    start_id: str,
    end_id: str,
    parents: dict[str, tuple[str, GraphEdge]],
    nodes_seen: dict[str, GraphNode],
) -> PathResult:
    path_ids = [end_id]
    edges: list[GraphEdge] = []
    while path_ids[-1] != start_id:
        prev_id, edge = parents[path_ids[-1]]
        edges.append(edge)
        path_ids.append(prev_id)
    path_ids.reverse()
    edges.reverse()
    return PathResult(
        path=[nodes_seen[nid] for nid in path_ids],
        edges=edges,
        total_weight=float(len(edges)),
    )
