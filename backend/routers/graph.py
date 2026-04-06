from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import get_db
from backend.models.graph import TraversalResult, PathResult

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/traverse", response_model=TraversalResult)
def traverse_graph(
    start_id: str = Query(...),
    max_depth: int = Query(2, ge=1, le=5),
    edge_types: list[str] = Query(default=[]),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
):
    # TODO: Implement DuckPGQ graph traversal
    return TraversalResult(nodes=[], edges=[])


@router.get("/path", response_model=PathResult)
def find_path(
    start_id: str = Query(...),
    end_id: str = Query(...),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
):
    # TODO: Implement DuckPGQ shortest path
    return PathResult(path=[], edges=[])
