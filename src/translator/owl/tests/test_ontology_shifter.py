"""
Regression tests for owl.ontology_shifter — Definition 4.3's shifting
defined directly on O2 (disjunctive) DL axioms.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/owl/tests/test_ontology_shifter.py

from anywhere (the `owl`/`pddl` package paths are resolved relative to
this file, not the current working directory).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl import (  # noqa: E402
    O2,
    AtomicConcept,
    ConceptInclusion,
    IntersectionConcept,
    Ontology,
    OWL_NOTHING,
    UnionConcept,
    normalize_ontology,
)
from owl.ontology_normalizer.fresh_symbols import (  # noqa: E402
    fresh_complement_concept_for,
)
from owl.ontology_shifter import shift_o2_axiom, shift_ontology  # noqa: E402

A1 = AtomicConcept("http://ex/A1")
A2 = AtomicConcept("http://ex/A2")
B1 = AtomicConcept("http://ex/B1")
B2 = AtomicConcept("http://ex/B2")
B3 = AtomicConcept("http://ex/B3")
Bp1 = fresh_complement_concept_for(B1)
Bp2 = fresh_complement_concept_for(B2)
Bp3 = fresh_complement_concept_for(B3)
Ap1 = fresh_complement_concept_for(A1)
Ap2 = fresh_complement_concept_for(A2)


class ShiftO2AxiomTest(unittest.TestCase):
    def test_single_conjunct_two_disjuncts(self):
        # A1 ⊑ B1 ⊔ B2
        shifted = shift_o2_axiom(ConceptInclusion(A1, UnionConcept((B1, B2))))

        self.assertEqual(
            shifted,
            [
                ConceptInclusion(
                    IntersectionConcept((A1, Bp1, Bp2)), OWL_NOTHING
                ),
                ConceptInclusion(IntersectionConcept((A1, Bp2)), B1),
                ConceptInclusion(IntersectionConcept((A1, Bp1)), B2),
                ConceptInclusion(IntersectionConcept((Bp1, Bp2)), Ap1),
            ],
        )

    def test_single_disjunct_is_passed_through_unchanged(self):
        # A1 ⊑ B1 (m=1: already deterministic, nothing to shift).
        ax = ConceptInclusion(A1, B1)
        self.assertEqual(shift_o2_axiom(ax), [ax])

    def test_three_disjuncts_gives_three_s2_rules(self):
        # A1 ⊑ B1 ⊔ B2 ⊔ B3
        shifted = shift_o2_axiom(ConceptInclusion(A1, UnionConcept((B1, B2, B3))))

        self.assertEqual(len(shifted), 1 + 3 + 1)  # S1, 3x S2, S3
        self.assertIn(
            ConceptInclusion(IntersectionConcept((A1, Bp1, Bp3)), B2), shifted
        )

    def test_two_conjuncts_gives_two_s3_rules(self):
        # A1 ⊓ A2 ⊑ B1 ⊔ B2
        shifted = shift_o2_axiom(
            ConceptInclusion(IntersectionConcept((A1, A2)), UnionConcept((B1, B2)))
        )

        self.assertEqual(len(shifted), 1 + 2 + 2)  # S1, 2x S2, 2x S3
        self.assertIn(
            ConceptInclusion(IntersectionConcept((A2, Bp1, Bp2)), Ap1), shifted
        )
        self.assertIn(
            ConceptInclusion(IntersectionConcept((A1, Bp1, Bp2)), Ap2), shifted
        )


class ShiftOntologyTest(unittest.TestCase):
    def test_m2_axiom_shifted_m1_axiom_passed_through(self):
        m1_axiom = ConceptInclusion(A2, B1)
        ontology = Ontology(
            iri="http://ex",
            concepts={c.id: c for c in (A1, A2, B1, B2)},
            axioms=[
                ConceptInclusion(A1, UnionConcept((B1, B2))),  # m=2: shifted
                m1_axiom,  # m=1: passed through unchanged
            ],
        )
        normalize_ontology(ontology)

        shifted = shift_ontology(ontology)

        self.assertEqual(len(shifted), 5)  # 4 shifted + the m=1 axiom itself
        self.assertIn(m1_axiom, shifted)

    def test_empty_when_no_o2_axioms(self):
        ontology = Ontology(
            iri="http://ex", concepts={A1.id: A1, B1.id: B1}, axioms=[]
        )
        normalize_ontology(ontology)

        self.assertEqual(shift_ontology(ontology), [])

    def test_operates_on_a_copy_not_the_original_axiom_objects(self):
        # The same normalized Ontology is also used, unmodified,
        # elsewhere (e.g. Table 1 rules for the upperbound) — shifting
        # must never be able to touch it, so shift_ontology deep-copies
        # first rather than reading the ontology passed in directly.
        ontology = Ontology(
            iri="http://ex",
            concepts={A1.id: A1, B1.id: B1},
            axioms=[ConceptInclusion(A1, B1)],  # m=1: passed through
        )
        normalize_ontology(ontology)
        (original_axiom,) = ontology.axiom_types[O2]

        (result,) = shift_ontology(ontology)

        self.assertEqual(result, original_axiom)
        self.assertIsNot(result, original_axiom)


if __name__ == "__main__":
    unittest.main()
