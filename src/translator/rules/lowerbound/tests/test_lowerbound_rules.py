"""
Regression tests for rules.lowerbound.lowerbound_rules — TODO.md's "Computing
Lowerbound rules pipeline", now computed entirely by Clipper rewriting
the shifted ontology (see owl.ontology_shifter).

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/lowerbound/tests/test_lowerbound_rules.py

from anywhere (the `owl`/`pddl`/`rules` package paths are resolved
relative to this file, not the current working directory).

HornShiqFragmentAxiomsTest, ShiftedOntologyAxiomsTest,
AssertStablePredicateNamesTest, NewPredicateRulesTest, and
WarnAboutNewPredicatesTest are hermetic (no external process). The
ComputeLowerboundRulesIntegrationTest class actually shells out to the
Clipper binary and is skipped unless one is found at a known path (see
TODO.md's own path-resolution snippet).
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
    O3,
    O10,
    O11,
    O13,
    AtomicConcept,
    AtomicRole,
    ConceptInclusion,
    FunctionalRole,
    MaxCardinalityConcept,
    MinCardinalityConcept,
    Ontology,
    OWL_NOTHING,
    OWL_THING,
    QualifiedExistentialConcept,
    UnionConcept,
    UniversalConcept,
    normalize_ontology,
)
from owl.clipper import Clipper  # noqa: E402
from owl.ontology_shifter import shift_ontology  # noqa: E402
from pddl.conditions import Atom  # noqa: E402

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.lowerbound.lowerbound_rules import (  # noqa: E402
    _assert_stable_predicate_names,
    _warn_about_new_predicates,
    compute_lowerbound_rules,
    horn_shiq_fragment_axioms,
    new_predicate_rules,
    shifted_ontology_axioms,
)

R = AtomicRole("http://ex/R")
A = AtomicConcept("http://ex/A")
B = AtomicConcept("http://ex/B")
B1 = AtomicConcept("http://ex/B1")
B2 = AtomicConcept("http://ex/B2")

_CLIPPER_CANDIDATES = [
    "/home/zinzin2312/repos/clipper/clipper-distribution/target/clipper/clipper.sh",
    "/Users/duynhu/repos/clipper/clipper-distribution/target/clipper/clipper.sh",
]
_CLIPPER_PATH = next((p for p in _CLIPPER_CANDIDATES if Path(p).exists()), None)


class HornShiqFragmentAxiomsTest(unittest.TestCase):
    def test_includes_o1_o3_o10_o13_unrestricted(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            roles={R.id: R},
            axioms=[
                ConceptInclusion(A, OWL_NOTHING),  # O1
                ConceptInclusion(QualifiedExistentialConcept(R, A), B),  # O3
                ConceptInclusion(A, QualifiedExistentialConcept(R, B)),  # O10
                ConceptInclusion(OWL_THING, UniversalConcept(R, A)),  # O13
            ],
        )
        normalize_ontology(ontology)

        axioms = horn_shiq_fragment_axioms(ontology)

        for label in (O1, O3, O10, O13):
            (ax,) = ontology.axiom_types[label]
            self.assertIn(ax, axioms)
        self.assertEqual(len(axioms), 4)

    def test_o11_kept_only_for_n_in_zero_or_one(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            roles={R.id: R},
            axioms=[
                ConceptInclusion(A, MaxCardinalityConcept(R, 0, B)),
                ConceptInclusion(A, MaxCardinalityConcept(R, 1, B)),
                ConceptInclusion(A, MaxCardinalityConcept(R, 2, B)),
                FunctionalRole(R),  # n=1
            ],
        )
        normalize_ontology(ontology)

        axioms = horn_shiq_fragment_axioms(ontology)

        self.assertEqual(len(axioms), 3)  # n=0, n=1, FunctionalRole — not n=2
        n2_axiom = ontology.axiom_types[O11][2]
        self.assertNotIn(n2_axiom, axioms)

    def test_o14_kept_only_for_n_at_least_one(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            roles={R.id: R},
            axioms=[ConceptInclusion(A, MinCardinalityConcept(R, 2, B))],
        )
        normalize_ontology(ontology)

        axioms = horn_shiq_fragment_axioms(ontology)

        self.assertEqual(len(axioms), 1)

    def test_o2_always_excluded(self):
        # Every O2 axiom (m=1 or m>=2) reaches Clipper only through
        # owl.ontology_shifter.shift_ontology — see ShiftedOntologyAxiomsTest.
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B1.id: B1, B2.id: B2},
            axioms=[
                ConceptInclusion(A, B1),  # O2, m=1
                ConceptInclusion(A, UnionConcept((B1, B2))),  # O2, m=2
            ],
        )
        normalize_ontology(ontology)

        self.assertEqual(horn_shiq_fragment_axioms(ontology), [])


class ShiftedOntologyAxiomsTest(unittest.TestCase):
    def test_is_horn_shiq_fragment_plus_shift_ontology(self):
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B, B1.id: B1, B2.id: B2},
            roles={R.id: R},
            axioms=[
                ConceptInclusion(QualifiedExistentialConcept(R, A), B),  # O3
                ConceptInclusion(A, UnionConcept((B1, B2))),  # O2, m=2
            ],
        )
        normalize_ontology(ontology)

        axioms = shifted_ontology_axioms(ontology)

        self.assertEqual(
            axioms, horn_shiq_fragment_axioms(ontology) + shift_ontology(ontology)
        )

    def test_original_o2_axiom_is_never_present(self):
        original = ConceptInclusion(A, UnionConcept((B1, B2)))
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B1.id: B1, B2.id: B2},
            axioms=[original],
        )
        normalize_ontology(ontology)

        self.assertNotIn(original, shifted_ontology_axioms(ontology))

    def test_o2_m1_axiom_is_present_verbatim(self):
        m1_axiom = ConceptInclusion(A, B1)
        ontology = Ontology(
            iri="http://ex", concepts={A.id: A, B1.id: B1}, axioms=[m1_axiom]
        )
        normalize_ontology(ontology)

        self.assertIn(m1_axiom, shifted_ontology_axioms(ontology))


class AssertStablePredicateNamesTest(unittest.TestCase):
    def test_no_raise_when_names_already_stable(self):
        clipper = Clipper("unused", "unused")
        _assert_stable_predicate_names({"a", "r"}, clipper)  # must not raise

    def test_raises_on_a_name_clipper_would_rename(self):
        clipper = Clipper("unused", "unused")
        with self.assertRaises(ValueError):
            _assert_stable_predicate_names({"Not-Stable"}, clipper)


class NewPredicateRulesTest(unittest.TestCase):
    def test_empty_when_every_rule_only_uses_known_names(self):
        rules = [
            DisjunctiveExistentialRule(
                effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
            )
        ]

        self.assertEqual(new_predicate_rules(rules, {"a", "b"}), [])

    def test_keeps_the_rule_using_a_predicate_clipper_introduced_itself(self):
        clipper_rule = DisjunctiveExistentialRule(
            effect=(Atom("eliminatemincardfresh1", ("?x", "?y")),), body=()
        )
        known_rule = DisjunctiveExistentialRule(
            effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
        )

        self.assertEqual(
            new_predicate_rules([known_rule, clipper_rule], {"a", "b"}), [clipper_rule]
        )


class WarnAboutNewPredicatesTest(unittest.TestCase):
    def test_no_warning_when_nothing_is_flagged(self):
        ontology = Ontology(iri="http://ex")

        _warn_about_new_predicates(ontology, [], {"a", "b"})

        self.assertEqual(ontology.warnings, [])

    def test_warns_about_flagged_rules_predicate_names(self):
        ontology = Ontology(iri="http://ex")
        flagged = [
            DisjunctiveExistentialRule(
                effect=(Atom("eliminatemincardfresh1", ("?x", "?y")),), body=()
            )
        ]

        _warn_about_new_predicates(ontology, flagged, {"a"})

        self.assertEqual(len(ontology.warnings), 1)
        self.assertIn("eliminatemincardfresh1", ontology.warnings[0])


@unittest.skipUnless(_CLIPPER_PATH, "no Clipper binary found at a known path")
class ComputeLowerboundRulesIntegrationTest(unittest.TestCase):
    def test_functional_role_produces_a_denial_rule_via_clipper(self):
        # FunctionalRole is O11-shaped with n=1: Clipper rewrites it as a
        # denial over two distinct fillers.
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A},
            roles={R.id: R},
            axioms=[FunctionalRole(R)],
        )
        normalize_ontology(ontology)

        rules, new_rules = compute_lowerbound_rules(ontology, _CLIPPER_PATH)

        self.assertTrue(
            any(
                not r.effect
                and any(atom.predicate == "r" for atom in r.body)
                and any(atom.negated for atom in r.body)
                for r in rules
            )
        )
        self.assertEqual(new_rules, [])  # nothing but known predicates here

    def test_o2_m1_axiom_produces_a_derivation_rule(self):
        # A ⊑ B1 (m=1) must still reach Clipper, verbatim, and produce
        # its ordinary derivation rule — this is the gap that was fixed:
        # previously an O2 axiom with m=1 was excluded from both
        # horn_shiq_fragment_axioms (which drops all O2) and
        # shift_ontology (which only shifts m>=2), so its content never
        # reached the lowerbound at all.
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B1.id: B1},
            axioms=[ConceptInclusion(A, B1)],
        )
        normalize_ontology(ontology)

        rules, _ = compute_lowerbound_rules(ontology, _CLIPPER_PATH)

        self.assertIn(
            DisjunctiveExistentialRule(
                effect=(Atom("b1", ("?x",)),), body=(Atom("a", ("?x",)),)
            ),
            rules,
        )

    def test_o2_rule_comes_from_the_shifted_ontology(self):
        # A ⊑ B1⊔B2 (m=2) never reaches Clipper verbatim — only its
        # shift (S1-S3, using fresh complement concepts) does.
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B1.id: B1, B2.id: B2},
            axioms=[ConceptInclusion(A, UnionConcept((B1, B2)))],
        )
        normalize_ontology(ontology)

        rules, _ = compute_lowerbound_rules(ontology, _CLIPPER_PATH)

        self.assertEqual(len(rules), 4)  # S1, S2_1, S2_2, S3
        heads = {atom.predicate for r in rules for atom in r.effect}
        self.assertTrue({"b1", "b2"} <= heads)
        # S1 -> ⊥: Clipper renders this as nothing(x), which
        # parse_clipper_rules normalises to an empty effect, not a
        # "nothing" atom.
        self.assertTrue(any(not r.effect for r in rules))
        self.assertNotIn("nothing", heads)

    def test_min_cardinality_flags_clippers_own_witness_predicate(self):
        # Clipper eliminates a general min-cardinality restriction using
        # its own internal "eliminatemincardfreshN" witness predicates —
        # names we never sent it.
        ontology = Ontology(
            iri="http://ex",
            concepts={A.id: A, B.id: B},
            roles={R.id: R},
            axioms=[ConceptInclusion(A, MinCardinalityConcept(R, 2, B))],
        )
        normalize_ontology(ontology)

        rules, new_rules = compute_lowerbound_rules(ontology, _CLIPPER_PATH)

        self.assertTrue(new_rules)
        self.assertTrue(set(new_rules) <= set(rules))
        self.assertIn("Clipper introduced new predicate(s)", ontology.warnings[0])


if __name__ == "__main__":
    unittest.main()
