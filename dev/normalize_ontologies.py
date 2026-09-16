#! /usr/bin/env python3
"""
Load and normalize every ontology under dev/ontologies/, printing the
result for manual inspection. Not a test — makes no assertions.

Run with:

    python3 dev/normalize_ontologies.py

from anywhere (paths are resolved relative to this file).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRANSLATOR_DIR = _REPO_ROOT / "src" / "translator"
sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl import TABLE1_LABELS, UNCLASSIFIED, normalize_ontology, parse_owl
from owl.axioms import _dl_axiom

ONTOLOGY_DIR = _REPO_ROOT / "dev" / "ontologies"


def main() -> None:
    for path in sorted(ONTOLOGY_DIR.glob("*.owl")):
        print(f"=== {path.name} ===")
        ontology = parse_owl(str(path))

        if ontology.warnings:
            print(f"warnings ({len(ontology.warnings)}):")
            for w in ontology.warnings:
                print(f"  ! {w}")

        normalize_ontology(ontology)

        print(f"axioms ({len(ontology.axioms)}):")
        for label in TABLE1_LABELS + (UNCLASSIFIED,):
            axioms = ontology.axiom_types[label]
            if not axioms:
                continue
            print(f"  {label} ({len(axioms)}):")
            for ax in axioms:
                print(f"    {_dl_axiom(ax)}")

        print()


if __name__ == "__main__":
    main()
