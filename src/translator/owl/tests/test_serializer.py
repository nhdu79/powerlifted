"""
Regression tests for owl.serializer — round-tripping normalized axioms
back to an OWL Turtle file that owl.parser.parse_owl can read again.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/owl/tests/test_serializer.py

from anywhere (the `owl`/`pddl` package paths are resolved relative to
this file, not the current working directory).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl import (  # noqa: E402
    O1,
    O2,
    O3,
    O6,
    O7,
    O10,
    O11,
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
    QualifiedExistentialConcept,
    RoleInclusion,
    UnionConcept,
    UniversalConcept,
    classify_axiom,
    normalize_ontology,
    parse_owl,
)
from owl.serializer import referenced_predicate_names, serialize_axioms  # noqa: E402

R = AtomicRole("http://ex/R")
S = AtomicRole("http://ex/S")
A = AtomicConcept("http://ex/A")
B = AtomicConcept("http://ex/B")


def _round_trip(axioms):
    """Serialize axioms, parse the result back, normalize it, and return
    the labels classify_axiom assigns each resulting axiom."""
    text = serialize_axioms(axioms, "http://ex/onto")
    with tempfile.NamedTemporaryFile(suffix=".owl", mode="w", delete=False) as f:
        f.write(text)
        path = f.name
    ontology = parse_owl(path)
    Path(path).unlink()
    normalize_ontology(ontology)
    assert not ontology.warnings, ontology.warnings
    return [classify_axiom(ax) for ax in ontology.axioms]


class SerializeAxiomsTest(unittest.TestCase):
    def test_o1_single_and_multi_conjunct(self):
        labels = _round_trip(
            [
                ConceptInclusion(A, OWL_NOTHING),
                ConceptInclusion(IntersectionConcept((A, B)), OWL_NOTHING),
            ]
        )
        self.assertEqual(labels, [O1, O1])

    def test_o3(self):
        labels = _round_trip([ConceptInclusion(QualifiedExistentialConcept(R, A), B)])
        self.assertEqual(labels, [O3])

    def test_o6(self):
        self.assertEqual(_round_trip([RoleInclusion(R, S)]), [O6])

    def test_o7(self):
        self.assertEqual(_round_trip([RoleInclusion(R, InverseRole(S))]), [O7])

    def test_o10(self):
        labels = _round_trip([ConceptInclusion(A, QualifiedExistentialConcept(R, B))])
        self.assertEqual(labels, [O10])

    def test_o11_max_cardinality_and_functional_role(self):
        labels = _round_trip(
            [
                ConceptInclusion(A, MaxCardinalityConcept(R, 0, B)),
                ConceptInclusion(A, MaxCardinalityConcept(R, 2, B)),
                FunctionalRole(S),
            ]
        )
        self.assertEqual(labels, [O11, O11, O11])

    def test_o14(self):
        labels = _round_trip([ConceptInclusion(A, MinCardinalityConcept(R, 2, B))])
        self.assertEqual(labels, [O14])

    def test_o13_direct_and_inverse(self):
        # owl.parser can't round-trip an axiom whose subject is owl:Thing
        # itself (it only scans named/blank-node subjects — a pre-
        # existing parser limitation), so this checks the serialized
        # Turtle directly rather than via _round_trip; Clipper (the
        # actual consumer, using the full OWL API) accepts it fine —
        # verified separately against the real binary.
        text = serialize_axioms(
            [
                ConceptInclusion(OWL_THING, UniversalConcept(R, A)),
                ConceptInclusion(OWL_THING, InverseUniversalConcept(S, B)),
            ],
            "http://ex",
        )
        self.assertIn("owl:Thing", text)
        self.assertIn("owl:allValuesFrom", text)
        self.assertIn("owl:inverseOf", text)

    def test_plain_subsumption_single_and_multi_conjunct(self):
        # owl.ontology_shifter's S2/S3 shape: a conjunction of atomic
        # concepts implies a single atomic concept.
        labels = _round_trip(
            [
                ConceptInclusion(A, B),
                ConceptInclusion(IntersectionConcept((A, B)), OWL_THING),
            ]
        )
        self.assertEqual(labels, [O2, O2])

    def test_unsupported_axiom_shape_raises(self):
        # General disjunction (m>=2) is only ever accepted after
        # owl.ontology_shifter has rewritten it — never verbatim.
        with self.assertRaises(ValueError):
            serialize_axioms([ConceptInclusion(A, UnionConcept((B, A)))], "http://ex")


class ReferencedPredicateNamesTest(unittest.TestCase):
    def test_names_of_every_referenced_concept_and_role(self):
        names = referenced_predicate_names(
            [ConceptInclusion(QualifiedExistentialConcept(R, A), B)]
        )

        self.assertEqual({"a", "b", "r", "thing", "nothing"}, names)

    def test_always_includes_thing_and_nothing(self):
        names = referenced_predicate_names([RoleInclusion(R, S)])

        self.assertIn("thing", names)
        self.assertIn("nothing", names)

    def test_cardinality_restriction_role_and_filler(self):
        names = referenced_predicate_names(
            [ConceptInclusion(A, MaxCardinalityConcept(R, 2, B))]
        )

        self.assertTrue({"a", "b", "r"} <= names)

    def test_functional_role(self):
        names = referenced_predicate_names([FunctionalRole(R)])

        self.assertIn("r", names)


if __name__ == "__main__":
    unittest.main()
