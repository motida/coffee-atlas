"""Tests for ontology/scripts/export_triples.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from ontology.scripts.export_triples import (
    _classify_object,
    export,
    parse_triples,
    write_triples,
)
from rdflib import BNode, Literal, URIRef


def _write_ttl(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_classify_object_handles_all_three_kinds():
    iri_value, kind, dt, lang = _classify_object(URIRef("http://example.org/x"))
    assert (iri_value, kind, dt, lang) == ("http://example.org/x", "iri", None, None)

    plain = Literal("hello")
    val, kind, dt, lang = _classify_object(plain)
    assert (val, kind, lang) == ("hello", "literal", None)

    typed = Literal(42)
    _, kind, dt, _ = _classify_object(typed)
    assert kind == "literal"
    assert dt is not None and dt.endswith("integer")

    tagged = Literal("bonjour", lang="fr")
    _, _, _, lang = _classify_object(tagged)
    assert lang == "fr"

    val, kind, _, _ = _classify_object(BNode("b1"))
    assert kind == "bnode"


def test_parse_triples_reads_module(tmp_path):
    ttl = _write_ttl(
        tmp_path / "tiny.ttl",
        """
        @prefix : <http://example.org/x#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

        :Foo a owl:Class ;
            rdfs:label "Foo" ;
            rdfs:comment "A class." .
        """,
    )
    rows = parse_triples([ttl])

    by_pred = {r.predicate.split("#")[-1] for r in rows}
    assert {"type", "label", "comment"}.issubset(by_pred)

    label = next(r for r in rows if r.predicate.endswith("#label"))
    assert label.object_kind == "literal"
    assert label.object_value == "Foo"

    type_row = next(r for r in rows if r.predicate.endswith("#type"))
    assert type_row.object_kind == "iri"
    assert type_row.object_value == "http://www.w3.org/2002/07/owl#Class"

    assert all(r.graph_iri == ttl.as_uri() for r in rows)


def test_write_triples_idempotent(db, tmp_path):
    ttl = _write_ttl(
        tmp_path / "tiny.ttl",
        """
        @prefix : <http://example.org/x#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        :A a owl:Class .
        :B a owl:Class .
        """,
    )
    rows = parse_triples([ttl])
    n1 = write_triples(db, rows)
    n2 = write_triples(db, rows)
    total = db.execute("SELECT COUNT(*) FROM ontology_triples").fetchone()[0]
    assert n1 == n2 == total


def test_export_against_real_ontology(db):
    root = Path(__file__).resolve().parents[2] / "ontology"
    n = export(ontology_root=root, conn=db)
    assert n > 0

    classes = db.execute(
        """
        SELECT COUNT(DISTINCT subject)
        FROM ontology_triples
        WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
          AND object_value = 'http://www.w3.org/2002/07/owl#Class'
        """
    ).fetchone()[0]
    assert classes >= 30


def test_export_missing_root_raises(tmp_path, db):
    with pytest.raises(FileNotFoundError):
        export(ontology_root=tmp_path, conn=db)
