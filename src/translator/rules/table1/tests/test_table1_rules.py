"""
Regression tests for rules.table1.table1_rules — the Table 1 (Zhou et al. 2015,
page 7) per-axiom translation.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/table1/tests/test_table1_rules.py

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
    O3,
    O4,
    O5,
    O6,
    O7,
    O8,
    O9,
    O10,
    O11,
    O12,
    O13,
    O14,
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    AtomicRole,
    ConceptInclusion,
    FunctionalRole,
    IntersectionConcept,
    InverseRole,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    MinCardinalityConcept,
    NegatedRole,
    Nominal,
    QualifiedExistentialConcept,
    RoleChain,
    RoleInclusion,
    SelfConcept,
    UnionConcept,
    UniversalConcept,
    classify_axiom,
)
from owl.expressions import Individual  # noqa: E402
from pddl.conditions import Atom  # noqa: E402

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.table1.table1_rules import neq_denial_rules, translate_axiom  # noqa: E402

R = AtomicRole("http://ex/R")
S = AtomicRole("http://ex/S")
T = AtomicRole("http://ex/T")
A = AtomicConcept("http://ex/A")
B = AtomicConcept("http://ex/B")
C = AtomicConcept("http://ex/C")
D = AtomicConcept("http://ex/D")


class TranslateO1Test(unittest.TestCase):
    def test_multiple_conjuncts(self):
        axiom = ConceptInclusion(IntersectionConcept((A, B)), OWL_NOTHING)
        self.assertEqual(classify_axiom(axiom), O1)

        rule = translate_axiom(axiom, O1)

        self.assertEqual(rule.body, (Atom("a", ("?x",)), Atom("b", ("?x",))))
        self.assertEqual(rule.effect, ())

    def test_single_conjunct(self):
        axiom = ConceptInclusion(A, OWL_NOTHING)
        self.assertEqual(classify_axiom(axiom), O1)

        rule = translate_axiom(axiom, O1)

        self.assertEqual(rule.body, (Atom("a", ("?x",)),))
        self.assertEqual(rule.effect, ())


class TranslateO2Test(unittest.TestCase):
    def test_rewritten_to_conjunctive_body_disjunctive_effect(self):
        axiom = ConceptInclusion(IntersectionConcept((A, B)), UnionConcept((C, D)))
        self.assertEqual(classify_axiom(axiom), O2)

        rule = translate_axiom(axiom, O2)

        self.assertEqual(rule.body, (Atom("a", ("?x",)), Atom("b", ("?x",))))
        self.assertEqual(rule.effect, (Atom("c", ("?x",)), Atom("d", ("?x",))))


class TranslateO3Test(unittest.TestCase):
    def test_existential_sub(self):
        axiom = ConceptInclusion(QualifiedExistentialConcept(R, A), B)
        self.assertEqual(classify_axiom(axiom), O3)

        rule = translate_axiom(axiom, O3)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?y")), Atom("a", ("?y",))))
        self.assertEqual(rule.effect, (Atom("b", ("?x",)),))


class TranslateO4Test(unittest.TestCase):
    def test_self_sup(self):
        axiom = ConceptInclusion(A, SelfConcept(R))
        self.assertEqual(classify_axiom(axiom), O4)

        rule = translate_axiom(axiom, O4)

        self.assertEqual(rule.body, (Atom("a", ("?x",)),))
        self.assertEqual(rule.effect, (Atom("r", ("?x", "?x")),))


class TranslateO5Test(unittest.TestCase):
    def test_self_sub(self):
        axiom = ConceptInclusion(SelfConcept(R), A)
        self.assertEqual(classify_axiom(axiom), O5)

        rule = translate_axiom(axiom, O5)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?x")),))
        self.assertEqual(rule.effect, (Atom("a", ("?x",)),))


class TranslateO6Test(unittest.TestCase):
    def test_role_inclusion(self):
        axiom = RoleInclusion(R, S)
        self.assertEqual(classify_axiom(axiom), O6)

        rule = translate_axiom(axiom, O6)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?y")),))
        self.assertEqual(rule.effect, (Atom("s", ("?x", "?y")),))


class TranslateO7Test(unittest.TestCase):
    def test_role_inclusion_into_inverse(self):
        axiom = RoleInclusion(R, InverseRole(S))
        self.assertEqual(classify_axiom(axiom), O7)

        rule = translate_axiom(axiom, O7)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?y")),))
        self.assertEqual(rule.effect, (Atom("s", ("?y", "?x")),))


class TranslateO8Test(unittest.TestCase):
    def test_role_chain(self):
        axiom = RoleInclusion(RoleChain((R, S)), T)
        self.assertEqual(classify_axiom(axiom), O8)

        rule = translate_axiom(axiom, O8)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?z")), Atom("s", ("?z", "?y"))))
        self.assertEqual(rule.effect, (Atom("t", ("?x", "?y")),))


class TranslateO9Test(unittest.TestCase):
    def test_disjoint_roles(self):
        axiom = RoleInclusion(R, NegatedRole(S))
        self.assertEqual(classify_axiom(axiom), O9)

        rule = translate_axiom(axiom, O9)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?y")), Atom("s", ("?x", "?y"))))
        self.assertEqual(rule.effect, ())


class TranslateO10Test(unittest.TestCase):
    def test_existential_sup(self):
        axiom = ConceptInclusion(A, QualifiedExistentialConcept(R, B))
        self.assertEqual(classify_axiom(axiom), O10)

        rule = translate_axiom(axiom, O10)

        self.assertEqual(rule.body, (Atom("a", ("?x",)),))
        self.assertEqual(rule.effect, (Atom("r", ("?x", "?y")), Atom("b", ("?y",))))


class TranslateO11Test(unittest.TestCase):
    def test_max_cardinality_needs_n_plus_1_fillers(self):
        # A ⊑ <=2 R.B needs 3 fillers to force a collision.
        axiom = ConceptInclusion(A, MaxCardinalityConcept(R, 2, B))
        self.assertEqual(classify_axiom(axiom), O11)

        rule = translate_axiom(axiom, O11)

        self.assertEqual(
            rule.body,
            (
                Atom("a", ("?x",)),
                Atom("r", ("?x", "?y1")),
                Atom("b", ("?y1",)),
                Atom("r", ("?x", "?y2")),
                Atom("b", ("?y2",)),
                Atom("r", ("?x", "?y3")),
                Atom("b", ("?y3",)),
            ),
        )
        self.assertEqual(
            rule.effect,
            (
                Atom("=", ("?y1", "?y2")),
                Atom("=", ("?y1", "?y3")),
                Atom("=", ("?y2", "?y3")),
            ),
        )

    def test_functional_role_uses_thing_for_a_and_b(self):
        axiom = FunctionalRole(R)
        self.assertEqual(classify_axiom(axiom), O11)

        rule = translate_axiom(axiom, O11)

        self.assertEqual(
            rule.body,
            (
                Atom("thing", ("?x",)),
                Atom("r", ("?x", "?y1")),
                Atom("thing", ("?y1",)),
                Atom("r", ("?x", "?y2")),
                Atom("thing", ("?y2",)),
            ),
        )
        self.assertEqual(rule.effect, (Atom("=", ("?y1", "?y2")),))


class TranslateO12Test(unittest.TestCase):
    def test_nominal(self):
        individual = Individual("http://ex/a")
        axiom = ConceptInclusion(A, Nominal(individual))
        self.assertEqual(classify_axiom(axiom), O12)

        rule = translate_axiom(axiom, O12)

        self.assertEqual(rule.body, (Atom("a", ("?x",)),))
        self.assertEqual(rule.effect, (Atom("=", ("?x", "a")),))


class TranslateO13Test(unittest.TestCase):
    def test_direct_universal(self):
        axiom = ConceptInclusion(OWL_THING, UniversalConcept(R, A))
        self.assertEqual(classify_axiom(axiom), O13)

        rule = translate_axiom(axiom, O13)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?y")),))
        self.assertEqual(rule.effect, (Atom("a", ("?y",)),))

    def test_inverse_universal_flips_which_argument_gets_the_filler(self):
        axiom = ConceptInclusion(OWL_THING, InverseUniversalConcept(R, A))
        self.assertEqual(classify_axiom(axiom), O13)

        rule = translate_axiom(axiom, O13)

        self.assertEqual(rule.body, (Atom("r", ("?x", "?y")),))
        self.assertEqual(rule.effect, (Atom("a", ("?x",)),))


class TranslateO14Test(unittest.TestCase):
    def test_min_cardinality_needs_n_fillers_marked_pairwise_neq(self):
        axiom = ConceptInclusion(A, MinCardinalityConcept(R, 3, B))
        self.assertEqual(classify_axiom(axiom), O14)

        rule = translate_axiom(axiom, O14)

        self.assertEqual(rule.body, (Atom("a", ("?x",)),))
        self.assertEqual(
            rule.effect,
            (
                Atom("r", ("?x", "?y1")),
                Atom("b", ("?y1",)),
                Atom("r", ("?x", "?y2")),
                Atom("b", ("?y2",)),
                Atom("r", ("?x", "?y3")),
                Atom("b", ("?y3",)),
                Atom("neq_", ("?y1", "?y2")),
                Atom("neq_", ("?y1", "?y3")),
                Atom("neq_", ("?y2", "?y3")),
            ),
        )
        self.assertFalse(any(atom.negated for atom in rule.effect))

    def test_n_equals_1_degenerates_to_o10_shape(self):
        # A ⊑ >=1 R.B has only one filler, so no neq_ atom at all.
        axiom = ConceptInclusion(A, MinCardinalityConcept(R, 1, B))

        rule = translate_axiom(axiom, O14)

        self.assertEqual(rule.body, (Atom("a", ("?x",)),))
        self.assertEqual(
            rule.effect, (Atom("r", ("?x", "?y1")), Atom("b", ("?y1",)))
        )


class NeqDenialRulesTest(unittest.TestCase):
    def test_neq_of_equated_terms_is_bottom_in_both_orders(self):
        self.assertEqual(
            neq_denial_rules(),
            [
                DisjunctiveExistentialRule(
                    effect=(),
                    body=(Atom("neq_", ("?y", "?z")), Atom("=", ("?y", "?z"))),
                ),
                DisjunctiveExistentialRule(
                    effect=(),
                    body=(Atom("neq_", ("?y", "?z")), Atom("=", ("?z", "?y"))),
                ),
            ],
        )

    def test_no_rule_needs_negation(self):
        for rule in neq_denial_rules():
            self.assertFalse(any(atom.negated for atom in rule.body))


if __name__ == "__main__":
    unittest.main()
