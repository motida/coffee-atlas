"""Authentication service: password hashing, JWTs, and the current-user deps.

Custom auth (no third-party provider): bcrypt password hashing, a signed JWT
delivered as an httpOnly cookie. ``get_current_user`` decodes the cookie and
loads the user row from Postgres, deliberately omitting ``password_hash`` from
the SELECT (the "never select sensitive columns" pattern from ``db/columns.py``).

Uses the ``bcrypt`` library directly rather than passlib: passlib 1.7.x is
effectively unmaintained and its bcrypt backend breaks against modern bcrypt
(>=4) releases.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, LiteralString

import bcrypt
import jwt
import psycopg
from fastapi import Cookie, Depends, HTTPException
from psycopg.rows import DictRow

from backend.config import settings
from backend.db.pg import get_pg

# FastAPI's Cookie(alias=...) needs a literal at definition time, so the cookie
# name is a module constant here; settings.COOKIE_NAME (same default) is used on
# the Set-Cookie side and shares this value.
CA_SESSION_COOKIE = "ca_session"

# Client-facing user columns — never includes password_hash.
_USER_COLS: LiteralString = "id, email, display_name, is_active, created_at, updated_at"

# bcrypt hashes at most the first 72 bytes of input; modern bcrypt raises rather
# than truncating, so we truncate explicitly (documented V1 limitation).
_BCRYPT_MAX_BYTES = 72


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(_pw_bytes(password), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    """Mint a signed JWT whose subject is the user id."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> str:
    """Return the ``sub`` (user id) from a valid token, or raise 401."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid session")
    return sub


def _load_active_user(pg: psycopg.Connection[DictRow], user_id: str) -> dict[str, Any] | None:
    """Load an active user row (sans password_hash), or None."""
    with pg.cursor() as cur:
        cur.execute(
            f"SELECT {_USER_COLS} FROM usr_users WHERE id = %s AND is_active = TRUE",
            [user_id],
        )
        return cur.fetchone()


def get_current_user(
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
    token: str | None = Cookie(default=None, alias=CA_SESSION_COOKIE),
) -> dict[str, Any]:
    """FastAPI dependency: the authenticated user row, or 401."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = _load_active_user(pg, _decode_token(token))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_user_optional(
    pg: psycopg.Connection[DictRow] = Depends(get_pg),
    token: str | None = Cookie(default=None, alias=CA_SESSION_COOKIE),
) -> dict[str, Any] | None:
    """Like ``get_current_user`` but returns None instead of raising 401."""
    if not token:
        return None
    try:
        user_id = _decode_token(token)
    except HTTPException:
        return None
    return _load_active_user(pg, user_id)
