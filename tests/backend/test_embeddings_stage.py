"""Tests for the embeddings ingest stage using a fake embedding service."""

from backend.ingest.embeddings_stage import TARGETS, run_embeddings
from backend.ingest.wcr_lexicon_loader import load_wcr_lexicon
from backend.services.embeddings import DIMENSIONS


class FakeEmbeddingService:
    """Returns deterministic vectors without hitting an API."""

    def __init__(self) -> None:
        self.call_count = 0

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        return [float(hash(text) % 1000) / 1000.0] * DIMENSIONS

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        return [self.embed(t) for t in texts]


def test_embeds_flavor_attributes(db):
    load_wcr_lexicon(conn=db)
    service = FakeEmbeddingService()
    results = run_embeddings(conn=db, service=service)
    assert results["flav_attributes"] == 110
    # Other tables are empty — should be 0
    for target in TARGETS:
        if target.table != "flav_attributes":
            assert results[target.table] == 0


def test_vector_dimensions(db):
    load_wcr_lexicon(conn=db)
    service = FakeEmbeddingService()
    run_embeddings(conn=db, service=service)
    row = db.execute(
        "SELECT name_embedding FROM flav_attributes WHERE name = 'Blackberry'"
    ).fetchone()
    assert row is not None
    assert len(row[0]) == DIMENSIONS


def test_skips_already_embedded(db):
    load_wcr_lexicon(conn=db)
    service = FakeEmbeddingService()
    run_embeddings(conn=db, service=service)
    assert service.call_count > 0

    # Second run should skip all rows
    service2 = FakeEmbeddingService()
    results = run_embeddings(conn=db, service=service2)
    assert results["flav_attributes"] == 0
    assert service2.call_count == 0


def test_idempotent_total_count(db):
    load_wcr_lexicon(conn=db)
    service = FakeEmbeddingService()
    run_embeddings(conn=db, service=service)
    run_embeddings(conn=db, service=service)
    count = db.execute(
        "SELECT COUNT(*) FROM flav_attributes WHERE name_embedding IS NOT NULL"
    ).fetchone()[0]
    assert count == 110


def test_empty_tables_produce_zero(db):
    """All tables exist but are empty — stage should succeed with 0 rows."""
    service = FakeEmbeddingService()
    results = run_embeddings(conn=db, service=service)
    assert all(v == 0 for v in results.values())


def test_embeds_fk_referenced_rows(db):
    """Rows referenced by edge tables must still be embeddable.

    DuckDB rewrites ARRAY-column updates as delete+insert, which violates
    foreign keys from edge tables; the stage works around it by snapshotting
    and restoring the referencing edges. Regression test for the roasting
    stage, whose loader creates roast→variety edges before embedding runs.
    """
    db.execute(
        "INSERT INTO var_varieties (id, name, description) VALUES ('v1', 'Geisha', 'floral')"
    )
    db.execute("INSERT INTO org_farms (id, name) VALUES ('f1', 'Konga')")
    db.execute(
        "INSERT INTO roast_profiles (id, name, description) VALUES ('p1', 'Nordic', 'light')"
    )
    db.execute("INSERT INTO edges_farm_variety (id, farm_id, variety_id) VALUES ('e1', 'f1', 'v1')")
    db.execute(
        "INSERT INTO edges_roast_variety (id, profile_id, variety_id) VALUES ('e2', 'p1', 'v1')"
    )

    results = run_embeddings(conn=db, service=FakeEmbeddingService())
    assert results["var_varieties"] == 1
    assert results["roast_profiles"] == 1

    # Embeddings written and the referencing edges restored intact.
    assert (
        db.execute(
            "SELECT COUNT(*) FROM var_varieties WHERE name_embedding IS NOT NULL"
        ).fetchone()[0]
        == 1
    )
    assert db.execute("SELECT COUNT(*) FROM edges_farm_variety").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM edges_roast_variety").fetchone()[0] == 1
