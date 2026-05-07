"""Export ontology triples (asserted) to DuckDB.

Reads all .ttl files under ontology/ via rdflib, normalizes each triple to
(subject, predicate, object_value, object_kind, object_datatype, object_lang,
graph_iri) and writes them to the `ontology_triples` table.

`object_kind` is one of:
  - "iri"     — object is a URI reference
  - "literal" — object is a typed or plain literal
  - "bnode"   — object is a blank node

The export is idempotent: the table is wiped and re-populated on each run.

Reasoning is *not* run here. Only asserted triples are exported. The HermiT
reasoner integration (which would materialize inferred triples) is a
separate concern and would require working owlready2 + Java setup.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import duckdb
from rdflib import BNode, Graph, Literal, URIRef


@dataclass(frozen=True)
class TripleRow:
    subject: str
    predicate: str
    object_value: str
    object_kind: str  # "iri" | "literal" | "bnode"
    object_datatype: str | None
    object_lang: str | None
    graph_iri: str


def _ttl_files(root: Path) -> list[Path]:
    """All .ttl files under the ontology root, sorted for deterministic order."""
    return sorted(root.rglob("*.ttl"))


def _classify_object(o: object) -> tuple[str, str, str | None, str | None]:
    """Return (value, kind, datatype, lang) for an rdflib triple object."""
    if isinstance(o, URIRef):
        return str(o), "iri", None, None
    if isinstance(o, Literal):
        dt = str(o.datatype) if o.datatype else None
        return str(o), "literal", dt, o.language
    if isinstance(o, BNode):
        return str(o), "bnode", None, None
    raise TypeError(f"Unexpected RDF object type: {type(o).__name__}")


def parse_triples(ttl_files: Iterable[Path]) -> list[TripleRow]:
    """Parse every TTL file independently and emit normalized rows.

    Each file is parsed into its own rdflib Graph so that `graph_iri` reflects
    where the triple came from — useful for splitting T-Box modules later.
    """
    rows: list[TripleRow] = []
    for path in ttl_files:
        g = Graph()
        g.parse(path, format="turtle")
        graph_iri = path.as_uri()
        for s, p, o in g:
            if isinstance(s, BNode):
                s_str, s_kind = str(s), "bnode"
            else:
                s_str, s_kind = str(s), "iri"
            value, kind, dt, lang = _classify_object(o)
            rows.append(
                TripleRow(
                    subject=s_str,
                    predicate=str(p),
                    object_value=value,
                    object_kind=kind,
                    object_datatype=dt,
                    object_lang=lang,
                    graph_iri=graph_iri,
                )
            )
            del s_kind  # subject kind not currently persisted
    return rows


def write_triples(conn: duckdb.DuckDBPyConnection, rows: list[TripleRow]) -> int:
    """Idempotently replace ontology_triples with `rows`. Returns count."""
    conn.execute("DELETE FROM ontology_triples")
    if not rows:
        return 0
    payload = [
        (
            r.subject,
            r.predicate,
            r.object_value,
            r.object_kind,
            r.object_datatype,
            r.object_lang,
            r.graph_iri,
        )
        for r in rows
    ]
    conn.executemany(
        """
        INSERT INTO ontology_triples
            (subject, predicate, object_value, object_kind,
             object_datatype, object_lang, graph_iri)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    return len(rows)


def export(
    ontology_root: Path | None = None,
    db_path: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Parse all .ttl files and write triples to DuckDB. Returns row count."""
    if ontology_root is None:
        ontology_root = Path(__file__).resolve().parent.parent

    files = _ttl_files(ontology_root)
    if not files:
        raise FileNotFoundError(f"No .ttl files found under {ontology_root}")

    rows = parse_triples(files)

    owns_conn = conn is None
    if conn is None:
        from backend.db.connection import get_connection
        from backend.db.schema import create_tables

        conn = get_connection() if db_path is None else duckdb.connect(db_path)
        create_tables(conn)

    try:
        return write_triples(conn, rows)
    finally:
        if owns_conn:
            conn.close()


def main() -> None:
    ontology_root = Path(__file__).resolve().parent.parent
    files = _ttl_files(ontology_root)
    if not files:
        print(f"No .ttl files found under {ontology_root}")
        sys.exit(1)
    print(f"Parsing {len(files)} ontology file(s)...")
    n = export(ontology_root=ontology_root)
    print(f"Wrote {n} triples to ontology_triples")


if __name__ == "__main__":
    main()
