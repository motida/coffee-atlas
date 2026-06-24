"""Tests for the deploy-time DB compaction (prune non-specialty shops + rebuild)."""

import duckdb
import pytest

from backend.db.compact import compact_database


def _make_source(path):
    """A tiny content DB: 2 specialty + 3 non-specialty shops, a shop edge table
    (one edge points at a non-specialty shop), and an unrelated table."""
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE shop_shops (id TEXT PRIMARY KEY, name TEXT, is_specialty BOOLEAN)")
    con.execute(
        "INSERT INTO shop_shops VALUES "
        "('s1','A',true), ('s2','B',true), ('s3','C',false), ('s4','D',false), ('s5','E',NULL)"
    )
    con.execute(
        "CREATE TABLE edges_shop_product (id TEXT, shop_id TEXT REFERENCES shop_shops(id), product_id TEXT)"
    )
    # two edges to specialty shops, one to a non-specialty shop (should be dropped)
    con.execute(
        "INSERT INTO edges_shop_product VALUES ('e1','s1','p1'), ('e2','s2','p2'), ('e3','s3','p3')"
    )
    con.execute("CREATE TABLE var_varieties (id TEXT PRIMARY KEY, name TEXT)")
    con.execute("INSERT INTO var_varieties VALUES ('v1','Geisha'), ('v2','Bourbon')")
    con.close()


def test_prunes_non_specialty_and_keeps_rest(tmp_path):
    src = tmp_path / "src.duckdb"
    out = tmp_path / "out.duckdb"
    _make_source(src)

    stats = compact_database(str(src), str(out))

    assert stats.shops_before == 5
    assert stats.shops_after == 2
    assert out.exists()

    con = duckdb.connect(str(out), read_only=True)
    shops = con.execute("SELECT id FROM shop_shops ORDER BY id").fetchall()
    assert [r[0] for r in shops] == ["s1", "s2"]
    # edge to the non-specialty shop (s3) is gone; specialty edges remain
    edges = con.execute("SELECT id FROM edges_shop_product ORDER BY id").fetchall()
    assert [r[0] for r in edges] == ["e1", "e2"]
    # unrelated table round-trips unchanged
    assert con.execute("SELECT count(*) FROM var_varieties").fetchone() == (2,)
    con.close()


def test_overwrites_existing_out_file(tmp_path):
    src = tmp_path / "src.duckdb"
    out = tmp_path / "out.duckdb"
    _make_source(src)
    out.write_bytes(b"stale not-a-db bytes")  # simulate the previous deploy's DB

    stats = compact_database(str(src), str(out))

    assert stats.shops_after == 2
    con = duckdb.connect(str(out), read_only=True)
    assert con.execute("SELECT count(*) FROM shop_shops").fetchone() == (2,)
    con.close()


def test_raises_if_prune_would_empty_shops(tmp_path):
    src = tmp_path / "src.duckdb"
    out = tmp_path / "out.duckdb"
    con = duckdb.connect(str(src))
    con.execute("CREATE TABLE shop_shops (id TEXT PRIMARY KEY, name TEXT, is_specialty BOOLEAN)")
    con.execute("INSERT INTO shop_shops VALUES ('s1','A',false), ('s2','B',NULL)")
    con.close()

    with pytest.raises(RuntimeError, match="drop every shop"):
        compact_database(str(src), str(out))


def test_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        compact_database(str(tmp_path / "nope.duckdb"), str(tmp_path / "out.duckdb"))
