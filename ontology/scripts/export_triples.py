"""Export inferred triples from the Coffee Atlas ontology to DuckDB."""

import sys
from pathlib import Path


def export():
    try:
        from owlready2 import get_ontology
    except ImportError:
        print("owlready2 is not installed. Run: uv pip install owlready2")
        sys.exit(1)

    ontology_path = Path(__file__).parent.parent / "coffee-atlas-ontology.ttl"
    if not ontology_path.exists():
        print(f"Ontology file not found: {ontology_path}")
        sys.exit(1)

    print(f"Loading ontology from {ontology_path}...")
    onto = get_ontology(ontology_path.as_uri()).load()

    # TODO: Export T-Box + inferred A-Box triples to DuckDB tables
    # 1. Iterate over classes, properties, individuals
    # 2. Map to relational schema
    # 3. Insert into DuckDB via backend.db.connection

    triple_count = 0
    for s, p, o in onto.get_triples():
        triple_count += 1

    print(f"Total triples: {triple_count}")
    print("Export to DuckDB not yet implemented.")


if __name__ == "__main__":
    export()
