"""Tests for the deploy-time DB compaction (prune non-specialty shops + rebuild).

The compacted artifact must keep its PK/FK constraints: the API container runs
``create_tables`` (CREATE TABLE IF NOT EXISTS) against the shipped DB on startup,
which fails if a referenced table has lost its primary key. So the source DB here
is built with the real schema, and the regression guard re-runs ``create_tables``
against the output.
"""

import duckdb
import pytest

from backend.db.compact import compact_database
from backend.db.schema import create_tables


def _seed_source(path, specialty=("true", "true", "false")):
    """Build a source DB on the real schema: one variety, N shops with the given
    is_specialty values, and one shop->variety edge per shop."""
    con = duckdb.connect(str(path))
    create_tables(con)
    con.execute("INSERT INTO var_varieties (id, name) VALUES ('v1', 'Geisha')")
    shops = ", ".join(f"('s{i}', 'Shop {i}', {v})" for i, v in enumerate(specialty, 1))
    edges = ", ".join(f"('e{i}', 's{i}', 'v1')" for i, _ in enumerate(specialty, 1))
    con.execute(f"INSERT INTO shop_shops (id, name, is_specialty) VALUES {shops}")
    con.execute(f"INSERT INTO edges_shop_variety (id, shop_id, variety_id) VALUES {edges}")
    con.close()


def test_prunes_non_specialty_and_keeps_rest(tmp_path):
    src, out = tmp_path / "src.duckdb", tmp_path / "out.duckdb"
    _seed_source(src, specialty=("true", "true", "false"))

    stats = compact_database(str(src), str(out))

    assert stats.shops_before == 3
    assert stats.shops_after == 2
    con = duckdb.connect(str(out), read_only=True)
    assert [r[0] for r in con.execute("SELECT id FROM shop_shops ORDER BY id").fetchall()] == [
        "s1",
        "s2",
    ]
    # the edge to the non-specialty shop (s3) is dropped; specialty edges remain
    assert [
        r[0] for r in con.execute("SELECT id FROM edges_shop_variety ORDER BY id").fetchall()
    ] == ["e1", "e2"]
    # an unrelated table round-trips unchanged
    assert con.execute("SELECT count(*) FROM var_varieties").fetchone() == (1,)
    con.close()


def test_output_survives_create_tables(tmp_path):
    """Regression guard: the shipped DB must pass the bootstrap startup step."""
    src, out = tmp_path / "src.duckdb", tmp_path / "out.duckdb"
    _seed_source(src)
    compact_database(str(src), str(out))

    con = duckdb.connect(str(out))
    create_tables(con)  # exactly what the container runs on startup; must not raise
    pks = con.execute(
        "SELECT count(*) FROM duckdb_constraints() "
        "WHERE table_name='shop_shops' AND constraint_type='PRIMARY KEY'"
    ).fetchone()
    assert pks == (1,)  # the PK on a referenced table survived compaction
    con.close()


def test_overwrites_existing_out_file(tmp_path):
    src, out = tmp_path / "src.duckdb", tmp_path / "out.duckdb"
    _seed_source(src)
    out.write_bytes(b"stale not-a-db bytes")  # simulate the previous deploy's DB

    stats = compact_database(str(src), str(out))

    assert stats.shops_after == 2
    con = duckdb.connect(str(out), read_only=True)
    assert con.execute("SELECT count(*) FROM shop_shops").fetchone() == (2,)
    con.close()


def test_raises_if_prune_would_empty_shops(tmp_path):
    src, out = tmp_path / "src.duckdb", tmp_path / "out.duckdb"
    _seed_source(src, specialty=("false", "NULL"))

    with pytest.raises(RuntimeError, match="drop every shop"):
        compact_database(str(src), str(out))


def test_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        compact_database(str(tmp_path / "nope.duckdb"), str(tmp_path / "out.duckdb"))
