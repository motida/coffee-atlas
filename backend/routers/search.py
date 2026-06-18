"""Cross-entity search.

Two endpoints:

- /text — case-insensitive LIKE over name + description columns. Cheap,
  works without API calls, covers all entity types.
- /semantic — embeds the query via Gemini, ranks by cosine similarity
  over each table's embedding column. Covers every entity type the
  embeddings stage populates; rows without embeddings are skipped.
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
    ("processing", "proc_methods", "name", "description"),
    ("shop", "shop_shops", "name", "description"),
    ("roast_profile", "roast_profiles", "name", "description"),
    ("product", "prod_products", "name", "description"),
]

# Per-entity-type extra WHERE fragment (no bind params). Shops are filtered to
# the specialty subset so search matches the rest of the app.
EXTRA_WHERE: dict[str, str] = {"shop": "is_specialty"}

# The embedding column each entity type ranks against. Types absent here
# (country, region) have no embeddings and so never take part in semantic search.
EMBEDDING_COLS: dict[str, str] = {
    "variety": "name_embedding",
    "flavor": "name_embedding",
    "processing": "description_embedding",
    "shop": "description_embedding",
    "roast_profile": "description_embedding",
    "product": "description_embedding",
}

# Semantic-search sources derive from TEXT_SOURCES — the same tuples plus the
# embedding column. Order is irrelevant; semantic results are re-sorted by
# similarity below.
SEMANTIC_SOURCES: list[tuple[str, str, str, str | None, str]] = [
    (*src, EMBEDDING_COLS[src[0]]) for src in TEXT_SOURCES if src[0] in EMBEDDING_COLS
]


def _per_source_limit(limit: int, n_sources: int) -> int:
    return max(5, (limit + n_sources - 1) // n_sources)


def _select_sources[S: tuple](
    sources: list[S], species: str | None, entity_types: list[str]
) -> list[S]:
    """Narrow a source list by the query filters.

    ``species`` is a variety-only attribute, so requesting one scopes the whole
    search to varieties, overriding any ``entity_types`` selection.
    """
    if species is not None:
        return [s for s in sources if s[0] == "variety"]
    if entity_types:
        wanted = set(entity_types)
        return [s for s in sources if s[0] in wanted]
    return sources


@router.get("/text", response_model=list[SearchResult])
def text_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    entity_types: list[str] = Query(default=[]),
    species: str | None = Query(None, description="Filter varieties by species (Arabica/Robusta)"),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[SearchResult]:
    sources = _select_sources(TEXT_SOURCES, species, entity_types)
    if not sources:
        return []

    pattern = f"%{query.lower()}%"
    per = _per_source_limit(limit, len(sources))
    rows: list[SearchResult] = []
    for entity_type, table, label_col, desc_col in sources:
        match_clauses = [f"LOWER({label_col}) LIKE ?"]
        params: list[Any] = [pattern]
        if desc_col is not None:
            match_clauses.append(f"LOWER(COALESCE({desc_col}, '')) LIKE ?")
            params.append(pattern)
        where = f"({' OR '.join(match_clauses)})"
        if species is not None:
            where += " AND LOWER(species) = LOWER(?)"
            params.append(species)
        if extra := EXTRA_WHERE.get(entity_type):
            where += f" AND {extra}"
        cols = f"id, {label_col}" + (f", {desc_col}" if desc_col else "")
        sql = (
            f"SELECT {cols} FROM {table} "
            f"WHERE {where} "
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
    species: str | None = Query(None, description="Filter varieties by species (Arabica/Robusta)"),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[SearchResult]:
    # Graceful degradation: the public demo runs without a Gemini key. Rather
    # than 502 on the flagship endpoint, fall back to text search transparently.
    if not settings.ENABLE_EMBEDDINGS or not settings.GEMINI_API_KEY:
        return text_search(
            query=query, limit=limit, entity_types=entity_types, species=species, db=db
        )

    sources = _select_sources(SEMANTIC_SOURCES, species, entity_types)
    if not sources:
        return []

    try:
        vector = EmbeddingService().embed(query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding service unavailable: {e}") from e

    rows: list[SearchResult] = []
    per = _per_source_limit(limit, len(sources))
    for entity_type, table, label_col, desc_col, embedding_col in sources:
        cols = f"id, {label_col}" + (f", {desc_col}" if desc_col else "")
        where = f"{embedding_col} IS NOT NULL"
        bind: list[Any] = [vector]
        if species is not None:
            where += " AND LOWER(species) = LOWER(?)"
            bind.append(species)
        if extra := EXTRA_WHERE.get(entity_type):
            where += f" AND {extra}"
        bind.append(per)
        sql = (
            f"SELECT {cols}, "
            f"array_cosine_similarity({embedding_col}, ?::FLOAT[3072]) AS sim "
            f"FROM {table} WHERE {where} "
            f"ORDER BY sim DESC LIMIT ?"
        )
        for row in db.execute(sql, bind).fetchall():
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
