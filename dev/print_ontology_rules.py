#! /usr/bin/env python3
"""
Load and normalize every ontology under dev/ontologies/, translate each
into Table 1's DisjunctiveExistentialRule form (Zhou et al. 2015, "Pay-
as-you-go ABox Reasoning"), and print the resulting rules — grouped by
Table 1 label, same grouping and layout as dev/normalize_ontologies.py
uses for axioms — for manual inspection. Not a test — makes no
assertions.

Run with:

    python3 dev/print_ontology_rules.py

from anywhere (paths are resolved relative to this file).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRANSLATOR_DIR = _REPO_ROOT / "src" / "translator"
sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl import TABLE1_LABELS, normalize_ontology, parse_owl
from owl.parser import UnsupportedConstructError
from rules import (
    format_rule,
    neq_denial_rules,
    top_population_rules,
    translate_ontology_by_label,
)
from rules.atoms import NEQ_PREDICATE

ONTOLOGY_DIR = _REPO_ROOT / "dev" / "ontologies"

TOP_POPULATION = "top-population"
NEQ_DENIALS = "neq_-denials"


def main() -> None:
    for path in sorted(ONTOLOGY_DIR.glob("*.owl")):
        print(f"=== {path.name} ===")
        ontology = parse_owl(str(path))
        normalize_ontology(ontology)

        try:
            by_label = translate_ontology_by_label(ontology)
        except UnsupportedConstructError as error:
            print(f"skipped — {error}")
            print()
            continue

        by_label[TOP_POPULATION] = top_population_rules(ontology)
        uses_neq = any(
            a.predicate == NEQ_PREDICATE
            for rules in by_label.values()
            for rule in rules
            for a in rule.effect
        )
        by_label[NEQ_DENIALS] = neq_denial_rules() if uses_neq else []
        total = sum(len(rules) for rules in by_label.values())

        print(f"rules ({total}):")
        for label in (TOP_POPULATION,) + TABLE1_LABELS + (NEQ_DENIALS,):
            rules = by_label[label]
            if not rules:
                continue
            print(f"  {label} ({len(rules)}):")
            for rule in rules:
                print(f"    {format_rule(rule)}")

        print()


if __name__ == "__main__":
    main()
