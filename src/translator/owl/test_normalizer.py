"""
Regression tests for owl.normalizer, run against the Turtle ontologies under
dev/ontologies/.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/owl/test_normalizer.py

from anywhere (the ontology paths and the `owl` package path are both
resolved relative to this file, not the current working directory).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent
_REPO_ROOT = _TRANSLATOR_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl.axioms import ConceptInclusion, Ontology, RoleInclusion  # noqa: E402
from owl.expressions import (  # noqa: E402
    OWL_NOTHING,
    AtomicConcept,
    AtomicRole,
    IntersectionConcept,
    InverseMaxCardinalityConcept,
    InverseQualifiedExistentialConcept,
    InverseRole,
    MaxCardinalityConcept,
    NegatedConcept,
    QualifiedExistentialConcept,
    RoleChain,
    UnionConcept,
)
from owl.ontology_normalizer import (  # noqa: E402
    O1,
    O2,
    O3,
    O6,
    O7,
    O8,
    O10,
    O11,
    TABLE1_LABELS,
    UNCLASSIFIED,
    _normalize_complex_concept_LHS,
    _normalize_complex_concept_RHS,
    _normalize_inverse_existential_concept,
    _normalize_inverse_max_cardinality_concept,
    _normalize_inverse_role_LHS,
    _normalize_negative_concept_inclusions,
    _normalize_role_chain_length,
    classify_axiom,
    ensure_fully_supported,
    normalize_ontology,
)
from owl.parser import UnsupportedConstructError, parse_owl  # noqa: E402

ASSEMBLY_OWL = _REPO_ROOT / "dev" / "ontologies" / "assembly.owl"
TTL_OWL = _REPO_ROOT / "dev" / "ontologies" / "TTL.owl"

FORALL_TTL = """
@prefix : <http://ex/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://ex> rdf:type owl:Ontology .
:P rdf:type owl:ObjectProperty .
:A rdf:type owl:Class .
:B rdf:type owl:Class ;
   rdfs:subClassOf [ rdf:type owl:Restriction ;
                      owl:onProperty :P ;
                      owl:allValuesFrom :A ] .
"""

MIN_CARDINALITY_TTL = """
@prefix : <http://ex/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://ex> rdf:type owl:Ontology .
:P rdf:type owl:ObjectProperty .
:A rdf:type owl:Class .
:B rdf:type owl:Class ;
   rdfs:subClassOf [ rdf:type owl:Restriction ;
                      owl:onProperty :P ;
                      owl:minQualifiedCardinality "2"^^xsd:nonNegativeInteger ;
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
        ∃R⁻.⊤ ⊑ B and are split into R ⊑ R'⁻ (O7) + ∃R'.⊤ ⊑ B (O3)."""
        normalize_ontology(self.ontology)
        sizes = {label: len(axs) for label, axs in self.ontology.axiom_types.items()}
        self.assertEqual(sizes[O2], 7)
        self.assertEqual(sizes[O3], 6)
        self.assertEqual(sizes[O7], 3)
        self.assertEqual(sizes[O11], 12)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        for label in TABLE1_LABELS:
            if label not in (O2, O3, O7, O11):
                self.assertEqual(sizes[label], 0, label)
        self.assertEqual(len(self.ontology.axioms), 28)


class NormalizeTtlOntologyTest(unittest.TestCase):
    """TTL.owl's disjointWith axioms (Drone/Human, Objectx/Rain) parse as
    ConceptInclusion(X, NegatedConcept(Y)); normalize_ontology rewrites them
    to ConceptInclusion(X ⊓ Y, ⊥)."""

    def setUp(self):
        self.ontology = parse_owl(str(TTL_OWL))

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
        normalization into O2 + O3, fully classified."""
        normalize_ontology(self.ontology)
        sizes = {label: len(axs) for label, axs in self.ontology.axiom_types.items()}
        self.assertEqual(sizes[O1], 2)
        self.assertEqual(sizes[O2], 9)
        self.assertEqual(sizes[O3], 4)
        self.assertEqual(sizes[O6], 1)
        self.assertEqual(sizes[O7], 2)
        self.assertEqual(sizes[O10], 1)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        for label in TABLE1_LABELS:
            if label not in (O1, O2, O3, O6, O7, O10):
                self.assertEqual(sizes[label], 0, label)
        self.assertEqual(len(self.ontology.axioms), 19)


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
    """owl:allValuesFrom (∀P.A) is not yet supported; parsing warns and
    skips it (like any other unsupported construct) rather than raising —
    ensure_fully_supported is what rejects the resulting ontology."""

    parse = _parse_ttl_string(FORALL_TTL)

    def test_warns_and_is_unsupported(self):
        ontology = self.parse()
        self.assertTrue(ontology.warnings)
        self.assertFalse(ontology.is_supported)

    def test_rejected_by_ensure_fully_supported(self):
        ontology = self.parse()
        normalize_ontology(ontology)
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)


class ParseMinCardinalityConceptTest(unittest.TestCase):
    """owl:minQualifiedCardinality (≥nP.A) is not yet supported; parsing
    warns and skips it rather than raising — ensure_fully_supported is what
    rejects the resulting ontology."""

    parse = _parse_ttl_string(MIN_CARDINALITY_TTL)

    def test_warns_and_is_unsupported(self):
        ontology = self.parse()
        self.assertTrue(ontology.warnings)
        self.assertFalse(ontology.is_supported)

    def test_rejected_by_ensure_fully_supported(self):
        ontology = self.parse()
        normalize_ontology(ontology)
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)


class NormalizeComplexConceptLHSTest(unittest.TestCase):
    """Direct tests of _normalize_complex_concept_LHS, against TTL.owl's
    3 general axioms (Drone conjoined with one or two existentials)."""

    def setUp(self):
        self.ontology = parse_owl(str(TTL_OWL))

    def test_complex_conjuncts_get_fresh_defining_axioms(self):
        axiom_count_before = len(self.ontology.axioms)

        _normalize_complex_concept_LHS(self.ontology)

        # One defining axiom per distinct existential conjunct (4 total).
        self.assertEqual(len(self.ontology.axioms), axiom_count_before + 4)

        defining = {
            ax.sub.id: ax.sup
            for ax in self.ontology.axioms
            if isinstance(ax, ConceptInclusion)
            and ax.sub.id
            in (
                "existsnear_dot_objectx",
                "existsenvironment_dot_lowvisibility",
                "existsnear_dot_movingobject",
                "existsveryclose_dot_objectx",
            )
        }
        self.assertEqual(len(defining), 4)
        for conjunct_id, fresh in defining.items():
            self.assertIsInstance(fresh, AtomicConcept)
            self.assertEqual(fresh, AtomicConcept(f"def_{conjunct_id}"))
            self.assertIn(fresh.id, self.ontology.concepts)
            self.assertIn(f"not_{fresh.id}", self.ontology.concepts)

    def test_general_axioms_rewritten_to_atomic_conjunctions(self):
        _normalize_complex_concept_LHS(self.ontology)

        rewritten = [
            ax
            for ax in self.ontology.axioms
            if isinstance(ax, ConceptInclusion)
            and isinstance(ax.sub, IntersectionConcept)
            and ax.sup.id == "riskofphysicaldamage"
        ]
        self.assertEqual(len(rewritten), 3)
        for ax in rewritten:
            for conjunct in ax.sub.operands:
                self.assertIsInstance(conjunct, AtomicConcept)

    def test_axioms_without_complex_conjuncts_are_untouched(self):
        assembly = parse_owl(str(ASSEMBLY_OWL))
        before = list(assembly.axioms)
        _normalize_complex_concept_LHS(assembly)
        self.assertEqual(before, assembly.axioms)

    def test_idempotent(self):
        _normalize_complex_concept_LHS(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_complex_concept_LHS(self.ontology)
        self.assertEqual(once, self.ontology.axioms)


class NormalizeComplexConceptRHSTest(unittest.TestCase):
    """Direct tests of _normalize_complex_concept_RHS. Built in-memory
    since neither dev/ontologies file uses owl:unionOf."""

    def setUp(self):
        # A ⊑ B ⊔ ∃R.C
        role = AtomicRole("http://ex/R")
        self.a, self.b, self.c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        self.exists_r_c = QualifiedExistentialConcept(role, self.c)
        self.axiom = ConceptInclusion(self.a, UnionConcept((self.b, self.exists_r_c)))
        self.ontology = Ontology(iri="http://ex", axioms=[self.axiom])

    def test_complex_disjunct_gets_fresh_defining_axiom(self):
        axiom_count_before = len(self.ontology.axioms)

        _normalize_complex_concept_RHS(self.ontology)

        self.assertEqual(len(self.ontology.axioms), axiom_count_before + 1)
        fresh = AtomicConcept(f"def_{self.exists_r_c.id}")
        self.assertIn(ConceptInclusion(fresh, self.exists_r_c), self.ontology.axioms)
        self.assertIn(fresh.id, self.ontology.concepts)
        self.assertIn(f"not_{fresh.id}", self.ontology.concepts)

    def test_axiom_rewritten_to_atomic_disjunction(self):
        _normalize_complex_concept_RHS(self.ontology)

        rewritten = [
            ax
            for ax in self.ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sub == self.a
        ]
        self.assertEqual(len(rewritten), 1)
        self.assertIsInstance(rewritten[0].sup, UnionConcept)
        for disjunct in rewritten[0].sup.operands:
            self.assertIsInstance(disjunct, AtomicConcept)

    def test_classification_before_and_after(self):
        self.assertEqual(classify_axiom(self.axiom), UNCLASSIFIED)

        _normalize_complex_concept_RHS(self.ontology)

        # A' ⊑ ∃R.C  (O10),  A ⊑ B ⊔ A'  (O2)
        labels = [classify_axiom(ax) for ax in self.ontology.axioms]
        self.assertCountEqual(labels, [O10, O2])

    def test_axioms_without_complex_disjuncts_are_untouched(self):
        plain = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(self.a, UnionConcept((self.b, self.c)))],
        )
        before = list(plain.axioms)
        _normalize_complex_concept_RHS(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        _normalize_complex_concept_RHS(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_complex_concept_RHS(self.ontology)
        self.assertEqual(once, self.ontology.axioms)

    def test_compound_disjunct_stays_unclassified(self):
        """A disjunct that is itself compound (e.g. a nested conjunction)
        rewrites to A' ⊑ (∃R.C ⊓ D) — "atomic ⊑ conjunction" has no Table 1
        row, so this stays UNCLASSIFIED; no other pass distributes it."""
        d = AtomicConcept("http://ex/D")
        nested = IntersectionConcept((self.exists_r_c, d))
        ontology = Ontology(
            iri="http://ex", axioms=[ConceptInclusion(self.a, UnionConcept((self.b, nested)))]
        )
        normalize_ontology(ontology)
        self.assertEqual(len(ontology.axiom_types[UNCLASSIFIED]), 1)


class NormalizeComplexConceptsFixpointTest(unittest.TestCase):
    """A defining axiom's own subject can itself be a nested
    conjunction/disjunction, requiring another LHS/RHS pass —
    normalize_ontology's fixpoint loop handles this. Built in-memory since
    neither dev/ontologies file has nested owl:intersectionOf/unionOf."""

    def test_lhs_only_nesting_resolved_by_fixpoint(self):
        # (∃R.B ⊓ C) ⊓ D ⊑ E
        role = AtomicRole("http://ex/R")
        b, c, d, e = (
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/D"),
            AtomicConcept("http://ex/E"),
        )
        exists_r_b = QualifiedExistentialConcept(role, b)
        inner = IntersectionConcept((exists_r_b, c))
        outer = IntersectionConcept((inner, d))
        ontology = Ontology(iri="http://ex", axioms=[ConceptInclusion(outer, e)])

        _normalize_complex_concept_LHS(ontology)
        labels = {classify_axiom(ax) for ax in ontology.axioms}
        self.assertIn(UNCLASSIFIED, labels)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        # ∃R.B ⊑ A_x  (O3),  A_x ⊓ C ⊑ A_y  (O2),  A_y ⊓ D ⊑ E  (O2)
        self.assertEqual(sizes[O3], 1)
        self.assertEqual(sizes[O2], 2)

    def test_rhs_only_nesting_resolved_by_fixpoint(self):
        # A ⊑ B ⊔ (X ⊔ ∃R.C) — mirrors the LHS case above, on the RHS.
        role = AtomicRole("http://ex/R")
        a, b, x, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/X"),
            AtomicConcept("http://ex/C"),
        )
        exists_r_c = QualifiedExistentialConcept(role, c)
        inner = UnionConcept((x, exists_r_c))
        outer = UnionConcept((b, inner))
        ontology = Ontology(iri="http://ex", axioms=[ConceptInclusion(a, outer)])

        _normalize_complex_concept_RHS(ontology)
        labels = {classify_axiom(ax) for ax in ontology.axioms}
        self.assertIn(UNCLASSIFIED, labels)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        # A_x ⊑ ∃R.C  (O10),  A_y ⊑ X ⊔ A_x  (O2),  A ⊑ B ⊔ A_y  (O2)
        self.assertEqual(sizes[O10], 1)
        self.assertEqual(sizes[O2], 2)

    def test_lhs_flattening_surfaces_inverse_existential_resolved_by_fixpoint(self):
        # ∃R⁻.A ⊓ C ⊑ D — LHS flattening turns the complex conjunct ∃R⁻.A
        # into its own defining axiom ∃R⁻.A ⊑ A_x, which then needs
        # _normalize_inverse_existential_concept too.
        role = AtomicRole("http://ex/R")
        a, c, d = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/D"),
        )
        inv_ex = InverseQualifiedExistentialConcept(role, a)
        ontology = Ontology(
            iri="http://ex", axioms=[ConceptInclusion(IntersectionConcept((inv_ex, c)), d)]
        )

        _normalize_complex_concept_LHS(ontology)
        labels = {classify_axiom(ax) for ax in ontology.axioms}
        self.assertIn(UNCLASSIFIED, labels)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        # R ⊑ R'⁻  (O7),  ∃R'.A ⊑ A_x  (O3),  A_x ⊓ C ⊑ D  (O2)
        self.assertEqual(sizes[O7], 1)
        self.assertEqual(sizes[O3], 1)
        self.assertEqual(sizes[O2], 1)


class NormalizeInverseExistentialConceptTest(unittest.TestCase):
    """Direct tests of _normalize_inverse_existential_concept."""

    def test_inverse_existential_sub_rewritten_to_o7_plus_o3(self):
        # ∃R⁻.A ⊑ B  ->  R ⊑ R'⁻ (O7)  +  ∃R'.A ⊑ B (O3)
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(InverseQualifiedExistentialConcept(role, a), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_inverse_existential_concept(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(role).id}")
        self.assertIn(RoleInclusion(role, InverseRole(fresh)), ontology.axioms)
        self.assertIn(
            ConceptInclusion(QualifiedExistentialConcept(fresh, a), b), ontology.axioms
        )
        for ax in ontology.axioms:
            self.assertNotEqual(classify_axiom(ax), UNCLASSIFIED)
        self.assertIn(fresh.id, ontology.roles)
        self.assertIn(f"not_{fresh.id}", ontology.roles)

    def test_inverse_existential_sup_rewritten_to_o7_plus_o10(self):
        # A ⊑ ∃R⁻.B  ->  R' ⊑ R⁻ (O7)  +  A ⊑ ∃R'.B (O10)
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(a, InverseQualifiedExistentialConcept(role, b))
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_inverse_existential_concept(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(role).id}")
        self.assertIn(RoleInclusion(fresh, InverseRole(role)), ontology.axioms)
        self.assertIn(
            ConceptInclusion(a, QualifiedExistentialConcept(fresh, b)), ontology.axioms
        )
        for ax in ontology.axioms:
            self.assertNotEqual(classify_axiom(ax), UNCLASSIFIED)

    def test_same_role_shared_across_both_positions(self):
        # ∃R⁻.A ⊑ B  and  C ⊑ ∃R⁻.D  in the same ontology must reuse R'.
        role = AtomicRole("http://ex/R")
        a, b, c, d = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/D"),
        )
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(InverseQualifiedExistentialConcept(role, a), b),
                ConceptInclusion(c, InverseQualifiedExistentialConcept(role, d)),
            ],
        )

        _normalize_inverse_existential_concept(ontology)

        # R ⊑ fresh⁻ (from the sub-position axiom) and fresh ⊑ R⁻ (from the
        # sup-position one) must name the identical fresh role.
        role_axioms = [ax for ax in ontology.axioms if isinstance(ax, RoleInclusion)]
        self.assertEqual(len(role_axioms), 2)
        fresh_from_sub_case = next(ax.sup.role for ax in role_axioms if ax.sub == role)
        fresh_from_sup_case = next(ax.sub for ax in role_axioms if ax.sub != role)
        self.assertEqual(fresh_from_sub_case, fresh_from_sup_case)

    def test_axioms_without_inverse_existential_are_untouched(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        plain = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(QualifiedExistentialConcept(role, a), b)],
        )
        before = list(plain.axioms)
        _normalize_inverse_existential_concept(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(InverseQualifiedExistentialConcept(role, a), b)],
        )
        _normalize_inverse_existential_concept(ontology)
        once = list(ontology.axioms)
        _normalize_inverse_existential_concept(ontology)
        self.assertEqual(once, ontology.axioms)


class NormalizeInverseMaxCardinalityConceptTest(unittest.TestCase):
    """Direct tests of _normalize_inverse_max_cardinality_concept. Unlike
    the existential case, ≤n is anti-monotone in the role, so the defining
    axiom direction is R ⊑ R'⁻ (matching the existential's *sub*-position
    case), not R' ⊑ R⁻ (its sup-position case) — despite ≤nR⁻.X only ever
    appearing in the sup position here."""

    def test_inverse_max_cardinality_rewritten_to_o7_plus_o11(self):
        # A ⊑ ≤2R⁻.B  ->  R ⊑ R'⁻ (O7)  +  A ⊑ ≤2R'.B (O11)
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(a, InverseMaxCardinalityConcept(role, 2, b))
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_inverse_max_cardinality_concept(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(role).id}")
        self.assertIn(RoleInclusion(role, InverseRole(fresh)), ontology.axioms)
        self.assertIn(
            ConceptInclusion(a, MaxCardinalityConcept(fresh, 2, b)), ontology.axioms
        )
        for ax in ontology.axioms:
            self.assertNotEqual(classify_axiom(ax), UNCLASSIFIED)
        self.assertIn(fresh.id, ontology.roles)
        self.assertIn(f"not_{fresh.id}", ontology.roles)

    def test_shares_fresh_role_with_inverse_existential_concept(self):
        # ∃R⁻.A ⊑ B  and  C ⊑ ≤2R⁻.D  in the same ontology must reuse R'.
        role = AtomicRole("http://ex/R")
        a, b, c, d = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/D"),
        )
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(InverseQualifiedExistentialConcept(role, a), b),
                ConceptInclusion(c, InverseMaxCardinalityConcept(role, 2, d)),
            ],
        )

        _normalize_inverse_existential_concept(ontology)
        _normalize_inverse_max_cardinality_concept(ontology)

        role_axioms = [ax for ax in ontology.axioms if isinstance(ax, RoleInclusion)]
        self.assertEqual(len(role_axioms), 1)  # both need R ⊑ R'⁻ — deduped

    def test_axioms_without_inverse_max_cardinality_are_untouched(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        plain = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(a, MaxCardinalityConcept(role, 2, b))],
        )
        before = list(plain.axioms)
        _normalize_inverse_max_cardinality_concept(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(a, InverseMaxCardinalityConcept(role, 2, b))],
        )
        _normalize_inverse_max_cardinality_concept(ontology)
        once = list(ontology.axioms)
        _normalize_inverse_max_cardinality_concept(ontology)
        self.assertEqual(once, ontology.axioms)


class RejectCardinalityConceptLHSTest(unittest.TestCase):
    """≤nR.B (or ≤nR⁻.B) as a ConceptInclusion's sub has no Table 1 row and
    is not Horn-normalizable. normalize_ontology leaves it UNCLASSIFIED like
    any other unsupported shape; ensure_fully_supported is what rejects it."""

    def test_direct_cardinality_lhs_is_unclassified_then_rejected(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(MaxCardinalityConcept(role, 2, b), a)],
        )
        normalize_ontology(ontology)
        self.assertEqual(len(ontology.axiom_types[UNCLASSIFIED]), 1)
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)

    def test_cardinality_surfaced_by_lhs_flattening_is_unclassified_then_rejected(self):
        # ≤2R.B ⊓ C ⊑ D — flattening extracts ≤2R.B into its own defining
        # axiom ≤2R.B ⊑ A_x, which must also end up UNCLASSIFIED.
        role = AtomicRole("http://ex/R")
        b, c, d = (
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/D"),
        )
        cardinality = MaxCardinalityConcept(role, 2, b)
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(IntersectionConcept((cardinality, c)), d)],
        )
        normalize_ontology(ontology)
        self.assertEqual(len(ontology.axiom_types[UNCLASSIFIED]), 1)
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)


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


class NormalizeRoleChainLengthTest(unittest.TestCase):
    """Direct tests of _normalize_role_chain_length in isolation, on an
    already-atomic chain R1 ∘ R2 ∘ R3 ⊑ S (inverse-role elimination is
    _normalize_inverse_role_LHS's job, tested separately below)."""

    def setUp(self):
        self.r1, self.r2, self.r3, self.s = (
            AtomicRole("http://ex/R1"),
            AtomicRole("http://ex/R2"),
            AtomicRole("http://ex/R3"),
            AtomicRole("http://ex/S"),
        )
        self.chain = RoleChain((self.r1, self.r2, self.r3))
        self.axiom = RoleInclusion(self.chain, self.s)
        self.ontology = Ontology(iri="http://ex", axioms=[self.axiom])

    def test_binarized_into_two_o8_axioms(self):
        _normalize_role_chain_length(self.ontology)

        self.assertEqual(len(self.ontology.axioms), 2)
        for ax in self.ontology.axioms:
            self.assertIsInstance(ax, RoleInclusion)
            self.assertIsInstance(ax.sub, RoleChain)
            self.assertEqual(len(ax.sub.roles), 2)
            self.assertEqual(classify_axiom(ax), O8)

        # The final axiom's target is the original super-role S.
        final = [ax for ax in self.ontology.axioms if ax.sup == self.s]
        self.assertEqual(len(final), 1)
        # The fresh intermediate role is registered, alongside its negation.
        fresh = final[0].sub.roles[0]
        self.assertIsInstance(fresh, AtomicRole)
        self.assertIn(fresh.id, self.ontology.roles)
        self.assertIn(f"not_{fresh.id}", self.ontology.roles)

    def test_two_role_chains_are_untouched(self):
        plain = Ontology(
            iri="http://ex",
            axioms=[RoleInclusion(RoleChain((self.r1, self.r2)), self.s)],
        )
        before = list(plain.axioms)
        _normalize_role_chain_length(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        _normalize_role_chain_length(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_role_chain_length(self.ontology)
        self.assertEqual(once, self.ontology.axioms)

    def test_normalize_ontology_fully_classifies(self):
        normalize_ontology(self.ontology)
        sizes = {label: len(axs) for label, axs in self.ontology.axiom_types.items()}
        self.assertEqual(sizes[O8], 2)
        self.assertEqual(sizes[UNCLASSIFIED], 0)


class NormalizeInverseRoleLHSTest(unittest.TestCase):
    """Direct tests of _normalize_inverse_role_LHS in isolation."""

    def test_bare_inverse_sub_rewritten_to_o7_defining_axiom(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        ontology = Ontology(
            iri="http://ex", axioms=[RoleInclusion(InverseRole(r), s)]
        )

        _normalize_inverse_role_LHS(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(r).id}")
        self.assertIn(RoleInclusion(r, InverseRole(fresh)), ontology.axioms)
        self.assertIn(RoleInclusion(fresh, s), ontology.axioms)
        for ax in ontology.axioms:
            self.assertEqual(classify_axiom(ax), O7 if ax.sub == r else O6)
        self.assertIn(fresh.id, ontology.roles)
        self.assertIn(f"not_{fresh.id}", ontology.roles)

    def test_chain_member_inverse_rewritten(self):
        r1, r2, r3, s = (
            AtomicRole("http://ex/R1"),
            AtomicRole("http://ex/R2"),
            AtomicRole("http://ex/R3"),
            AtomicRole("http://ex/S"),
        )
        ontology = Ontology(
            iri="http://ex",
            axioms=[RoleInclusion(RoleChain((r1, InverseRole(r2), r3)), s)],
        )

        _normalize_inverse_role_LHS(ontology)

        rewritten = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, RoleInclusion) and isinstance(ax.sub, RoleChain)
        ]
        self.assertEqual(len(rewritten), 1)
        for member in rewritten[0].sub.roles:
            self.assertIsInstance(member, AtomicRole)

    def test_axioms_without_inverse_lhs_are_untouched(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        plain = Ontology(iri="http://ex", axioms=[RoleInclusion(r, InverseRole(s))])
        before = list(plain.axioms)
        _normalize_inverse_role_LHS(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        ontology = Ontology(
            iri="http://ex", axioms=[RoleInclusion(InverseRole(r), s)]
        )
        _normalize_inverse_role_LHS(ontology)
        once = list(ontology.axioms)
        _normalize_inverse_role_LHS(ontology)
        self.assertEqual(once, ontology.axioms)


class NormalizeRoleAxiomIntegrationTest(unittest.TestCase):
    """R1 ∘ R2⁻ ∘ R3 ⊑ S needs both new passes together: inverse-role
    elimination, then chain-length binarization."""

    def test_normalize_ontology_fully_classifies(self):
        r1, r2, r3, s = (
            AtomicRole("http://ex/R1"),
            AtomicRole("http://ex/R2"),
            AtomicRole("http://ex/R3"),
            AtomicRole("http://ex/S"),
        )
        chain = RoleChain((r1, InverseRole(r2), r3))
        ontology = Ontology(iri="http://ex", axioms=[RoleInclusion(chain, s)])

        self.assertEqual(classify_axiom(ontology.axioms[0]), UNCLASSIFIED)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        # R2 ⊑ A_x⁻  (O7),  R1∘A_x ⊑ A_y  (O8),  A_y∘R3 ⊑ S  (O8)
        self.assertEqual(sizes[O7], 1)
        self.assertEqual(sizes[O8], 2)
        self.assertEqual(sizes[UNCLASSIFIED], 0)


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
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(MaxCardinalityConcept(role, 2, b), a)],
        )
        normalize_ontology(ontology)
        self.assertEqual(ontology.warnings, [])
        with self.assertRaises(UnsupportedConstructError):
            ensure_fully_supported(ontology)


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

    def test_ttl_owl(self):
        self._check(TTL_OWL)


if __name__ == "__main__":
    unittest.main()
