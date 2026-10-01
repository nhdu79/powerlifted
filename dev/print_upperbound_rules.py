#! /usr/bin/env python3
"""
Load and normalize every ontology under dev/ontologies/ and print its
upperbound rules (rules.upperbound.compute_upperbound_rules), grouped by
their normal form (2)-(4) of Zhou et al. 2015, page 5 (rules.normal_form) —
for manual inspection. Not a test — makes no assertions.

Only the ontology is known here, without a task: the equality axioms appear
if the ontology itself derives equality, and there are no UNA rules, which
need the task's objects.

Run with:

    python3 dev/print_upperbound_rules.py

from anywhere (paths are resolved relative to this file).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRANSLATOR_DIR = _REPO_ROOT / "src" / "translator"
sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl import normalize_ontology, parse_owl
from owl.parser import UnsupportedConstructError
from rules import (
    BOTTOM,
    DISJUNCTIVE,
    EXISTENTIAL,
    compute_upperbound_rules,
    format_rule,
    group_by_normal_form,
)

ONTOLOGY_DIR = _REPO_ROOT / "dev" / "ontologies"

FORM_TITLES = {
    BOTTOM: "(2) body → ⊥",
    EXISTENTIAL: "(3) body → ∃z γ",
    DISJUNCTIVE: "(4) body → γ1 ∨ … ∨ γm",
}


def main() -> None:
    for path in sorted(ONTOLOGY_DIR.glob("*.owl")):
        print(f"=== {path.name} ===")
        ontology = parse_owl(str(path))
        normalize_ontology(ontology)

        try:
            rules = compute_upperbound_rules(ontology)
        except UnsupportedConstructError as error:
            print(f"skipped — {error}")
            print()
            continue

        print(f"rules ({len(rules)}):")
        for form, rules in group_by_normal_form(rules).items():
            if not rules:
                continue
            print(f"  {FORM_TITLES[form]} ({len(rules)}):")
            for rule in rules:
                print(f"    {format_rule(rule)}")

        print()


if __name__ == "__main__":
    main()
