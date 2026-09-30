"""
Regression tests for owl.ontology_normalizer.concept_normalization, run
against the Turtle ontologies under dev/ontologies/.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/owl/ontology_normalizer/tests/test_concept_normalization.py

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

from owl.axioms import ConceptInclusion, Ontology, RoleInclusion  # noqa: E402
from owl.ontology_normalizer.axiom_classification import (  # noqa: E402
    O1,
    O2,
    O3,
    O7,
    O10,
    O11,
    O13,
    O14,
    UNCLASSIFIED,
    classify_axiom,
    ensure_fully_supported,
)
from owl.expressions import (  # noqa: E402
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    AtomicRole,
    IntersectionConcept,
    InverseMaxCardinalityConcept,
    InverseMinCardinalityConcept,
    InverseQualifiedExistentialConcept,
    InverseRole,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    MinCardinalityConcept,
    QualifiedExistentialConcept,
    UnionConcept,
    UniversalConcept,
)
from owl.ontology_normalizer.concept_normalization import (  # noqa: E402
    _normalize_intersection_sub,
    _normalize_intersection_sup,
    _normalize_inverse_role_concept,
    _normalize_max_cardinality_LHS,
    _normalize_min_cardinality_LHS,
    _normalize_restriction_concept_filler,
    _normalize_union_sub,
    _normalize_union_sup,
    _normalize_universal_concept,
)
from owl.ontology_normalizer import normalize_ontology  # noqa: E402
from owl.parser import parse_owl  # noqa: E402

ASSEMBLY_OWL = _REPO_ROOT / "dev" / "ontologies" / "assembly.owl"
TTL_OWL = _REPO_ROOT / "dev" / "ontologies" / "TTL.owl"


class NormalizeIntersectionSubTest(unittest.TestCase):
    """Direct tests of _normalize_intersection_sub, against TTL.owl's
    3 general axioms (Drone conjoined with one or two existentials)."""

    def setUp(self):
        self.ontology = parse_owl(str(TTL_OWL))

    def test_complex_conjuncts_get_fresh_defining_axioms(self):
        axiom_count_before = len(self.ontology.axioms)

        _normalize_intersection_sub(self.ontology)

        # Two defining axioms (both ⊑ directions) per distinct existential
        # conjunct (4 distinct conjuncts, 8 defining axioms total).
        self.assertEqual(len(self.ontology.axioms), axiom_count_before + 8)

        defining = {
            ax.sub.id: ax.sup
            for ax in self.ontology.axioms
            if isinstance(ax, ConceptInclusion)
            and ax.sub.id
            in (
                "exists_near_dot_objectx",
                "exists_environment_dot_lowvisibility",
                "exists_near_dot_movingobject",
                "exists_veryclose_dot_objectx",
            )
        }
        self.assertEqual(len(defining), 4)
        for conjunct_id, fresh in defining.items():
            self.assertIsInstance(fresh, AtomicConcept)
            self.assertEqual(fresh, AtomicConcept(f"def_{conjunct_id}"))
            self.assertIn(fresh.id, self.ontology.concepts)
            self.assertIn(f"not_{fresh.id}", self.ontology.concepts)

    def test_general_axioms_rewritten_to_atomic_conjunctions(self):
        _normalize_intersection_sub(self.ontology)

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
        _normalize_intersection_sub(assembly)
        self.assertEqual(before, assembly.axioms)

    def test_idempotent(self):
        _normalize_intersection_sub(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_intersection_sub(self.ontology)
        self.assertEqual(once, self.ontology.axioms)


class NormalizeUnionSupTest(unittest.TestCase):
    """Direct tests of _normalize_union_sup. Built in-memory
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

        _normalize_union_sup(self.ontology)

        self.assertEqual(len(self.ontology.axioms), axiom_count_before + 2)
        fresh = AtomicConcept(f"def_{self.exists_r_c.id}")
        self.assertIn(ConceptInclusion(fresh, self.exists_r_c), self.ontology.axioms)
        self.assertIn(ConceptInclusion(self.exists_r_c, fresh), self.ontology.axioms)
        self.assertIn(fresh.id, self.ontology.concepts)
        self.assertIn(f"not_{fresh.id}", self.ontology.concepts)

    def test_axiom_rewritten_to_atomic_disjunction(self):
        _normalize_union_sup(self.ontology)

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

        _normalize_union_sup(self.ontology)

        # A' ⊑ ∃R.C  (O10),  ∃R.C ⊑ A'  (O3),  A ⊑ B ⊔ A'  (O2)
        labels = [classify_axiom(ax) for ax in self.ontology.axioms]
        self.assertCountEqual(labels, [O10, O3, O2])

    def test_axioms_without_complex_disjuncts_are_untouched(self):
        plain = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(self.a, UnionConcept((self.b, self.c)))],
        )
        before = list(plain.axioms)
        _normalize_union_sup(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        _normalize_union_sup(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_union_sup(self.ontology)
        self.assertEqual(once, self.ontology.axioms)

    def test_compound_disjunct_is_fully_classified_by_fixpoint(self):
        """A disjunct that is itself compound (e.g. a nested conjunction)
        rewrites to A' ⊑ (∃R.C ⊓ D) — "atomic ⊑ conjunction" has no Table 1
        row on its own, but _normalize_intersection_sup then splits it into
        A' ⊑ ∃R.C, A' ⊑ D."""
        d = AtomicConcept("http://ex/D")
        nested = IntersectionConcept((self.exists_r_c, d))
        ontology = Ontology(
            iri="http://ex", axioms=[ConceptInclusion(self.a, UnionConcept((self.b, nested)))]
        )
        normalize_ontology(ontology)
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        fresh = AtomicConcept(f"def_{nested.id}")
        self.assertIn(ConceptInclusion(fresh, self.exists_r_c), ontology.axioms)
        self.assertIn(ConceptInclusion(fresh, d), ontology.axioms)


class NormalizeIntersectionSupTest(unittest.TestCase):
    """Direct tests of _normalize_intersection_sup: C ⊑ C1 ⊓ … ⊓ Cn (n>=2,
    no Table 1 row for a conjunction on the sup side at all, regardless of
    whether the Ci are atomic) is split into C ⊑ C1, …, C ⊑ Cn — an exact
    equivalence, no fresh concept needed."""

    def setUp(self):
        # C ⊑ C1 ⊓ C2
        self.c, self.c1, self.c2 = (
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/C1"),
            AtomicConcept("http://ex/C2"),
        )
        self.intersection = IntersectionConcept((self.c1, self.c2))
        self.axiom = ConceptInclusion(self.c, self.intersection)
        self.ontology = Ontology(iri="http://ex", axioms=[self.axiom])

    def test_split_into_per_conjunct_axioms(self):
        self.assertEqual(classify_axiom(self.axiom), UNCLASSIFIED)

        _normalize_intersection_sup(self.ontology)

        self.assertIn(ConceptInclusion(self.c, self.c1), self.ontology.axioms)
        self.assertIn(ConceptInclusion(self.c, self.c2), self.ontology.axioms)
        self.assertNotIn(self.axiom, self.ontology.axioms)
        self.assertEqual(len(self.ontology.axioms), 2)
        for ax in self.ontology.axioms:
            self.assertEqual(classify_axiom(ax), O2)

    def test_duplicate_split_result_deduplicated_by_fixpoint(self):
        # C ⊑ C1 ⊓ C2 and a pre-existing C ⊑ C1 both produce C ⊑ C1 —
        # normalize_ontology's closing dedup must collapse them to one.
        ontology = Ontology(
            iri="http://ex", axioms=[self.axiom, ConceptInclusion(self.c, self.c1)]
        )
        normalize_ontology(ontology)
        matches = [
            ax for ax in ontology.axioms if ax == ConceptInclusion(self.c, self.c1)
        ]
        self.assertEqual(len(matches), 1)

    def test_nested_intersection_resolved_by_fixpoint(self):
        # C ⊑ (C1 ⊓ C2) ⊓ C3 — one split leaves C ⊑ (C1 ⊓ C2), needing a
        # second pass, handled by normalize_ontology's fixpoint.
        c3 = AtomicConcept("http://ex/C3")
        nested = IntersectionConcept((self.intersection, c3))
        ontology = Ontology(iri="http://ex", axioms=[ConceptInclusion(self.c, nested)])

        normalize_ontology(ontology)

        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        self.assertIn(ConceptInclusion(self.c, self.c1), ontology.axioms)
        self.assertIn(ConceptInclusion(self.c, self.c2), ontology.axioms)
        self.assertIn(ConceptInclusion(self.c, c3), ontology.axioms)

    def test_axioms_without_intersection_sup_are_untouched(self):
        plain = Ontology(
            iri="http://ex", axioms=[ConceptInclusion(self.c, self.c1)]
        )
        before = list(plain.axioms)
        _normalize_intersection_sup(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        _normalize_intersection_sup(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_intersection_sup(self.ontology)
        self.assertEqual(once, self.ontology.axioms)


class NormalizeUnionSubTest(unittest.TestCase):
    """Direct tests of _normalize_union_sub: C1 ⊔ … ⊔ Cn ⊑ C (n>=2, no
    Table 1 row for a disjunction on the sub side at all, regardless of
    whether the Ci are atomic) is split into C1 ⊑ C, …, Cn ⊑ C — an exact
    equivalence, no fresh concept or negation needed."""

    def setUp(self):
        # C1 ⊔ C2 ⊑ C
        self.c, self.c1, self.c2 = (
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/C1"),
            AtomicConcept("http://ex/C2"),
        )
        self.union = UnionConcept((self.c1, self.c2))
        self.axiom = ConceptInclusion(self.union, self.c)
        self.ontology = Ontology(iri="http://ex", axioms=[self.axiom])

    def test_split_into_per_disjunct_axioms(self):
        self.assertEqual(classify_axiom(self.axiom), UNCLASSIFIED)

        _normalize_union_sub(self.ontology)

        self.assertIn(ConceptInclusion(self.c1, self.c), self.ontology.axioms)
        self.assertIn(ConceptInclusion(self.c2, self.c), self.ontology.axioms)
        self.assertNotIn(self.axiom, self.ontology.axioms)
        self.assertEqual(len(self.ontology.axioms), 2)
        for ax in self.ontology.axioms:
            self.assertEqual(classify_axiom(ax), O2)

    def test_complex_disjunct_is_fully_classified_by_fixpoint(self):
        # C1 ⊔ ∃R.C2 ⊑ C — the complex disjunct's split-off axiom
        # (∃R.C2 ⊑ C) is directly O3, no further pass needed.
        role = AtomicRole("http://ex/R")
        exists_r_c2 = QualifiedExistentialConcept(role, self.c2)
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(UnionConcept((self.c1, exists_r_c2)), self.c)],
        )

        normalize_ontology(ontology)

        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        self.assertIn(ConceptInclusion(self.c1, self.c), ontology.axioms)
        self.assertIn(ConceptInclusion(exists_r_c2, self.c), ontology.axioms)

    def test_duplicate_split_result_deduplicated_by_fixpoint(self):
        # C1 ⊔ C2 ⊑ C and a pre-existing C1 ⊑ C both produce C1 ⊑ C —
        # normalize_ontology's closing dedup must collapse them to one.
        ontology = Ontology(
            iri="http://ex", axioms=[self.axiom, ConceptInclusion(self.c1, self.c)]
        )
        normalize_ontology(ontology)
        matches = [
            ax for ax in ontology.axioms if ax == ConceptInclusion(self.c1, self.c)
        ]
        self.assertEqual(len(matches), 1)

    def test_nested_union_resolved_by_fixpoint(self):
        # (C1 ⊔ C2) ⊔ C3 ⊑ C — one split leaves (C1 ⊔ C2) ⊑ C, needing a
        # second pass, handled by normalize_ontology's fixpoint.
        c3 = AtomicConcept("http://ex/C3")
        nested = UnionConcept((self.union, c3))
        ontology = Ontology(iri="http://ex", axioms=[ConceptInclusion(nested, self.c)])

        normalize_ontology(ontology)

        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        self.assertIn(ConceptInclusion(self.c1, self.c), ontology.axioms)
        self.assertIn(ConceptInclusion(self.c2, self.c), ontology.axioms)
        self.assertIn(ConceptInclusion(c3, self.c), ontology.axioms)

    def test_axioms_without_union_sub_are_untouched(self):
        plain = Ontology(
            iri="http://ex", axioms=[ConceptInclusion(self.c1, self.c)]
        )
        before = list(plain.axioms)
        _normalize_union_sub(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        _normalize_union_sub(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_union_sub(self.ontology)
        self.assertEqual(once, self.ontology.axioms)


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

        _normalize_intersection_sub(ontology)
        labels = {classify_axiom(ax) for ax in ontology.axioms}
        self.assertIn(UNCLASSIFIED, labels)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        # ∃R.B≡A_x (O3, O10),  A_x⊓C≡A_y — the ⊑ direction is O2,  the ⊒
        # direction splits into A_y⊑∃R.B (O10) and A_y⊑C (O2),  A_y⊓D⊑E
        # (O2)
        self.assertEqual(sizes[O3], 1)
        self.assertEqual(sizes[O10], 2)
        self.assertEqual(sizes[O2], 3)

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

        _normalize_union_sup(ontology)
        labels = {classify_axiom(ax) for ax in ontology.axioms}
        self.assertIn(UNCLASSIFIED, labels)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        # ∃R.C≡A_x — the ⊑ direction is O10, the ⊒ direction is O3; the ⊒
        # direction also appears once more from union-sub splitting
        # X⊔∃R.C≡A_y's ⊒ direction (X⊑A_y is O2, ∃R.C⊑A_y is O3);
        # A_y ⊑ X ⊔ A_x  (O2),  A ⊑ B ⊔ A_y  (O2)
        self.assertEqual(sizes[O10], 1)
        self.assertEqual(sizes[O3], 2)
        self.assertEqual(sizes[O2], 3)

    def test_lhs_flattening_surfaces_inverse_existential_resolved_by_fixpoint(self):
        # ∃R⁻.A ⊓ C ⊑ D — LHS flattening turns the complex conjunct ∃R⁻.A
        # into its own defining axiom ∃R⁻.A ⊑ A_x, which then needs
        # _normalize_inverse_role_concept too.
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

        _normalize_intersection_sub(ontology)
        labels = {classify_axiom(ax) for ax in ontology.axioms}
        self.assertIn(UNCLASSIFIED, labels)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        # R ≡ R'⁻  (O7 x2),  ∃R'.A ≡ A_x  (O3, O10),  A_x ⊓ C ⊑ D  (O2)
        self.assertEqual(sizes[O7], 2)
        self.assertEqual(sizes[O3], 1)
        self.assertEqual(sizes[O10], 1)
        self.assertEqual(sizes[O2], 1)

    def test_nested_existential_filler_resolved_by_fixpoint(self):
        # ∃R1.(∃R2.(C1 ⊓ C2) ⊔ C3) ⊑ C — a filler that is itself a union
        # whose own disjunct is an existential over a non-atomic filler;
        # needs _normalize_restriction_concept_filler, _normalize_union_
        # sub, and another _normalize_restriction_concept_filler pass, in
        # that order, to fully classify.
        r1, r2 = AtomicRole("http://ex/R1"), AtomicRole("http://ex/R2")
        c1, c2, c3, c = (
            AtomicConcept("http://ex/C1"),
            AtomicConcept("http://ex/C2"),
            AtomicConcept("http://ex/C3"),
            AtomicConcept("http://ex/C"),
        )
        inner_filler = IntersectionConcept((c1, c2))
        exists_r2 = QualifiedExistentialConcept(r2, inner_filler)
        outer_filler = UnionConcept((exists_r2, c3))
        exists_r1 = QualifiedExistentialConcept(r1, outer_filler)
        ontology = Ontology(iri="http://ex", axioms=[ConceptInclusion(exists_r1, c)])

        self.assertEqual(classify_axiom(ontology.axioms[0]), UNCLASSIFIED)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        # inner_filler ≡ A_y: (C1⊓C2)⊑A_y (O2), A_y⊑C1, A_y⊑C2 (O2, O2);
        # ∃R2.A_y ≡ A_z: ∃R2.A_y⊑A_z (O3), A_z⊑∃R2.A_y (O10);
        # outer_filler (∃R2.A_y ⊔ C3) ≡ A_w, split by _normalize_union_sub
        # on the ⊑ side: ∃R2.A_y⊑A_w (O3), C3⊑A_w (O2); the ⊒ side stays
        # A_w⊑(A_z⊔C3) (O2); ∃R1.A_w⊑C (O3)
        self.assertEqual(sizes[O3], 3)
        self.assertEqual(sizes[O10], 1)
        self.assertEqual(sizes[O2], 5)


class NormalizeRestrictionConceptFillerTest(unittest.TestCase):
    """Direct tests of _normalize_restriction_concept_filler, covering all
    four restriction shapes (∃, ∀, ≤n, ≥n) at both sub and sup positions."""

    def test_existential_sub_position_rewritten(self):
        # ∃R.(A ⊓ B) ⊑ C  ->  (A ⊓ B) ⊑ A_x  +  ∃R.A_x ⊑ C
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, b))
        axiom = ConceptInclusion(QualifiedExistentialConcept(role, filler), c)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(QualifiedExistentialConcept(role, fresh), c),
            ontology.axioms,
        )
        self.assertIn(fresh.id, ontology.concepts)
        self.assertIn(f"not_{fresh.id}", ontology.concepts)

    def test_existential_sup_position_rewritten(self):
        # C ⊑ ∃R.(A ⊔ B)  ->  A_x ⊑ (A ⊔ B)  +  C ⊑ ∃R.A_x
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = UnionConcept((a, b))
        axiom = ConceptInclusion(c, QualifiedExistentialConcept(role, filler))
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(fresh, filler), ontology.axioms)
        self.assertIn(
            ConceptInclusion(c, QualifiedExistentialConcept(role, fresh)),
            ontology.axioms,
        )

    def test_inverse_existential_filler_also_handled(self):
        # ∃R⁻.(A ⊓ B) ⊑ C  ->  (A ⊓ B) ⊑ A_x  +  ∃R⁻.A_x ⊑ C
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, b))
        axiom = ConceptInclusion(InverseQualifiedExistentialConcept(role, filler), c)
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(InverseQualifiedExistentialConcept(role, fresh), c),
            ontology.axioms,
        )

    def test_universal_sub_position_rewritten(self):
        # ∀R.(A ⊓ B) ⊑ C  ->  (A ⊓ B) ⊑ A_x  +  ∀R.A_x ⊑ C
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, b))
        axiom = ConceptInclusion(UniversalConcept(role, filler), c)
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(UniversalConcept(role, fresh), c), ontology.axioms
        )

    def test_universal_sup_position_rewritten(self):
        # C ⊑ ∀R.(A ⊔ B)  ->  (A ⊔ B) ⊑ A_x  +  C ⊑ ∀R.A_x
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = UnionConcept((a, b))
        axiom = ConceptInclusion(c, UniversalConcept(role, filler))
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(c, UniversalConcept(role, fresh)), ontology.axioms
        )

    def test_min_cardinality_sub_position_rewritten(self):
        # >=2R.(A ⊓ B) ⊑ C  ->  (A ⊓ B) ⊑ A_x  +  >=2R.A_x ⊑ C
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, b))
        axiom = ConceptInclusion(MinCardinalityConcept(role, 2, filler), c)
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(MinCardinalityConcept(role, 2, fresh), c), ontology.axioms
        )

    def test_min_cardinality_sup_position_rewritten(self):
        # C ⊑ >=2R.(A ⊔ B)  ->  A_x ⊑ (A ⊔ B)  +  C ⊑ >=2R.A_x
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = UnionConcept((a, b))
        axiom = ConceptInclusion(c, MinCardinalityConcept(role, 2, filler))
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(fresh, filler), ontology.axioms)
        self.assertIn(
            ConceptInclusion(c, MinCardinalityConcept(role, 2, fresh)), ontology.axioms
        )

    def test_max_cardinality_sub_position_rewritten(self):
        # <=2R.(A ⊓ B) ⊑ C  ->  (A ⊓ B) ⊑ A_x  +  <=2R.A_x ⊑ C
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, b))
        axiom = ConceptInclusion(MaxCardinalityConcept(role, 2, filler), c)
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(MaxCardinalityConcept(role, 2, fresh), c), ontology.axioms
        )

    def test_max_cardinality_sup_position_rewritten(self):
        # C ⊑ <=2R.(A ⊔ B)  ->  (A ⊔ B) ⊑ A_x  +  C ⊑ <=2R.A_x
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = UnionConcept((a, b))
        axiom = ConceptInclusion(c, MaxCardinalityConcept(role, 2, filler))
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(c, MaxCardinalityConcept(role, 2, fresh)), ontology.axioms
        )

    def test_inverse_max_cardinality_filler_also_handled(self):
        # <=2R⁻.(A ⊓ B) ⊑ C  ->  (A ⊓ B) ⊑ A_x  +  <=2R⁻.A_x ⊑ C
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, b))
        axiom = ConceptInclusion(InverseMaxCardinalityConcept(role, 2, filler), c)
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_restriction_concept_filler(ontology)

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(
            ConceptInclusion(InverseMaxCardinalityConcept(role, 2, fresh), c),
            ontology.axioms,
        )

    def test_axioms_with_atomic_filler_are_untouched(self):
        role = AtomicRole("http://ex/R")
        a, c = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/C")
        plain = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(QualifiedExistentialConcept(role, a), c),
                ConceptInclusion(MaxCardinalityConcept(role, 2, a), c),
                ConceptInclusion(c, MinCardinalityConcept(role, 2, a)),
            ],
        )
        before = list(plain.axioms)
        _normalize_restriction_concept_filler(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, b))
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(QualifiedExistentialConcept(role, filler), c),
                ConceptInclusion(MaxCardinalityConcept(role, 2, filler), c),
            ],
        )
        _normalize_restriction_concept_filler(ontology)
        once = list(ontology.axioms)
        _normalize_restriction_concept_filler(ontology)
        self.assertEqual(once, ontology.axioms)


class NormalizeInverseRoleConceptTest(unittest.TestCase):
    """Direct tests of _normalize_inverse_role_concept, covering all three
    shapes it handles (∃, ≤n, ≥n) — each uses the same R ≡ R'⁻ direction
    at both sub and sup, so one parametrized-by-hand set of tests covers
    all three."""

    # (InverseConcept class, direct Concept class, sup-side Table 1 label)
    SHAPES = (
        (InverseQualifiedExistentialConcept, QualifiedExistentialConcept, O10),
        (InverseMaxCardinalityConcept, MaxCardinalityConcept, O11),
        (InverseMinCardinalityConcept, MinCardinalityConcept, O14),
    )

    _EXISTENTIAL_CLASSES = (
        QualifiedExistentialConcept,
        InverseQualifiedExistentialConcept,
    )

    def _restriction(self, cls, role, concept):
        """cls(role, concept) for ∃, cls(role, 2, concept) for ≤2/≥2."""
        if cls in self._EXISTENTIAL_CLASSES:
            return cls(role, concept)
        return cls(role, 2, concept)

    def test_sub_position_rewritten_to_o7_plus_direct_form(self):
        for inverse_cls, direct_cls, _ in self.SHAPES:
            with self.subTest(inverse_cls=inverse_cls):
                role = AtomicRole("http://ex/R")
                a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
                axiom = ConceptInclusion(self._restriction(inverse_cls, role, a), b)
                ontology = Ontology(iri="http://ex", axioms=[axiom])
                self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

                _normalize_inverse_role_concept(ontology)

                fresh = AtomicRole(f"defr_{InverseRole(role).id}")
                self.assertIn(RoleInclusion(role, InverseRole(fresh)), ontology.axioms)
                self.assertIn(RoleInclusion(fresh, InverseRole(role)), ontology.axioms)
                self.assertIn(
                    ConceptInclusion(self._restriction(direct_cls, fresh, a), b),
                    ontology.axioms,
                )
                self.assertIn(fresh.id, ontology.roles)
                self.assertIn(f"not_{fresh.id}", ontology.roles)

    def test_sup_position_rewritten_to_o7_plus_direct_form(self):
        for inverse_cls, direct_cls, label in self.SHAPES:
            with self.subTest(inverse_cls=inverse_cls):
                role = AtomicRole("http://ex/R")
                a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
                axiom = ConceptInclusion(a, self._restriction(inverse_cls, role, b))
                ontology = Ontology(iri="http://ex", axioms=[axiom])
                self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

                _normalize_inverse_role_concept(ontology)

                fresh = AtomicRole(f"defr_{InverseRole(role).id}")
                self.assertIn(RoleInclusion(role, InverseRole(fresh)), ontology.axioms)
                self.assertIn(RoleInclusion(fresh, InverseRole(role)), ontology.axioms)
                rewritten = ConceptInclusion(a, self._restriction(direct_cls, fresh, b))
                self.assertIn(rewritten, ontology.axioms)
                self.assertEqual(classify_axiom(rewritten), label)

    def test_same_role_shared_across_all_shapes(self):
        # ∃R⁻.A ⊑ B, C ⊑ ≤2R⁻.D, and E ⊑ ≥2R⁻.F in the same ontology must
        # all reuse the identical fresh role R'.
        role = AtomicRole("http://ex/R")
        a, b, c, d, e, f = (AtomicConcept(f"http://ex/{name}") for name in "ABCDEF")
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(InverseQualifiedExistentialConcept(role, a), b),
                ConceptInclusion(c, InverseMaxCardinalityConcept(role, 2, d)),
                ConceptInclusion(e, InverseMinCardinalityConcept(role, 2, f)),
            ],
        )

        _normalize_inverse_role_concept(ontology)

        role_axioms = [ax for ax in ontology.axioms if isinstance(ax, RoleInclusion)]
        fresh = AtomicRole(f"defr_{InverseRole(role).id}")
        self.assertCountEqual(
            role_axioms,
            [
                RoleInclusion(role, InverseRole(fresh)),
                RoleInclusion(fresh, InverseRole(role)),
            ],
        )

    def test_axioms_without_inverse_role_concepts_are_untouched(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        plain = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(QualifiedExistentialConcept(role, a), b),
                ConceptInclusion(a, MaxCardinalityConcept(role, 2, b)),
                ConceptInclusion(a, MinCardinalityConcept(role, 2, b)),
            ],
        )
        before = list(plain.axioms)
        _normalize_inverse_role_concept(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(InverseQualifiedExistentialConcept(role, a), b),
                ConceptInclusion(a, InverseMaxCardinalityConcept(role, 2, b)),
                ConceptInclusion(InverseMinCardinalityConcept(role, 2, a), b),
            ],
        )
        _normalize_inverse_role_concept(ontology)
        once = list(ontology.axioms)
        _normalize_inverse_role_concept(ontology)
        self.assertEqual(once, ontology.axioms)


class NormalizeCardinalityConceptFillerLHSTest(unittest.TestCase):
    """A cardinality restriction as a ConceptInclusion's sub has no Table 1
    row itself, but is handled when R, A, B are all atomic — see
    NormalizeMinCardinalityLHSTest / NormalizeMaxCardinalityLHSTest, which
    rewrite ≥nR.A ⊑ B / ≤nR.A ⊑ B via their contrapositive into O1/O2/O11
    or O1/O2/O14. A non-atomic filler concept no longer blocks this:
    _normalize_restriction_concept_filler extracts it to a fresh atomic
    concept first, then the contrapositive rewrite applies as usual."""

    def test_max_cardinality_lhs_with_non_atomic_filler_is_fully_classified(self):
        # <=2R.(A ⊓ C) ⊑ B: filler extracted as an equivalence, (A⊓C)⊑A_x
        # (O2) and A_x⊑(A⊓C), the latter split by _normalize_intersection_
        # sup into A_x⊑A, A_x⊑C (O2, O2) — rewriting to <=2R.A_x ⊑ B, then
        # the contrapositive gives B'⊑>=3R.A_x (O14), B⊓B'⊑⊥ (O1),
        # ⊤⊑B⊔B' (O2).
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, c))
        axiom = ConceptInclusion(MaxCardinalityConcept(role, 2, filler), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        normalize_ontology(ontology)

        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        self.assertEqual(sizes[O1], 1)
        self.assertEqual(sizes[O2], 4)
        self.assertEqual(sizes[O14], 1)
        ensure_fully_supported(ontology)  # does not raise

        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(filler, fresh), ontology.axioms)
        self.assertIn(ConceptInclusion(fresh, a), ontology.axioms)
        self.assertIn(ConceptInclusion(fresh, c), ontology.axioms)

    def test_min_cardinality_lhs_with_non_atomic_filler_is_fully_classified(self):
        # >=2R.(A ⊓ C) ⊑ B: filler extracted as an equivalence, (A⊓C)⊑A_x
        # and A_x⊑(A⊓C) (O2), the latter split into A_x⊑A, A_x⊑C (O2, O2)
        # — rewriting to >=2R.A_x ⊑ B, then the contrapositive gives
        # B'⊑<=1R.A_x (O11), B⊓B'⊑⊥ (O1), ⊤⊑B⊔B' (O2).
        role = AtomicRole("http://ex/R")
        a, b, c = (
            AtomicConcept("http://ex/A"),
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
        )
        filler = IntersectionConcept((a, c))
        axiom = ConceptInclusion(MinCardinalityConcept(role, 2, filler), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        normalize_ontology(ontology)

        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        self.assertEqual(sizes[O1], 1)
        self.assertEqual(sizes[O2], 4)
        self.assertEqual(sizes[O11], 1)
        ensure_fully_supported(ontology)  # does not raise

    def test_max_cardinality_lhs_with_union_filler_is_forward_derivable(self):
        # <=2R.(A1 ⊔ A2) ⊑ B: _normalize_union_sub splits (A1⊔A2)⊑A_x
        # into A1⊑A_x and A2⊑A_x (forward-derivable from A1/A2 alone).
        role = AtomicRole("http://ex/R")
        a1, a2, b = (
            AtomicConcept("http://ex/A1"),
            AtomicConcept("http://ex/A2"),
            AtomicConcept("http://ex/B"),
        )
        filler = UnionConcept((a1, a2))
        axiom = ConceptInclusion(MaxCardinalityConcept(role, 2, filler), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        normalize_ontology(ontology)

        self.assertEqual(len(ontology.axiom_types[UNCLASSIFIED]), 0)
        fresh = AtomicConcept(f"def_{filler.id}")
        self.assertIn(ConceptInclusion(a1, fresh), ontology.axioms)
        self.assertIn(ConceptInclusion(a2, fresh), ontology.axioms)
        self.assertIn(ConceptInclusion(fresh, filler), ontology.axioms)


class NormalizeMinCardinalityLHSTest(unittest.TestCase):
    """Direct tests of _normalize_min_cardinality_LHS: ≥nR.A ⊑ B (R, A, B
    atomic) is rewritten via its contrapositive ¬B ⊑ ≤(n-1)R.A into
    B' ⊑ ≤(n-1)R.A (O11), B ⊓ B' ⊑ ⊥ (O1), ⊤ ⊑ B ⊔ B' (O2), replacing the
    original — fully classified, not UNCLASSIFIED. Only B gets a fresh
    complement; A is used directly in the O11 axiom."""

    def test_rewritten_to_o1_o2_o11(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(MinCardinalityConcept(role, 2, a), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        normalize_ontology(ontology)

        b_comp = AtomicConcept("comp_b")
        self.assertIn(
            ConceptInclusion(b_comp, MaxCardinalityConcept(role, 1, a)),
            ontology.axioms,
        )
        self.assertIn(
            ConceptInclusion(IntersectionConcept((b, b_comp)), OWL_NOTHING),
            ontology.axioms,
        )
        self.assertIn(
            ConceptInclusion(OWL_THING, UnionConcept((b, b_comp))),
            ontology.axioms,
        )
        self.assertNotIn(axiom, ontology.axioms)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[O1], 1)
        self.assertEqual(sizes[O2], 1)
        self.assertEqual(sizes[O11], 1)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        self.assertIn(b_comp.id, ontology.concepts)
        self.assertIn(f"not_{b_comp.id}", ontology.concepts)

    def test_n_equals_0_degenerates_to_thing_sub_b(self):
        # >=0R.A subseteq B holds vacuously (a count is always >= 0), so
        # this reduces straight to top subseteq B (O2) -- no fresh
        # concept, no B/B' disjointness or covering axioms at all.
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(MinCardinalityConcept(role, 0, a), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        normalize_ontology(ontology)

        self.assertEqual(ontology.axioms, [ConceptInclusion(OWL_THING, b)])
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[O2], 1)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        self.assertNotIn("comp_b", ontology.concepts)

    def test_n_equals_1_degenerates_to_existential(self):
        # >=1R.A subseteq B is exactly exists R.A subseteq B (O3) -- no
        # contrapositive, no fresh B', no disjointness/covering axioms.
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(MinCardinalityConcept(role, 1, a), b)],
        )
        normalize_ontology(ontology)
        self.assertEqual(
            ontology.axioms,
            [ConceptInclusion(QualifiedExistentialConcept(role, a), b)],
        )
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[O3], 1)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        self.assertNotIn("comp_b", ontology.concepts)

    def test_shares_fresh_complement_across_axioms_on_the_same_concept(self):
        # Two different >=nR.A subseteq B axioms (different roles/n) on the
        # same B must reuse the same B'.
        r1, r2 = AtomicRole("http://ex/R1"), AtomicRole("http://ex/R2")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(MinCardinalityConcept(r1, 2, a), b),
                ConceptInclusion(MinCardinalityConcept(r2, 3, a), b),
            ],
        )
        normalize_ontology(ontology)
        disjointness_axioms = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sup is OWL_NOTHING
        ]
        self.assertEqual(len(disjointness_axioms), 1)  # B/B' disjointness deduped

    def test_axioms_without_atomic_min_cardinality_lhs_are_untouched(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        # sup-position min-cardinality (already handled elsewhere) must be
        # left alone by this pass.
        plain = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(a, MinCardinalityConcept(role, 2, b))],
        )
        before = list(plain.axioms)
        _normalize_min_cardinality_LHS(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(MinCardinalityConcept(role, 2, a), b)],
        )
        _normalize_min_cardinality_LHS(ontology)
        once = list(ontology.axioms)
        _normalize_min_cardinality_LHS(ontology)
        self.assertEqual(once, ontology.axioms)

    def test_min_cardinality_surfaced_by_lhs_flattening_is_fully_classified(self):
        # >=2R.B ⊓ C ⊑ D — flattening extracts >=2R.B into its own defining
        # axiom >=2R.B ⊑ A_x, which this pass must then also rewrite.
        role = AtomicRole("http://ex/R")
        b, c, d = (
            AtomicConcept("http://ex/B"),
            AtomicConcept("http://ex/C"),
            AtomicConcept("http://ex/D"),
        )
        cardinality = MinCardinalityConcept(role, 2, b)
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(IntersectionConcept((cardinality, c)), d)],
        )
        normalize_ontology(ontology)
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        ensure_fully_supported(ontology)  # does not raise


class NormalizeMaxCardinalityLHSTest(unittest.TestCase):
    """Direct tests of _normalize_max_cardinality_LHS: ≤nR.A ⊑ B (R, A, B
    atomic) is rewritten via its contrapositive ¬B ⊑ ≥(n+1)R.A into
    B' ⊑ ≥(n+1)R.A (O14), B ⊓ B' ⊑ ⊥ (O1), ⊤ ⊑ B ⊔ B' (O2), replacing the
    original — fully classified, not UNCLASSIFIED. Mirrors
    NormalizeMinCardinalityLHSTest exactly, threshold flipped the other
    way (n → n+1, ≤ → ≥)."""

    def test_rewritten_to_o1_o2_o14(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(MaxCardinalityConcept(role, 2, a), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        normalize_ontology(ontology)

        b_comp = AtomicConcept("comp_b")
        self.assertIn(
            ConceptInclusion(b_comp, MinCardinalityConcept(role, 3, a)),
            ontology.axioms,
        )
        self.assertIn(
            ConceptInclusion(IntersectionConcept((b, b_comp)), OWL_NOTHING),
            ontology.axioms,
        )
        self.assertIn(
            ConceptInclusion(OWL_THING, UnionConcept((b, b_comp))),
            ontology.axioms,
        )
        self.assertNotIn(axiom, ontology.axioms)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[O1], 1)
        self.assertEqual(sizes[O2], 1)
        self.assertEqual(sizes[O14], 1)
        self.assertEqual(sizes[UNCLASSIFIED], 0)
        self.assertIn(b_comp.id, ontology.concepts)
        self.assertIn(f"not_{b_comp.id}", ontology.concepts)

    def test_n_equals_0_gives_min_cardinality_1(self):
        # <=0R.A subseteq B  ->  B' subseteq >=1R.A (still a valid O14).
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(MaxCardinalityConcept(role, 0, a), b)],
        )
        normalize_ontology(ontology)
        b_comp = AtomicConcept("comp_b")
        self.assertIn(
            ConceptInclusion(b_comp, MinCardinalityConcept(role, 1, a)),
            ontology.axioms,
        )
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])

    def test_shares_fresh_complement_across_axioms_on_the_same_concept(self):
        # Two different <=nR.A subseteq B axioms (different roles/n) on the
        # same B must reuse the same B'.
        r1, r2 = AtomicRole("http://ex/R1"), AtomicRole("http://ex/R2")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(MaxCardinalityConcept(r1, 2, a), b),
                ConceptInclusion(MaxCardinalityConcept(r2, 3, a), b),
            ],
        )
        normalize_ontology(ontology)
        disjointness_axioms = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sup is OWL_NOTHING
        ]
        self.assertEqual(len(disjointness_axioms), 1)  # B/B' disjointness deduped

    def test_shares_fresh_complement_with_min_cardinality_lhs(self):
        # >=nR1.A ⊑ B and <=mR2.A ⊑ B on the same B must reuse the same B'
        # across the two different passes.
        r1, r2 = AtomicRole("http://ex/R1"), AtomicRole("http://ex/R2")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(MinCardinalityConcept(r1, 2, a), b),
                ConceptInclusion(MaxCardinalityConcept(r2, 3, a), b),
            ],
        )
        normalize_ontology(ontology)
        disjointness_axioms = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion) and ax.sup is OWL_NOTHING
        ]
        self.assertEqual(len(disjointness_axioms), 1)  # B/B' disjointness deduped

    def test_axioms_without_atomic_max_cardinality_lhs_are_untouched(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        # sup-position max-cardinality (already handled elsewhere) must be
        # left alone by this pass.
        plain = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(a, MaxCardinalityConcept(role, 2, b))],
        )
        before = list(plain.axioms)
        _normalize_max_cardinality_LHS(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(MaxCardinalityConcept(role, 2, a), b)],
        )
        _normalize_max_cardinality_LHS(ontology)
        once = list(ontology.axioms)
        _normalize_max_cardinality_LHS(ontology)
        self.assertEqual(once, ontology.axioms)

    def test_max_cardinality_surfaced_by_lhs_flattening_is_fully_classified(self):
        # <=2R.B ⊓ C ⊑ D — flattening extracts <=2R.B into its own defining
        # axiom <=2R.B ⊑ A_x, which this pass must then also rewrite.
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
        self.assertEqual(ontology.axiom_types[UNCLASSIFIED], [])
        ensure_fully_supported(ontology)  # does not raise


class NormalizeUniversalConceptTest(unittest.TestCase):
    """Direct tests of _normalize_universal_concept: ∀R.A ⊑ B and B ⊑ ∀R.A
    (R, A, B atomic) are rewritten via their contrapositive
    ¬∀R.A ≡ ∃R.¬A into O10/O3 respectively, using fresh atomic complements
    A' ≡ ¬A, B' ≡ ¬B forced by disjointness + covering pairs."""

    def test_forall_sub_rewritten_to_o10_plus_o1_o2_pairs(self):
        # ∀R.A ⊑ B  ->  B' ⊑ ∃R.A' (O10). Negating both sides of a
        # subsumption swaps which side the existential lands on relative
        # to the B ⊑ ∀R.A case below — verified by exhaustive finite-model
        # check, see _normalize_universal_concept's docstring.
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(UniversalConcept(role, a), b)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        normalize_ontology(ontology)

        a_comp, b_comp = AtomicConcept("comp_a"), AtomicConcept("comp_b")
        self.assertIn(
            ConceptInclusion(b_comp, QualifiedExistentialConcept(role, a_comp)),
            ontology.axioms,
        )
        self.assertIn(
            ConceptInclusion(IntersectionConcept((a, a_comp)), OWL_NOTHING),
            ontology.axioms,
        )
        self.assertIn(
            ConceptInclusion(OWL_THING, UnionConcept((a, a_comp))), ontology.axioms
        )
        self.assertIn(
            ConceptInclusion(IntersectionConcept((b, b_comp)), OWL_NOTHING),
            ontology.axioms,
        )
        self.assertIn(
            ConceptInclusion(OWL_THING, UnionConcept((b, b_comp))), ontology.axioms
        )
        self.assertNotIn(axiom, ontology.axioms)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[O1], 2)
        self.assertEqual(sizes[O2], 2)
        self.assertEqual(sizes[O10], 1)
        self.assertEqual(sizes[UNCLASSIFIED], 0)

    def test_forall_sup_rewritten_to_o3(self):
        # B ⊑ ∀R.A  ->  ∃R.A' ⊑ B' (O3).
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        axiom = ConceptInclusion(b, UniversalConcept(role, a))
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        normalize_ontology(ontology)

        a_comp, b_comp = AtomicConcept("comp_a"), AtomicConcept("comp_b")
        self.assertIn(
            ConceptInclusion(QualifiedExistentialConcept(role, a_comp), b_comp),
            ontology.axioms,
        )
        self.assertNotIn(axiom, ontology.axioms)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        self.assertEqual(sizes[O3], 1)
        self.assertEqual(sizes[UNCLASSIFIED], 0)

    def test_thing_sup_stays_o13_untouched(self):
        # ⊤ ⊑ ∀R.A is O13 already, and must not be rewritten by this pass.
        role = AtomicRole("http://ex/R")
        a = AtomicConcept("http://ex/A")
        axiom = ConceptInclusion(OWL_THING, UniversalConcept(role, a))
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        before = list(ontology.axioms)
        _normalize_universal_concept(ontology)
        self.assertEqual(before, ontology.axioms)

    def test_shares_fresh_complement_with_cardinality_lhs(self):
        # B ⊑ ∀R1.A and >=nR2.A2 ⊑ B on the same B must reuse the same B'.
        r1, r2 = AtomicRole("http://ex/R1"), AtomicRole("http://ex/R2")
        a1, a2, b = (
            AtomicConcept("http://ex/A1"),
            AtomicConcept("http://ex/A2"),
            AtomicConcept("http://ex/B"),
        )
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                ConceptInclusion(b, UniversalConcept(r1, a1)),
                ConceptInclusion(MinCardinalityConcept(r2, 2, a2), b),
            ],
        )
        normalize_ontology(ontology)
        disjointness_axioms = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, ConceptInclusion)
            and ax.sup is OWL_NOTHING
            and isinstance(ax.sub, IntersectionConcept)
            and b in ax.sub.operands
        ]
        self.assertEqual(len(disjointness_axioms), 1)  # B/B' disjointness deduped

    def test_inverse_universal_concept_is_untouched(self):
        # ∀R⁻.A ⊑ B / B ⊑ ∀R⁻.A: InverseUniversalConcept isn't handled by
        # this pass and is left for a later extension.
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex",
            axioms=[ConceptInclusion(InverseUniversalConcept(role, a), b)],
        )
        before = list(ontology.axioms)
        _normalize_universal_concept(ontology)
        self.assertEqual(before, ontology.axioms)

    def test_axioms_without_universal_concept_are_untouched(self):
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        plain = Ontology(iri="http://ex", axioms=[ConceptInclusion(a, b)])
        before = list(plain.axioms)
        _normalize_universal_concept(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        role = AtomicRole("http://ex/R")
        a, b = AtomicConcept("http://ex/A"), AtomicConcept("http://ex/B")
        ontology = Ontology(
            iri="http://ex", axioms=[ConceptInclusion(UniversalConcept(role, a), b)]
        )
        _normalize_universal_concept(ontology)
        once = list(ontology.axioms)
        _normalize_universal_concept(ontology)
        self.assertEqual(once, ontology.axioms)


if __name__ == "__main__":
    unittest.main()
