from fastapi import APIRouter, Depends, Query
import duckdb

from backend.db.connection import get_db
from backend.models.search import SearchResult

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/semantic", response_model=list[SearchResult])
def semantic_search(
    query: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
):
    # TODO: Generate embedding for query, run VSS similarity search
    return []


@router.get("/text", response_model=list[SearchResult])
def text_search(
    query: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
):
    # TODO: Implement full-text search across entity tables
    return []
