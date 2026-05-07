"""Tests for the graph stage — edge population from FKs and embeddings."""

from __future__ import annotations

from backend.ingest.graph_stage import (
    populate_geo_edges,
    populate_variety_flavor_edges,
    run_graph_stage,
)

EMBED_DIM = 3072


def _vec(idx: int) -> list[float]:
    """Unit vector with 1.0 at position idx % EMBED_DIM, 0 elsewhere."""
    v = [0.0] * EMBED_DIM
    v[idx % EMBED_DIM] = 1.0
    return v


def _seed_geo(db) -> None:
    db.execute("INSERT INTO org_countries (id, name) VALUES ('c1', 'Ethiopia')")
    db.execute("INSERT INTO org_countries (id, name) VALUES ('c2', 'Kenya')")
    db.execute(
        "INSERT INTO org_regions (id, name, country_id) VALUES "
        "('r1', 'Yirgacheffe', 'c1'), ('r2', 'Sidamo', 'c1'), ('r3', 'Nyeri', 'c2')"
    )
    # One farm with NULL region — should be skipped from edges_region_farm.
    db.execute(
        "INSERT INTO org_farms (id, name, region_id) VALUES "
        "('f1', 'Konga', 'r1'), ('f2', 'Idido', 'r1'), ('f3', 'Tegu', 'r3'), "
        "('f-orphan', 'No Region', NULL)"
    )


def test_geo_edges_built_from_fks(db):
    _seed_geo(db)
    cr, rf = populate_geo_edges(db)
    assert cr == 3  # r1, r2, r3 all have country
    assert rf == 3  # f1, f2, f3; f-orphan skipped

    rows = db.execute(
        "SELECT country_id, region_id FROM edges_country_region ORDER BY country_id, region_id"
    ).fetchall()
    assert rows == [("c1", "r1"), ("c1", "r2"), ("c2", "r3")]

    rows = db.execute(
        "SELECT region_id, farm_id FROM edges_region_farm ORDER BY region_id, farm_id"
    ).fetchall()
    assert rows == [("r1", "f1"), ("r1", "f2"), ("r3", "f3")]


def test_geo_edges_idempotent(db):
    _seed_geo(db)
    populate_geo_edges(db)
    populate_geo_edges(db)  # second pass should not duplicate
    cr_count = db.execute("SELECT COUNT(*) FROM edges_country_region").fetchone()[0]
    rf_count = db.execute("SELECT COUNT(*) FROM edges_region_farm").fetchone()[0]
    assert cr_count == 3
    assert rf_count == 3


def _vec_two(i: int, j: int) -> list[float]:
    """Vector with 1.0 at positions i and j; cosine sim with _vec(i) is 1/sqrt(2)."""
    v = [0.0] * EMBED_DIM
    v[i % EMBED_DIM] = 1.0
    v[j % EMBED_DIM] = 1.0
    return v


def test_variety_flavor_top_k_limits_results(db):
    # f-high sim=1.0; f-mid sim=1/sqrt(2)≈0.707; f-zero sim=0.0
    db.execute(
        "INSERT INTO flav_attributes (id, name, name_embedding) VALUES "
        "(?, 'High', ?), (?, 'Mid', ?), (?, 'Zero', ?)",
        ["f-high", _vec(0), "f-mid", _vec_two(0, 1), "f-zero", _vec(100)],
    )
    db.execute(
        "INSERT INTO var_varieties (id, name, name_embedding) VALUES (?, 'V1', ?)",
        ["v1", _vec(0)],
    )

    # threshold below all positives, top_k=2 → keep two highest only.
    n = populate_variety_flavor_edges(db, top_k=2, threshold=0.0)
    assert n == 2
    picked = db.execute(
        "SELECT flavor_id FROM edges_variety_flavor ORDER BY strength DESC"
    ).fetchall()
    assert [r[0] for r in picked] == ["f-high", "f-mid"]


def test_variety_flavor_threshold_filters(db):
    db.execute(
        "INSERT INTO flav_attributes (id, name, name_embedding) VALUES "
        "(?, 'High', ?), (?, 'Mid', ?)",
        ["f-high", _vec(0), "f-mid", _vec_two(0, 1)],
    )
    db.execute(
        "INSERT INTO var_varieties (id, name, name_embedding) VALUES (?, 'V1', ?)",
        ["v1", _vec(0)],
    )

    # f-mid sim ≈ 0.707; threshold 0.9 excludes it.
    n = populate_variety_flavor_edges(db, top_k=10, threshold=0.9)
    assert n == 1
    picked = db.execute("SELECT flavor_id FROM edges_variety_flavor").fetchone()
    assert picked == ("f-high",)


def test_variety_flavor_skips_null_embeddings(db):
    db.execute(
        "INSERT INTO flav_attributes (id, name, name_embedding) VALUES "
        "(?, 'Match', ?), (?, 'NoEmbed', NULL)",
        ["f-match", _vec(0), "f-null"],
    )
    db.execute(
        "INSERT INTO var_varieties (id, name, name_embedding) VALUES "
        "(?, 'V1', ?), (?, 'V-null', NULL)",
        ["v1", _vec(0), "v-null"],
    )
    n = populate_variety_flavor_edges(db, top_k=5, threshold=0.0)
    assert n == 1  # only the v1 / f-match pair qualifies


def test_variety_flavor_idempotent(db):
    db.execute(
        "INSERT INTO flav_attributes (id, name, name_embedding) VALUES (?, 'F', ?)",
        ["f1", _vec(0)],
    )
    db.execute(
        "INSERT INTO var_varieties (id, name, name_embedding) VALUES (?, 'V', ?)",
        ["v1", _vec(0)],
    )
    populate_variety_flavor_edges(db, top_k=5, threshold=0.0)
    populate_variety_flavor_edges(db, top_k=5, threshold=0.0)
    count = db.execute("SELECT COUNT(*) FROM edges_variety_flavor").fetchone()[0]
    assert count == 1


def test_run_graph_stage_orchestrates_all(db):
    _seed_geo(db)
    db.execute(
        "INSERT INTO flav_attributes (id, name, name_embedding) VALUES (?, 'F', ?)",
        ["f1", _vec(0)],
    )
    db.execute(
        "INSERT INTO var_varieties (id, name, name_embedding) VALUES (?, 'V', ?)",
        ["v1", _vec(0)],
    )
    counts = run_graph_stage(conn=db, top_k=5, threshold=0.0)
    assert counts.country_region == 3
    assert counts.region_farm == 3
    assert counts.variety_flavor == 1
    # property_graph_ok depends on DuckPGQ availability — don't assert.
