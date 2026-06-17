"""Account activity routes: the signed-in user's favorites and cupping notes.

One router for both: favorites and notes aren't separate content domains, they
are two facets of one domain — the signed-in user's activity — sharing the same
``user_id``-scoped + DuckDB-validated axis. Every route depends on
``get_current_user``; every read and write is scoped ``WHERE user_id = %s``,
which is the core per-user isolation guarantee. Write routes additionally inject
the DuckDB connection to validate the referenced entity exists before writing.
"""

from typing import Any, LiteralString
from uuid import uuid4

import duckdb
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import sql
from psycopg.rows import DictRow

from backend.db.connection import get_db
from backend.db.pg import get_pg
from backend.models.activity import (
    CuppingNoteCreate,
    CuppingNoteRead,
    CuppingNoteUpdate,
    FavoriteCreate,
    FavoriteRead,
)
from backend.routers._activity_entities import (
    CUPPING_ENTITY_TABLES,
    FAVORITE_ENTITY_TABLES,
    resolve_entity_table,
)
from backend.routers._helpers import require_entity
from backend.services.auth import get_current_user

router = APIRouter(prefix="/api/v1/account", tags=["account"])

_FAV_COLS: LiteralString = "id, user_id, entity_type, entity_id, created_at"
_NOTE_COLS: LiteralString = (
    "id, user_id, entity_type, entity_id, score, notes, brew_method, created_at, updated_at"
)
# Columns a PATCH may set (whitelist — never the raw client payload keys).
_NOTE_UPDATABLE = {"notes", "score", "brew_method"}


# --- Favorites ---
@router.get("/favorites", response_model=list[FavoriteRead])
def list_favorites(
    entity_type: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> list[dict[str, Any]]:
    query: LiteralString = f"SELECT {_FAV_COLS} FROM usr_favorites WHERE user_id = %s"
    params: list[Any] = [user["id"]]
    if entity_type is not None:
        query += " AND entity_type = %s"
        params.append(entity_type)
    query += " ORDER BY created_at DESC"
    with pg.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.post("/favorites", response_model=FavoriteRead, status_code=201)
def add_favorite(
    body: FavoriteCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> dict[str, Any]:
    table = resolve_entity_table(FAVORITE_ENTITY_TABLES, body.entity_type)
    require_entity(db, table, body.entity_id, body.entity_type)
    with pg.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO usr_favorites (id, user_id, entity_type, entity_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, entity_type, entity_id) DO NOTHING
            RETURNING {_FAV_COLS}
            """,
            [str(uuid4()), user["id"], body.entity_type, body.entity_id],
        )
        row = cur.fetchone()
        if row is None:  # already favorited — return the existing row (idempotent)
            cur.execute(
                f"SELECT {_FAV_COLS} FROM usr_favorites "
                "WHERE user_id = %s AND entity_type = %s AND entity_id = %s",
                [user["id"], body.entity_type, body.entity_id],
            )
            row = cur.fetchone()
    assert row is not None  # either freshly inserted or the pre-existing row
    return row


@router.delete("/favorites/{favorite_id}", status_code=204)
def delete_favorite(
    favorite_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> None:
    with pg.cursor() as cur:
        cur.execute(
            "DELETE FROM usr_favorites WHERE id = %s AND user_id = %s RETURNING id",
            [favorite_id, user["id"]],
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Favorite not found")


# --- Cupping notes ---
@router.get("/notes", response_model=list[CuppingNoteRead])
def list_notes(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> list[dict[str, Any]]:
    query: LiteralString = f"SELECT {_NOTE_COLS} FROM usr_cupping_notes WHERE user_id = %s"
    params: list[Any] = [user["id"]]
    if entity_type is not None:
        query += " AND entity_type = %s"
        params.append(entity_type)
    if entity_id is not None:
        query += " AND entity_id = %s"
        params.append(entity_id)
    query += " ORDER BY created_at DESC"
    with pg.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.post("/notes", response_model=CuppingNoteRead, status_code=201)
def add_note(
    body: CuppingNoteCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> dict[str, Any]:
    table = resolve_entity_table(CUPPING_ENTITY_TABLES, body.entity_type)
    require_entity(db, table, body.entity_id, body.entity_type)
    with pg.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO usr_cupping_notes
                (id, user_id, entity_type, entity_id, score, notes, brew_method)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING {_NOTE_COLS}
            """,
            [
                str(uuid4()),
                user["id"],
                body.entity_type,
                body.entity_id,
                body.score,
                body.notes,
                body.brew_method,
            ],
        )
        row = cur.fetchone()
    assert row is not None  # INSERT ... RETURNING always yields the new row
    return row


@router.patch("/notes/{note_id}", response_model=CuppingNoteRead)
def update_note(
    note_id: str,
    body: CuppingNoteUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> dict[str, Any]:
    # Only whitelisted columns reach SQL, built as identifiers via psycopg.sql.
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _NOTE_UPDATABLE}
    with pg.cursor() as cur:
        if fields:
            assignments = sql.SQL(", ").join(
                sql.SQL("{} = %s").format(sql.Identifier(col)) for col in fields
            )
            query = sql.SQL(
                "UPDATE usr_cupping_notes SET {assignments}, updated_at = now() "
                "WHERE id = %s AND user_id = %s RETURNING {cols}"
            ).format(assignments=assignments, cols=sql.SQL(_NOTE_COLS))
            cur.execute(query, [*fields.values(), note_id, user["id"]])
        else:  # no-op PATCH: just return the current row (still ownership-scoped)
            cur.execute(
                f"SELECT {_NOTE_COLS} FROM usr_cupping_notes WHERE id = %s AND user_id = %s",
                [note_id, user["id"]],
            )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return row


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(
    note_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> None:
    with pg.cursor() as cur:
        cur.execute(
            "DELETE FROM usr_cupping_notes WHERE id = %s AND user_id = %s RETURNING id",
            [note_id, user["id"]],
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Note not found")
