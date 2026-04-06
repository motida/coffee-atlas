"""Validate the Coffee Atlas ontology using Owlready2 and HermiT reasoner."""

import sys
from pathlib import Path


def validate():
    try:
        from owlready2 import get_ontology, sync_reasoner_hermit
    except ImportError:
        print("owlready2 is not installed. Run: uv pip install owlready2")
        sys.exit(1)

    ontology_path = Path(__file__).parent.parent / "coffee-atlas-ontology.ttl"
    if not ontology_path.exists():
        print(f"Ontology file not found: {ontology_path}")
        sys.exit(1)

    print(f"Loading ontology from {ontology_path}...")
    onto = get_ontology(ontology_path.as_uri()).load()

    print("Running HermiT reasoner...")
    try:
        sync_reasoner_hermit(onto)
        print("Ontology is consistent.")
    except Exception as e:
        print(f"Ontology is inconsistent: {e}")
        sys.exit(1)

    print(f"Classes: {len(list(onto.classes()))}")
    print(f"Properties: {len(list(onto.properties()))}")
    print(f"Individuals: {len(list(onto.individuals()))}")


if __name__ == "__main__":
    validate()
