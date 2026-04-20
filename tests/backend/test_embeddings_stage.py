"""Tests for the embeddings ingest stage using a fake embedding service."""

from backend.ingest.embeddings_stage import TARGETS, run_embeddings
from backend.ingest.wcr_lexicon_loader import load_wcr_lexicon
from backend.services.embeddings import DIMENSIONS


class FakeEmbeddingService:
    """Returns deterministic vectors without hitting an API."""

    def __init__(self):
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
