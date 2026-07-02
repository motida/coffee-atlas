"""Authentication routes: register, login, logout, current user."""

from typing import Any, LiteralString
from uuid import uuid4

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from psycopg.rows import DictRow

from backend.config import settings
from backend.db.pg import get_pg
from backend.models.users import LoginRequest, UserCreate, UserRead
from backend.services.auth import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Public user columns (mirrors services.auth._USER_COLS) — never password_hash.
_USER_COLS: LiteralString = "id, email, display_name, is_active, created_at, updated_at"


def _set_session_cookie(response: Response, user_id: str) -> None:
    """Attach the signed-JWT session cookie to the response."""
    response.set_cookie(
        settings.COOKIE_NAME,
        create_access_token(user_id),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=201)
def register(
    body: UserCreate,
    response: Response,
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> dict[str, Any]:
    user_id = str(uuid4())
    try:
        with pg.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO usr_users (id, email, password_hash, display_name)
                VALUES (%s, %s, %s, %s)
                RETURNING {_USER_COLS}
                """,
                [user_id, body.email, hash_password(body.password), body.display_name],
            )
            user = cur.fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already registered")
    assert user is not None  # INSERT ... RETURNING always yields the new row
    _set_session_cookie(response, user["id"])
    return user


@router.post("/login", response_model=UserRead)
def login(
    body: LoginRequest,
    response: Response,
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
) -> dict[str, Any]:
    with pg.cursor() as cur:
        cur.execute(
            f"SELECT {_USER_COLS}, password_hash FROM usr_users "
            "WHERE LOWER(email) = LOWER(%s) AND is_active = TRUE",
            [body.email],
        )
        row = cur.fetchone()
    # Verify against a dummy hash when the email is unknown, so bcrypt runs on
    # both paths and response latency doesn't enumerate registered addresses.
    password_ok = verify_password(
        body.password, row["password_hash"] if row else DUMMY_PASSWORD_HASH
    )
    if row is None or not password_ok:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _set_session_cookie(response, row["id"])
    return row


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(settings.COOKIE_NAME, path="/")


@router.get("/me", response_model=UserRead)
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return user
