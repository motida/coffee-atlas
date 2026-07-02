"""Tests for backend.db.connection — extension loading behavior."""

from __future__ import annotations

from typing import cast

import duckdb
import pytest

import backend.db.connection as connection


class _StubConn:
    """Records executed SQL; raises on INSTALL when told to."""

    def __init__(self, fail_install: bool = False) -> None:
        self.fail_install = fail_install
        self.executed: list[str] = []

    def execute(self, sql: str):
        self.executed.append(sql)
        if self.fail_install and sql.startswith("INSTALL"):
            raise RuntimeError("no network")


def _load(conn: _StubConn) -> None:
    connection._load_extensions(cast("duckdb.DuckDBPyConnection", conn))


@pytest.fixture(autouse=True)
def _reset_install_state(monkeypatch):
    monkeypatch.setattr(connection, "_vss_installed", None)


def test_install_attempted_once_per_process():
    """INSTALL hits the extension repo, so it must not repeat on every
    request-scoped connection; LOAD is per-connection and local."""
    first, second = _StubConn(), _StubConn()
    _load(first)
    _load(second)
    assert "INSTALL vss" in first.executed
    assert "LOAD vss" in first.executed
    assert second.executed == ["LOAD vss"]


def test_failed_install_not_retried_and_nonfatal():
    first, second = _StubConn(fail_install=True), _StubConn()
    _load(first)  # must not raise
    _load(second)
    assert second.executed == []  # no LOAD without a successful INSTALL


def test_no_pgq_attempt():
    """duckpgq is parked (crashes on this DuckDB build) and 'pgq' was never
    its name — no variant should be attempted."""
    conn = _StubConn()
    _load(conn)
    assert not any("pgq" in sql.lower() for sql in conn.executed)
