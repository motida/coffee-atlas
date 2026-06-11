"""Cross-entity search.

Two endpoints:

- /text — case-insensitive LIKE over name + description columns. Cheap,
  works without API calls, covers all entity types.
- /semantic — embeds the query via Gemini, ranks by cosine similarity
  over the `name_embedding` columns. Limited to entity types that have
  embeddings populated (varieties, flavor attributes).
"""

from __future__ import annotations

from typing import Any

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.config import settings
from backend.db.connection import get_db
from backend.models.search import SearchResult
from backend.services.embeddings import EmbeddingService

router = APIRouter(prefix="/api/v1/search", tags=["search"])


# Text-search sources: (entity_type, table, label_col, desc_col_or_null)
TEXT_SOURCES: list[tuple[str, str, str, str | None]] = [
    ("variety", "var_varieties", "name", "description"),
    ("flavor", "flav_attributes", "name", "description"),
    ("country", "org_countries", "name", None),
    ("region", "org_regions", "name", None),
    ("shop", "shop_shops", "name", "description"),
    ("roast_profile", "roast_profiles", "name", "description"),
]

# Semantic-search sources: only tables that have name_embedding populated.
SEMANTIC_SOURCES: list[tuple[str, str, str, str | None]] = [
    ("variety", "var_varieties", "name", "description"),
    ("flavor", "flav_attributes", "name", "description"),
]


def _per_source_limit(limit: int, n_sources: int) -> int:
    return max(5, (limit + n_sources - 1) // n_sources)


@router.get("/text", response_model=list[SearchResult])
def text_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    entity_types: list[str] = Query(default=[]),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[SearchResult]:
    sources = TEXT_SOURCES
    if entity_types:
        wanted = set(entity_types)
        sources = [s for s in sources if s[0] in wanted]
    if not sources:
        return []

    pattern = f"%{query.lower()}%"
    per = _per_source_limit(limit, len(sources))
    rows: list[SearchResult] = []
    for entity_type, table, label_col, desc_col in sources:
        where = [f"LOWER({label_col}) LIKE ?"]
        params: list[Any] = [pattern]
        if desc_col is not None:
            where.append(f"LOWER(COALESCE({desc_col}, '')) LIKE ?")
            params.append(pattern)
        cols = f"id, {label_col}" + (f", {desc_col}" if desc_col else "")
        sql = (
            f"SELECT {cols} FROM {table} "
            f"WHERE {' OR '.join(where)} "
            f"ORDER BY length({label_col}) ASC "  # exact-ish matches first
            f"LIMIT ?"
        )
        params.append(per)
        for row in db.execute(sql, params).fetchall():
            rows.append(
                SearchResult(
                    id=row[0],
                    entity_type=entity_type,
                    label=row[1],
                    description=row[2] if desc_col else None,
                    similarity=None,
                )
            )
    return rows[:limit]


@router.get("/semantic", response_model=list[SearchResult])
def semantic_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    entity_types: list[str] = Query(default=[]),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[SearchResult]:
    # Graceful degradation: the public demo runs without a Gemini key. Rather
    # than 502 on the flagship endpoint, fall back to text search transparently.
    if not settings.ENABLE_EMBEDDINGS or not settings.GEMINI_API_KEY:
        return text_search(query=query, limit=limit, entity_types=entity_types, db=db)

    sources = SEMANTIC_SOURCES
    if entity_types:
        wanted = set(entity_types)
        sources = [s for s in sources if s[0] in wanted]
    if not sources:
        return []

    try:
        vector = EmbeddingService().embed(query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding service unavailable: {e}") from e

    rows: list[SearchResult] = []
    per = _per_source_limit(limit, len(sources))
    for entity_type, table, label_col, desc_col in sources:
        cols = f"id, {label_col}" + (f", {desc_col}" if desc_col else "")
        sql = (
            f"SELECT {cols}, "
            f"array_cosine_similarity(name_embedding, ?::FLOAT[3072]) AS sim "
            f"FROM {table} WHERE name_embedding IS NOT NULL "
            f"ORDER BY sim DESC LIMIT ?"
        )
        for row in db.execute(sql, [vector, per]).fetchall():
            rows.append(
                SearchResult(
                    id=row[0],
                    entity_type=entity_type,
                    label=row[1],
                    description=row[2] if desc_col else None,
                    similarity=row[-1],
                )
            )
    rows.sort(key=lambda r: r.similarity or 0, reverse=True)
    return rows[:limit]
