"""Pure-logic tests for backend.services.auth (no database)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from backend.config import settings
from backend.services import auth


@pytest.fixture(autouse=True)
def _jwt_secret() -> None:
    settings.JWT_SECRET = "unit-test-secret-key-at-least-32-bytes-long!!"


def test_hash_and_verify_roundtrip() -> None:
    h = auth.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert auth.verify_password("correct horse battery staple", h)
    assert not auth.verify_password("wrong password", h)


def test_long_password_truncated_not_errored() -> None:
    # bcrypt caps at 72 bytes; we truncate rather than raise.
    base = "a" * 72
    h = auth.hash_password(base + "extra-ignored-bytes")
    assert auth.verify_password(base, h)


def test_token_roundtrip() -> None:
    token = auth.create_access_token("user-abc")
    assert auth._decode_token(token) == "user-abc"


def test_expired_token_rejected() -> None:
    past = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": "user-abc", "iat": past - timedelta(hours=1), "exp": past},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        auth._decode_token(token)
    assert exc.value.status_code == 401


def test_token_wrong_secret_rejected() -> None:
    token = jwt.encode(
        {"sub": "user-abc", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "a-different-secret-key-not-the-real-one-xx",
        algorithm=settings.JWT_ALGORITHM,
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        auth._decode_token(token)
