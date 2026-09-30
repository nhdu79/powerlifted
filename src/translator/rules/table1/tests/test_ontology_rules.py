"""
Regression tests for rules.table1.ontology_rules — assembling a whole
ontology's rule set (per-axiom rules plus the auxiliary top-population
rules).

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/table1/tests/test_ontology_rules.py

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

from owl import (  # noqa: E402
    O1,
    O2,
    OWL_NOTHING,
    TABLE1_LABELS,
    AtomicConcept,
    AtomicRole,
    ConceptInclusion,
    MinCardinalityConcept,
    Ontology,
    QualifiedExistentialConcept,
    normalize_ontology,
)
from owl.parser import UnsupportedConstructError  # noqa: E402
from pddl.conditions import Atom  # noqa: E402

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.table1.ontology_rules import (  # noqa: E402
    translate_ontology,
    translate_ontology_by_label,
)
from rules.table1.table1_rules import neq_denial_rules  # noqa: E402
from rules.table1.top_population import top_population_rules  # noqa: E402

R = AtomicRole("http://ex/R")
S = AtomicRole("http://ex/S")
A = AtomicConcept("http://ex/A")
B = AtomicConcept("http://ex/B")


class TranslateOntologyTest(unittest.TestCase):
    def test_translates_every_classified_axiom_plus_top_population(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            axioms=[ConceptInclusion(A, B)],
        )
        normalize_ontology(ontology)

        rules = translate_ontology(ontology)

        # 1 top-population rule for A, 1 for B, plus the O2-shaped A⊑B rule.
        self.assertEqual(len(rules), 3)
        self.assertIn(
            DisjunctiveExistentialRule(
                effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
            ),
            rules,
        )

    def test_adds_neq_denials_only_for_min_cardinality_at_least_2(self):
        denials = neq_denial_rules()
        for n, expected in ((1, False), (2, True)):
            ontology = Ontology(
                iri="http://ex",
                concepts={A.id: A, B.id: B},
                roles={R.id: R},
                axioms=[ConceptInclusion(A, MinCardinalityConcept(R, n, B))],
            )
            normalize_ontology(ontology)

            rules = translate_ontology(ontology)

            self.assertEqual(all(d in rules for d in denials), expected, n)
            self.assertEqual(any(d in rules for d in denials), expected, n)

    def test_raises_on_unsupported_ontology(self):
        # ∃R.A ⊑ ∃S.B has no Table 1 row and nothing rewrites it (see
        # EnsureFullySupportedTest in owl.ontology_normalizer's own tests).
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(
                    QualifiedExistentialConcept(R, A), QualifiedExistentialConcept(S, B)
                )
            ],
        )
        normalize_ontology(ontology)

        with self.assertRaises(UnsupportedConstructError):
            translate_ontology(ontology)


class TranslateOntologyByLabelTest(unittest.TestCase):
    def test_groups_rules_under_their_table1_label(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            axioms=[ConceptInclusion(A, B), ConceptInclusion(A, OWL_NOTHING)],
        )
        normalize_ontology(ontology)

        by_label = translate_ontology_by_label(ontology)

        self.assertEqual(set(by_label), set(TABLE1_LABELS))
        self.assertEqual(
            by_label[O2],
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
                )
            ],
        )
        self.assertEqual(
            by_label[O1],
            [DisjunctiveExistentialRule(effect=(), body=(Atom("a", ("?x",)),))],
        )
        for label, rules in by_label.items():
            if label not in (O1, O2):
                self.assertEqual(rules, [], label)

    def test_excludes_top_population_rules(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A},
            axioms=[ConceptInclusion(A, OWL_NOTHING)],
        )
        normalize_ontology(ontology)

        by_label = translate_ontology_by_label(ontology)

        all_rules = [rule for rules in by_label.values() for rule in rules]
        top_population = top_population_rules(ontology)
        self.assertTrue(top_population)
        for rule in top_population:
            self.assertNotIn(rule, all_rules)

    def test_translate_ontology_matches_the_flattened_grouped_result(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            axioms=[ConceptInclusion(A, B)],
        )
        normalize_ontology(ontology)

        flattened = translate_ontology(ontology)
        by_label = translate_ontology_by_label(ontology)
        grouped = top_population_rules(ontology)
        for rules in by_label.values():
            grouped.extend(rules)

        self.assertCountEqual(flattened, grouped)

    def test_raises_on_unsupported_ontology(self):
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(
                    QualifiedExistentialConcept(R, A), QualifiedExistentialConcept(S, B)
                )
            ],
        )
        normalize_ontology(ontology)

        with self.assertRaises(UnsupportedConstructError):
            translate_ontology_by_label(ontology)


if __name__ == "__main__":
    unittest.main()
