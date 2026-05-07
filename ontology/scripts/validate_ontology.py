"""Validate the Coffee Atlas ontology.

Today this is a *structural* validator: it parses every .ttl module via
rdflib, merges them into a single graph, and reports class / property /
individual counts. Syntax errors fail loudly.

Full OWL 2 DL consistency checking with HermiT (per the spec in CLAUDE.md)
is parked: owlready2 cannot natively parse Turtle on the current install,
and HermiT requires a working Java toolchain. The fix is non-trivial — see
memory/project_ontology_tooling_state.md.

The structural check still catches the cases that bite in practice:
malformed turtle, missing prefixes, unparsable IRIs.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import OWL, RDF, Graph, URIRef
from rdflib.namespace import RDFS

ONTOLOGY_ROOT = Path(__file__).resolve().parent.parent


def _ttl_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.ttl"))


def _count_distinct_subjects(g: Graph, predicate: URIRef, object_: URIRef) -> int:
    return len({s for s in g.subjects(predicate=predicate, object=object_)})


def _count_properties(g: Graph) -> tuple[int, int]:
    obj = _count_distinct_subjects(g, RDF.type, OWL.ObjectProperty)
    data = _count_distinct_subjects(g, RDF.type, OWL.DatatypeProperty)
    return obj, data


def _count_named_individuals(g: Graph) -> int:
    """Subjects typed by something that's also typed as owl:Class."""
    classes = {s for s in g.subjects(predicate=RDF.type, object=OWL.Class)}
    individuals: set[URIRef] = set()
    for s, _, o in g.triples((None, RDF.type, None)):
        if isinstance(o, URIRef) and o in classes and isinstance(s, URIRef):
            individuals.add(s)
    return len(individuals)


def validate(root: Path = ONTOLOGY_ROOT) -> Graph:
    files = _ttl_files(root)
    if not files:
        print(f"No .ttl files found under {root}")
        sys.exit(1)

    g = Graph()
    print(f"Parsing {len(files)} ontology file(s)...")
    for path in files:
        try:
            g.parse(path, format="turtle")
        except Exception as e:
            print(f"  FAIL {path.name}: {e}")
            sys.exit(1)
        print(f"  ok   {path.name}")

    classes = _count_distinct_subjects(g, RDF.type, OWL.Class)
    obj_props, data_props = _count_properties(g)
    individuals = _count_named_individuals(g)
    labels = sum(1 for _ in g.triples((None, RDFS.label, None)))
    comments = sum(1 for _ in g.triples((None, RDFS.comment, None)))

    print()
    print(f"Triples:           {len(g)}")
    print(f"Classes:           {classes}")
    print(f"Object properties: {obj_props}")
    print(f"Datatype props:    {data_props}")
    print(f"Named individuals: {individuals}")
    print(f"rdfs:label triples:   {labels}")
    print(f"rdfs:comment triples: {comments}")
    print()
    print("Ontology parses cleanly. (HermiT-level DL reasoning not run.)")
    return g


if __name__ == "__main__":
    validate()
