"""
Regression tests for owl.ontology_normalizer (the orchestrator) and, in
turn, for its interaction with owl.parser — run against the Turtle
ontologies under dev/ontologies/ and inline Turtle fixtures.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/owl/ontology_normalizer/tests/test_ontology_normalizer.py

from anywhere (the ontology paths and the `owl` package path are both
resolved relative to this file, not the current working directory).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent.parent
_REPO_ROOT = _TRANSLATOR_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl.axioms import (  # noqa: E402
    ConceptInclusion,
    InverseFunctionalRole,
    Ontology,
    RoleInclusion,
)
from owl.ontology_normalizer.axiom_classification import (  # noqa: E402
    O1,
    O2,
    O3,
    O6,
    O7,
    O9,
    O10,
    O11,
    O13,
    O14,
    TABLE1_LABELS,
    UNCLASSIFIED,
    classify_axiom,
    ensure_fully_supported,
)
from owl.expressions import (  # noqa: E402
    OWL_NOTHING,
    AtomicConcept,
    AtomicRole,
    InverseMinCardinalityConcept,
    InverseQualifiedExistentialConcept,
    InverseRole,
    InverseUniversalConcept,
    MinCardinalityConcept,
    NegatedConcept,
    NegatedRole,
    QualifiedExistentialConcept,
    UniversalConcept,
)
from owl.ontology_normalizer.concept_normalization import (  # noqa: E402
    _normalize_negative_concept_inclusions,
    _normalize_universal_concept,
)
from owl.ontology_normalizer import (  # noqa: E402
    _deduplicate_axioms,
    normalize_ontology,
)
from owl.parser import UnsupportedConstructError, parse_owl  # noqa: E402

ASSEMBLY_OWL = _REPO_ROOT / "dev" / "ontologies" / "assembly.owl"
DRONES_OWL = _REPO_ROOT / "dev" / "ontologies" / "drones.owl"

FORALL_TTL = """
@prefix : <http://ex/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://ex> rdf:type owl:Ontology .
:P rdf:type owl:ObjectProperty .
:Q rdf:type owl:ObjectProperty .
:A rdf:type owl:Class .
:B rdf:type owl:Class ;
   rdfs:subClassOf [ rdf:type owl:Restriction ;
                      owl:onProperty :P ;
                      owl:allValuesFrom :A ] .
:C rdf:type owl:Class ;
   rdfs:subClassOf [ rdf:type owl:Restriction ;
                      owl:onProperty [ owl:inverseOf :Q ] ;
                      owl:allValuesFrom :A ] .
"""

PROPERTY_DISJOINT_TTL = """
@prefix : <http://ex/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

<http://ex> rdf:type owl:Ontology .
:R rdf:type owl:ObjectProperty .
:S rdf:type owl:ObjectProperty .
:R owl:propertyDisjointWith :S .
"""

INVERSE_OF_TTL = """
@prefix : <http://ex/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

<http://ex> rdf:type owl:Ontology .
:P rdf:type owl:ObjectProperty .
:Q rdf:type owl:ObjectProperty .
:P owl:inverseOf :Q .
"""

EQUIVALENT_CLASS_TTL = """
@prefix : <http://ex/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

<http://ex> rdf:type owl:Ontology .
:P rdf:type owl:ObjectProperty .
:A rdf:type owl:Class .
:B rdf:type owl:Class .
:C rdf:type owl:Class .
:A owl:equivalentClass :B .
[ rdf:type owl:Restriction ;
  owl:onProperty :P ;
  owl:someValuesFrom :A ] owl:equivalentClass :C .
"""

MIN_CARDINALITY_TTL = """
@prefix : <http://ex/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://ex> rdf:type owl:Ontology .
:P rdf:type owl:ObjectProperty .
:Q rdf:type owl:ObjectProperty .
:A rdf:type owl:Class .
:B rdf:type owl:Class ;
   rdfs:subClassOf [ rdf:type owl:Restriction ;
                      owl:onProperty :P ;
                      owl:minQualifiedCardinality "2"^^xsd:nonNegativeInteger ;
                      owl:onClass :A ] .
:C rdf:type owl:Class ;
   rdfs:subClassOf [ rdf:type owl:Restriction ;
                      owl:onProperty [ owl:inverseOf :Q ] ;
                      owl:minQualifiedCardinality "3"^^xsd:nonNegativeInteger ;
                      owl:onClass :A ] .
"""


class NormalizeAssemblyOntologyTest(unittest.TestCase):
    """assembly.owl has no disjointWith axioms, so negative-inclusion
    rewriting is a no-op on it. Its range axioms do parse as ∃R⁻.⊤ ⊑ B
    (InverseQualifiedExistentialConcept), so the full pipeline is not a
    no-op overall — see test_table1_classification."""

    def setUp(self):
        self.ontology = parse_owl(str(ASSEMBLY_OWL))

    def test_loads_without_warnings(self):
        self.assertEqual(self.ontology.warnings, [])

    def test_no_negated_superclass_axioms_present(self):
        for ax in self.ontology.axioms:
            if isinstance(ax, ConceptInclusion):
                self.assertNotIsInstance(ax.sup, NegatedConcept)

    def test_negative_concept_inclusion_rewrite_is_a_noop(self):
        before = list(self.ontology.axioms)
        _normalize_negative_concept_inclusions(self.ontology)
        self.assertEqual(before, self.ontology.axioms)

    def test_table1_classification(self):
        """subClassOf/general-intersection axioms (O2), domain axioms (O3),
        Functional/InverseFunctional roles (O11); range axioms parse as
        ∃R⁻.⊤ ⊑ B and are split into R ≡ R'⁻ (O7 x2) + ∃R'.⊤ ⊑ B (O3); the
        3 InverseFunctionalRole axioms are each split into P ≡ P'⁻ (O7 x2)
        + funct(P') (O11), so O7 also picks up those 3x2 defining axioms."""
        normalize_ontology(self.ontology)
        sizes = {label: len(axs) for label, axs in self.ontology.axiom_types.items()}
        self.assertEqual(sizes[O2], 7)
        self.assertEqual(sizes[O3], 6)
        self.assertEqual(sizes[O7], 12)
        self.assertEqual(sizes[O11], 12)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        for label in TABLE1_LABELS:
            if label not in (O2, O3, O7, O11):
                self.assertEqual(sizes[label], 0, label)
        self.assertEqual(len(self.ontology.axioms), 37)


class NormalizeTtlOntologyTest(unittest.TestCase):
    """drones.owl's disjointWith axioms (Drone/Human, Objectx/Rain) parse as
    ConceptInclusion(X, NegatedConcept(Y)); normalize_ontology rewrites them
    to ConceptInclusion(X ⊓ Y, ⊥)."""

    def setUp(self):
        self.ontology = parse_owl(str(DRONES_OWL))

    def test_loads_without_warnings(self):
        self.assertEqual(self.ontology.warnings, [])

    def test_disjointness_axioms_present_before_normalization(self):
        sup_ids = {
            ax.sup.id
            for ax in self.ontology.axioms
            if isinstance(ax, ConceptInclusion) and isinstance(ax.sup, NegatedConcept)
        }
        self.assertIn("not_human", sup_ids)
        self.assertIn("not_rain", sup_ids)

    def test_negative_concept_inclusions_rewritten(self):
        normalize_ontology(self.ontology)

        for ax in self.ontology.axioms:
            if isinstance(ax, ConceptInclusion):
                self.assertNotIsInstance(ax.sup, NegatedConcept)

        rewritten_ids = {
            ax.id
            for ax in self.ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sup is OWL_NOTHING
        }
        self.assertIn("drone_and_human_sub_nothing", rewritten_ids)
        self.assertIn("objectx_and_rain_sub_nothing", rewritten_ids)

    def test_rewritten_intersection_and_negation_registered_in_concepts(self):
        normalize_ontology(self.ontology)

        inter_ids = {
            ax.sub.id
            for ax in self.ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sup is OWL_NOTHING
        }
        self.assertTrue(inter_ids)
        for inter_id in inter_ids:
            self.assertIn(inter_id, self.ontology.concepts)
            self.assertIn(f"not_{inter_id}", self.ontology.concepts)

    def test_normalization_is_idempotent(self):
        normalize_ontology(self.ontology)
        once = list(self.ontology.axioms)
        normalize_ontology(self.ontology)
        self.assertEqual(once, self.ontology.axioms)

    def test_table1_classification(self):
        """Rewritten disjointness (O1), subClassOf (O2), subPropertyOf (O6),
        symmetric-property inclusions (O7), someValuesFrom (O10), and the 3
        general axioms (mixed atomic/existential conjuncts) split by LHS
        normalization into O2 + O3, plus each extracted existential
        conjunct's reverse direction (O10), fully classified."""
        normalize_ontology(self.ontology)
        sizes = {label: len(axs) for label, axs in self.ontology.axiom_types.items()}
        self.assertEqual(sizes[O1], 2)
        self.assertEqual(sizes[O2], 9)
        self.assertEqual(sizes[O3], 4)
        self.assertEqual(sizes[O6], 1)
        self.assertEqual(sizes[O7], 2)
        self.assertEqual(sizes[O10], 5)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        for label in TABLE1_LABELS:
            if label not in (O1, O2, O3, O6, O7, O10):
                self.assertEqual(sizes[label], 0, label)
        self.assertEqual(len(self.ontology.axioms), 23)


def _parse_ttl_string(ttl: str):
    """Write ttl to a temp .owl file, parse it, and clean up. Only usable
    inside a unittest.TestCase (uses self.addCleanup)."""
    def parse(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".owl", delete=False) as f:
            f.write(ttl)
            path = f.name
        self.addCleanup(Path(path).unlink)
        return parse_owl(path)

    return parse


class ParseForallConceptTest(unittest.TestCase):
    """owl:allValuesFrom (∀P.A / ∀P⁻.A) is fully supported by the parser:
    it resolves to UniversalConcept / InverseUniversalConcept with no
    warning, the same way owl:someValuesFrom resolves to
    (Inverse)QualifiedExistentialConcept. Table 1's O13 only covers the
    ⊤ ⊑ ∀R.A shape directly (see classify_axiom); B's axiom (B ⊑ ∀P.A, a
    named non-⊤ subject, direct role) is instead reached via
    _normalize_universal_concept's contrapositive and ends up O10. C's
    axiom (C ⊑ ∀Q⁻.A, an inverse role) isn't handled by that pass and
    stays UNCLASSIFIED."""

    parse = _parse_ttl_string(FORALL_TTL)

    def test_no_warnings(self):
        ontology = self.parse()
        self.assertEqual(ontology.warnings, [])
        self.assertTrue(ontology.is_supported)

    def test_direct_property_resolves_to_universal_concept(self):
        ontology = self.parse()
        b, a, p = (
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/A"),
            AtomicRole("http://ex/P"),
        )
        matches = [
            ax.sup
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sub == b
        ]
        self.assertEqual(matches, [UniversalConcept(p, a)])

    def test_inverse_property_resolves_to_inverse_universal_concept(self):
        ontology = self.parse()
        c, a, q = (
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/A"),
            AtomicRole("http://ex/Q"),
        )
        matches = [
            ax.sup
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sub == c
        ]
        self.assertEqual(matches, [InverseUniversalConcept(q, a)])

    def test_direct_form_reaches_o3_inverse_form_stays_unclassified(self):
        # B ⊑ ∀P.A (direct role) -> ∃P.A' ⊑ B' (O3), via
        # _normalize_universal_concept's contrapositive.
        ontology = self.parse()
        normalize_ontology(ontology)
        unclassified_subs = {
            ax.sub for ax in ontology.axiom_types[UNCLASSIFIED] if hasattr(ax, "sub")
        }
        self.assertNotIn(AtomicConcept("http://ex/B"), unclassified_subs)
        self.assertIn(AtomicConcept("http://ex/C"), unclassified_subs)
        b_comp = AtomicConcept("comp_b")
        p, a = AtomicRole("http://ex/P"), AtomicConcept("http://ex/A")
        a_comp = AtomicConcept("comp_a")
        self.assertIn(
            ConceptInclusion(QualifiedExistentialConcept(p, a_comp), b_comp),
            ontology.axiom_types[O3],
        )
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)


class ParsePropertyDisjointWithTest(unittest.TestCase):
    """owl:propertyDisjointWith is fully supported by the parser: it
    resolves to RoleInclusion(R, NegatedRole(S)), which classify_axiom
    reads directly as O9 (R ⊑ ¬S ≡ R ⊓ S ⊑ ⊥) — no rewriting needed."""

    parse = _parse_ttl_string(PROPERTY_DISJOINT_TTL)

    def test_no_warnings(self):
        ontology = self.parse()
        self.assertEqual(ontology.warnings, [])
        self.assertTrue(ontology.is_supported)

    def test_resolves_to_role_inclusion_with_negated_role(self):
        ontology = self.parse()
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        self.assertIn(RoleInclusion(r, NegatedRole(s)), ontology.axioms)

    def test_classified_as_o9(self):
        ontology = self.parse()
        normalize_ontology(ontology)
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        self.assertIn(RoleInclusion(r, NegatedRole(s)), ontology.axiom_types[O9])
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        ensure_fully_supported(ontology)  # does not raise


class ParseInverseOfTest(unittest.TestCase):
    """A direct owl:inverseOf axiom on a named property is fully supported
    by the parser: P owl:inverseOf Q becomes RoleInclusion(P, InverseRole(Q))
    and RoleInclusion(Q, InverseRole(P)), each directly O7 — no rewriting
    needed. The pre-existing blank-node-filler usage ([owl:inverseOf :P] as
    a role expression, e.g. inside rdfs:subPropertyOf) is untouched — see
    ParseForallConceptTest's FORALL_TTL for that usage still parsing
    without warnings."""

    parse = _parse_ttl_string(INVERSE_OF_TTL)

    def test_no_warnings(self):
        ontology = self.parse()
        self.assertEqual(ontology.warnings, [])
        self.assertTrue(ontology.is_supported)

    def test_resolves_to_role_inclusions_both_directions(self):
        ontology = self.parse()
        p, q = AtomicRole("http://ex/P"), AtomicRole("http://ex/Q")
        self.assertIn(RoleInclusion(p, InverseRole(q)), ontology.axioms)
        self.assertIn(RoleInclusion(q, InverseRole(p)), ontology.axioms)

    def test_classified_as_o7(self):
        ontology = self.parse()
        normalize_ontology(ontology)
        p, q = AtomicRole("http://ex/P"), AtomicRole("http://ex/Q")
        self.assertIn(RoleInclusion(p, InverseRole(q)), ontology.axiom_types[O7])
        self.assertIn(RoleInclusion(q, InverseRole(p)), ontology.axiom_types[O7])
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        ensure_fully_supported(ontology)  # does not raise


class ParseEquivalentClassTest(unittest.TestCase):
    """owl:equivalentClass is fully supported by the parser: A ≡ B becomes
    ConceptInclusion(A, B) + ConceptInclusion(B, A), for both a named-class
    subject and a blank-node (general-axiom) subject."""

    parse = _parse_ttl_string(EQUIVALENT_CLASS_TTL)

    def test_no_warnings(self):
        ontology = self.parse()
        self.assertEqual(ontology.warnings, [])
        self.assertTrue(ontology.is_supported)

    def test_named_class_resolves_to_both_directions(self):
        ontology = self.parse()
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        self.assertIn(ConceptInclusion(a, b), ontology.axioms)
        self.assertIn(ConceptInclusion(b, a), ontology.axioms)

    def test_general_axiom_resolves_to_both_directions(self):
        ontology = self.parse()
        p, a, c = (
            AtomicRole("http://ex/P"),
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/C"),
        )
        existential = QualifiedExistentialConcept(p, a)
        self.assertIn(ConceptInclusion(existential, c), ontology.axioms)
        self.assertIn(ConceptInclusion(c, existential), ontology.axioms)

    def test_classified_and_fully_supported(self):
        ontology = self.parse()
        normalize_ontology(ontology)
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        ensure_fully_supported(ontology)  # does not raise


class ParseMinCardinalityConceptTest(unittest.TestCase):
    """owl:minQualifiedCardinality (≥nP.A / ≥nP⁻.A) is fully supported by
    the parser: it resolves to MinCardinalityConcept /
    InverseMinCardinalityConcept with no warning, via the same
    _resolve_qualified_cardinality helper already used for
    owl:maxQualifiedCardinality. B's direct-property axiom (atomic sub,
    atomic role, atomic filler) fits O14 directly; C's inverse-property one
    is rewritten to O14 too by _normalize_inverse_role_concept, so the
    fully-normalized ontology is accepted by ensure_fully_supported."""

    parse = _parse_ttl_string(MIN_CARDINALITY_TTL)

    def test_no_warnings(self):
        ontology = self.parse()
        self.assertEqual(ontology.warnings, [])
        self.assertTrue(ontology.is_supported)

    def test_direct_property_resolves_to_min_cardinality_concept(self):
        ontology = self.parse()
        b, a, p = (
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/A"),
            AtomicRole("http://ex/P"),
        )
        matches = [
            ax.sup
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sub == b
        ]
        self.assertEqual(matches, [MinCardinalityConcept(p, 2, a)])

    def test_inverse_property_resolves_to_inverse_min_cardinality_concept(self):
        ontology = self.parse()
        c, a, q = (
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/A"),
            AtomicRole("http://ex/Q"),
        )
        matches = [
            ax.sup
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sub == c
        ]
        self.assertEqual(matches, [InverseMinCardinalityConcept(q, 3, a)])

    def test_both_direct_and_inverse_forms_normalize_to_o14(self):
        ontology = self.parse()
        normalize_ontology(ontology)
        o14_subs = {ax.sub for ax in ontology.axiom_types[O14]}
        self.assertIn(AtomicConcept("http://ex/B"), o14_subs)
        self.assertIn(AtomicConcept("http://ex/C"), o14_subs)
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        ensure_fully_supported(ontology)  # does not raise


class DeduplicateAxiomsTest(unittest.TestCase):
    """Direct tests of _deduplicate_axioms."""

    def test_duplicate_axioms_collapsed_keeping_first_occurrence(self):
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        first, second = ConceptInclusion(a, b), ConceptInclusion(a, b)
        ontology = Ontology(iri="http://ex", axioms=[first, second])

        _deduplicate_axioms(ontology)

        self.assertEqual(ontology.axioms, [first])

    def test_distinct_axioms_are_untouched(self):
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(a, b), ConceptInclusion(a, c)],
        )
        before = list(ontology.axioms)
        _deduplicate_axioms(ontology)
        self.assertEqual(before, ontology.axioms)


class ClassifyAxiomInvariantsTest(unittest.TestCase):
    """Structural invariants that must hold for any ontology, independent of
    which specific axioms it contains."""

    def _check(self, ontology_path):
        ontology = parse_owl(str(ontology_path))
        normalize_ontology(ontology)

        self.assertEqual(
            set(ontology.axiom_types.keys()), set(TABLE1_LABELS) | {UNCLASSIFIED}
        )

        # axiom_types is a strict partition of ontology.axioms.
        total = 0
        for label, axioms in ontology.axiom_types.items():
            for ax in axioms:
                self.assertEqual(classify_axiom(ax), label)
            total += len(axioms)
        self.assertEqual(total, len(ontology.axioms))

    def test_assembly_owl(self):
        self._check(ASSEMBLY_OWL)

    def test_drones_owl(self):
        self._check(DRONES_OWL)


if __name__ == "__main__":
    unittest.main()
