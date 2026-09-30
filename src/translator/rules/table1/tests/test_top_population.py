"""
Regression tests for rules.table1.top_population.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/table1/tests/test_top_population.py

from anywhere (the `owl`/`pddl`/`rules` package paths are resolved
relative to this file, not the current working directory).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl import OWL_THING, AtomicConcept, AtomicRole, Ontology  # noqa: E402
from pddl.conditions import Atom  # noqa: E402

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.table1.top_population import top_population_rules  # noqa: E402

R = AtomicRole("http://ex/R")
A = AtomicConcept("http://ex/A")
B = AtomicConcept("http://ex/B")


class TopPopulationRulesTest(unittest.TestCase):
    def test_one_rule_per_atomic_concept_and_two_per_atomic_role(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B, OWL_THING.id: OWL_THING},
            roles={R.id: R},
        )

        rules = top_population_rules(ontology)

        self.assertCountEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("thing", ("?x",)),), body=(Atom("a", ("?x",)),)
                ),
                DisjunctiveExistentialRule(
                    effect=(Atom("thing", ("?x",)),), body=(Atom("b", ("?x",)),)
                ),
                DisjunctiveExistentialRule(
                    effect=(Atom("thing", ("?x",)),), body=(Atom("r", ("?x", "?y")),)
                ),
                DisjunctiveExistentialRule(
                    effect=(Atom("thing", ("?y",)),), body=(Atom("r", ("?x", "?y")),)
                ),
            ],
        )

    def test_owl_thing_itself_gets_no_rule(self):
        ontology = Ontology(iri="http://ex", concepts={OWL_THING.id: OWL_THING})
        self.assertEqual(top_population_rules(ontology), [])


if __name__ == "__main__":
    unittest.main()
