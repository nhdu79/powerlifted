"""
Regression tests for rules.upperbound.upperbound_rules — pi(O) (per-axiom
rules plus the auxiliary top-population rules), and the equality axioms and
UNA rules added when equality can be derived.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/upperbound/tests/test_upperbound_rules.py

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
    FunctionalRole,
    Individual,
    MinCardinalityConcept,
    Nominal,
    OWL_THING,
    Ontology,
    QualifiedExistentialConcept,
    SelfConcept,
    normalize_ontology,
)
from owl.parser import UnsupportedConstructError  # noqa: E402
from pddl.conditions import Atom  # noqa: E402

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.equality_rules import equality_rules  # noqa: E402
from rules.table1.table1_rules import neq_denial_rules  # noqa: E402
from rules.table1.top_population import top_population_rules  # noqa: E402
from rules.una_rules import una_rules  # noqa: E402
from rules.normal_form import NORMAL_FORMS, normal_form  # noqa: E402
from rules.upperbound.upperbound_rules import (  # noqa: E402
    compute_upperbound_rules,
    translate_ontology_by_label,
)

R = AtomicRole("http://ex/R")
S = AtomicRole("http://ex/S")
A = AtomicConcept("http://ex/A")
B = AtomicConcept("http://ex/B")


class ComputeUpperboundRulesTest(unittest.TestCase):
    def test_translates_every_classified_axiom(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            axioms=[ConceptInclusion(A, B)],
        )
        normalize_ontology(ontology)

        rules = compute_upperbound_rules(ontology)

        # Only the O2-shaped A⊑B rule: no rule reads ⊤, so no top-population.
        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
                )
            ],
        )

    def test_adds_top_population_only_if_some_rule_reads_top(self):
        for sub, expected in ((A, False), (OWL_THING, True)):
            ontology = Ontology(
                iri="http://ex",
                concepts={A.id: A, B.id: B},
                axioms=[ConceptInclusion(sub, B)],
            )
            normalize_ontology(ontology)

            rules = compute_upperbound_rules(ontology)

            top_population = top_population_rules(ontology)
            self.assertTrue(top_population)
            self.assertEqual(all(r in rules for r in top_population), expected, sub)
            self.assertEqual(any(r in rules for r in top_population), expected, sub)

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

            rules = compute_upperbound_rules(ontology)

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
            compute_upperbound_rules(ontology)


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

    def test_upperbound_without_equality_is_the_flattened_grouped_result(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            axioms=[ConceptInclusion(A, B)],
        )
        normalize_ontology(ontology)

        flattened = compute_upperbound_rules(ontology)
        by_label = translate_ontology_by_label(ontology)
        # A⊑B reads no ⊤, so no top-population rules.
        grouped = [rule for rules in by_label.values() for rule in rules]

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


def _ontology(*axioms, roles=()):
    ontology = Ontology(
        iri="http://ex",
        concepts={A.id: A, B.id: B},
        roles={r.id: r for r in roles},
        axioms=list(axioms),
    )
    normalize_ontology(ontology)
    return ontology


SYMMETRY = equality_rules({})[0]


class EqualityInUpperboundTest(unittest.TestCase):
    def test_no_equality_rules_without_equality(self):
        rules = compute_upperbound_rules(
            _ontology(ConceptInclusion(A, B)), constants=["a", "b"]
        )

        self.assertNotIn(SYMMETRY, rules)
        self.assertFalse(any(r in rules for r in una_rules(["a", "b"])))

    def test_self_sub_adds_no_equality_or_una_rules(self):
        # O5's body reads x ≈ y, but reflexivity is already in the initial
        # state, so it must not bring in (EQ1)-(EQ4) or the UNA rules.
        ontology = _ontology(ConceptInclusion(SelfConcept(R), A), roles=(R,))

        rules = compute_upperbound_rules(ontology, constants=["a", "b"])

        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("a", ("?x",)),),
                    body=(Atom("r", ("?x", "?y")), Atom("=", ("?x", "?y"))),
                )
            ],
        )

    def test_number_restriction_adds_equality_and_una_rules(self):
        ontology = _ontology(FunctionalRole(R), roles=(R,))

        rules = compute_upperbound_rules(ontology, constants=["a", "b"])

        self.assertIn(SYMMETRY, rules)
        for rule in una_rules(["a", "b"]):
            self.assertIn(rule, rules)

    def test_nominal_adds_equality_rules(self):
        nominal = Nominal(Individual("http://ex/a"))
        rules = compute_upperbound_rules(_ontology(ConceptInclusion(A, nominal)))

        self.assertIn(SYMMETRY, rules)

    def test_task_equality_adds_equality_rules(self):
        ontology = _ontology(ConceptInclusion(A, B))

        rules = compute_upperbound_rules(ontology, constants=["a", "b"], uses_equality=True)

        self.assertIn(SYMMETRY, rules)
        for rule in una_rules(["a", "b"]):
            self.assertIn(rule, rules)

    def test_arities_extend_the_equality_signature(self):
        ontology = _ontology(ConceptInclusion(A, B))
        eq1 = DisjunctiveExistentialRule(
            effect=(Atom("=", ("?x1", "?x1")),), body=(Atom("p", ("?x1",)),)
        )

        rules = compute_upperbound_rules(ontology, arities={"p": 1}, uses_equality=True)

        self.assertIn(eq1, rules)


class RenameTest(unittest.TestCase):
    def test_rules_and_equality_axioms_use_the_renamed_names_only(self):
        ontology = _ontology(ConceptInclusion(A, B))
        spelled = {"a": "A-pddl", "b": "B-pddl"}

        rules = compute_upperbound_rules(
            ontology,
            arities={"A-pddl": 1},
            uses_equality=True,
            rename=lambda name: spelled.get(name, name),
        )

        self.assertIn(
            DisjunctiveExistentialRule(
                effect=(Atom("B-pddl", ("?x",)),), body=(Atom("A-pddl", ("?x",)),)
            ),
            rules,
        )
        predicates = {a.predicate for r in rules for a in r.body + r.effect}
        self.assertEqual(predicates, {"A-pddl", "B-pddl", "="})


class UpperboundRulesNormalFormTest(unittest.TestCase):
    def test_every_upperbound_rule_is_normalised(self):
        # O10/O14 are normalised by table1_rules; the rest are already.
        nominal = Nominal(Individual("http://ex/a"))
        ontology = _ontology(
            ConceptInclusion(A, QualifiedExistentialConcept(R, B)),
            ConceptInclusion(A, MinCardinalityConcept(R, 2, B)),
            ConceptInclusion(OWL_THING, B),
            ConceptInclusion(A, nominal),
            FunctionalRole(R),
            roles=(R,),
        )

        rules = compute_upperbound_rules(ontology, constants=["a", "b"])

        forms = {normal_form(rule) for rule in rules}
        self.assertEqual(forms, set(NORMAL_FORMS))


if __name__ == "__main__":
    unittest.main()
