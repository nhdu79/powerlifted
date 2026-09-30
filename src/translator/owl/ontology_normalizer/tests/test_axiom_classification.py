"""
Regression tests for owl.ontology_normalizer.axiom_classification, run
against the Turtle ontologies under dev/ontologies/.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/owl/ontology_normalizer/tests/test_axiom_classification.py

from anywhere (the ontology paths and the `owl` package path are both
resolved relative to this file, not the current working directory).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent.parent
_REPO_ROOT = _TRANSLATOR_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl.axioms import (  # noqa: E402
    ConceptInclusion,
    FunctionalRole,
    InverseFunctionalRole,
    Ontology,
    RoleInclusion,
)
from owl.ontology_normalizer.axiom_classification import (  # noqa: E402
    O3,
    O8,
    O9,
    O10,
    O11,
    UNCLASSIFIED,
    classify_axiom,
    ensure_fully_supported,
)
from owl.expressions import (  # noqa: E402
    AtomicConcept,
    AtomicRole,
    InverseRole,
    NegatedRole,
    QualifiedExistentialConcept,
    RoleChain,
)
from owl.ontology_normalizer import normalize_ontology  # noqa: E402
from owl.parser import UnsupportedConstructError, parse_owl  # noqa: E402

ASSEMBLY_OWL = _REPO_ROOT / "dev" / "ontologies" / "assembly.owl"
TTL_OWL = _REPO_ROOT / "dev" / "ontologies" / "TTL.owl"


class ClassifyDisjointRoleTest(unittest.TestCase):
    """O9 (R ⊓ S ⊑ ⊥) is read directly off RoleInclusion(R, NegatedRole(S)),
    R and S atomic."""

    def test_role_inclusion_with_negated_atomic_role_is_o9(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        axiom = RoleInclusion(r, NegatedRole(s))
        self.assertEqual(classify_axiom(axiom), O9)

    def test_negated_inverse_role_is_unclassified(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        axiom = RoleInclusion(r, NegatedRole(InverseRole(s)))
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

    def test_inverse_sub_is_unclassified(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        axiom = RoleInclusion(InverseRole(r), NegatedRole(s))
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)


class ClassifyFunctionalRoleTest(unittest.TestCase):
    """O11 (⊤ ⊑ ≤1 P.⊤) is read directly off FunctionalRole(P), P atomic.
    InverseFunctionalRole means P⁻ is functional — not O11 as-is; it needs
    _normalize_inverse_functional_role first."""

    def test_functional_role_is_o11(self):
        p = AtomicRole("http://ex/P")
        self.assertEqual(classify_axiom(FunctionalRole(p)), O11)

    def test_inverse_functional_role_is_unclassified(self):
        p = AtomicRole("http://ex/P")
        self.assertEqual(classify_axiom(InverseFunctionalRole(p)), UNCLASSIFIED)


class ClassifyRoleChainLengthTest(unittest.TestCase):
    """O8 (R ∘ S ⊑ T) covers only a 2-role chain; a longer
    owl:propertyChainAxiom-style chain must not be classified O8."""

    def test_two_role_chain_is_o8(self):
        r, s, t = (
            AtomicRole("http://ex/R"),
            AtomicRole("http://ex/S"),
            AtomicRole("http://ex/T"),
        )
        axiom = RoleInclusion(RoleChain((r, s)), t)
        self.assertEqual(classify_axiom(axiom), O8)

    def test_two_role_chain_with_inverse_member_is_unclassified(self):
        r, s, t = (
            AtomicRole("http://ex/R"),
            AtomicRole("http://ex/S"),
            AtomicRole("http://ex/T"),
        )
        axiom = RoleInclusion(RoleChain((r, InverseRole(s))), t)
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

    def test_three_role_chain_is_unclassified(self):
        r1, r2, r3, s = (
            AtomicRole("http://ex/R1"),
            AtomicRole("http://ex/R2"),
            AtomicRole("http://ex/R3"),
            AtomicRole("http://ex/S"),
        )
        axiom = RoleInclusion(RoleChain((r1, r2, r3)), s)
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)


class EnsureFullySupportedTest(unittest.TestCase):
    """ensure_fully_supported is the sole point that raises for an
    unsupported ontology — normalize_ontology itself never does."""

    def test_fully_supported_ontology_does_not_raise(self):
        for path in (ASSEMBLY_OWL, TTL_OWL):
            ontology = parse_owl(str(path))
            normalize_ontology(ontology)
            ensure_fully_supported(ontology)  # must not raise

    def test_raises_on_warnings_even_with_no_unclassified_axioms(self):
        ontology = Ontology(iri="http://ex", warnings=["some skipped construct"])
        normalize_ontology(ontology)
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)

    def test_raises_on_unclassified_axiom_even_with_no_warnings(self):
        # ∃R.A ⊑ ∃S.B: an existential on both sides has no Table 1 row —
        # neither O3 (needs sup atomic) nor O10 (needs sub atomic) fits,
        # and nothing rewrites it (it isn't a conjunction/disjunction, an
        # inverse, or a cardinality restriction, so no pass touches it).
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(
                    QualifiedExistentialConcept(r, a),
                    QualifiedExistentialConcept(s, b),
                )
            ],
        )
        normalize_ontology(ontology)
        self.assertEqual(ontology.warnings, [])
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)


if __name__ == "__main__":
    unittest.main()
