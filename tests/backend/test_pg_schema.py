"""Tests for the Postgres user-data schema."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.db.pg_schema import create_pg_tables


def test_create_pg_tables_idempotent(pg) -> None:
    # Fixture already created the tables once; running again must not error.
    create_pg_tables(pg)
    create_pg_tables(pg)
    with pg.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'usr_%'"
        )
        names = {r["table_name"] for r in cur.fetchall()}
    assert {"usr_users", "usr_favorites", "usr_cupping_notes"} <= names


def test_email_case_insensitive_unique(pg) -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO usr_users (id, email, password_hash) VALUES (%s, %s, %s)",
            [str(uuid4()), "Person@Example.com", "x"],
        )
        pg.commit()
        with pytest.raises(Exception):  # UniqueViolation on LOWER(email)
            cur.execute(
                "INSERT INTO usr_users (id, email, password_hash) VALUES (%s, %s, %s)",
                [str(uuid4()), "person@example.com", "y"],
            )
        pg.rollback()


def test_favorite_unique_and_cascade(pg) -> None:
    user_id = str(uuid4())
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO usr_users (id, email, password_hash) VALUES (%s, %s, %s)",
            [user_id, "fav@example.com", "x"],
        )
        cur.execute(
            "INSERT INTO usr_favorites (id, user_id, entity_type, entity_id) "
            "VALUES (%s, %s, %s, %s)",
            [str(uuid4()), user_id, "variety", "v1"],
        )
        pg.commit()
        # Duplicate (user, type, id) rejected.
        with pytest.raises(Exception):
            cur.execute(
                "INSERT INTO usr_favorites (id, user_id, entity_type, entity_id) "
                "VALUES (%s, %s, %s, %s)",
                [str(uuid4()), user_id, "variety", "v1"],
            )
        pg.rollback()
        # Deleting the user cascades to favorites.
        cur.execute("DELETE FROM usr_users WHERE id = %s", [user_id])
        pg.commit()
        cur.execute("SELECT count(*) AS n FROM usr_favorites WHERE user_id = %s", [user_id])
        assert cur.fetchone()["n"] == 0
