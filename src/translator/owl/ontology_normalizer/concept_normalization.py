"""
Concept-side normalization passes: rewriting negative concept inclusions,
flattening complex conjuncts/disjuncts, splitting a conjunctive sup and a
disjunctive sub, eliminating a non-atomic ∃/∀/≤n/≥n filler, eliminating
∃R⁻/≤nR⁻/≥nR⁻ from a ConceptInclusion, and the ≥n/≤n-on-the-sub-side and
∀ contrapositive rewrites. All but the first run together, repeatedly, as
_normalize_complex_concepts_to_fixpoint in __init__.py.
"""

from __future__ import annotations

from dataclasses import replace

from owl.axioms import ConceptInclusion, Ontology
from owl.expressions import (
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    ConceptExpression,
    IntersectionConcept,
    InverseMaxCardinalityConcept,
    InverseMinCardinalityConcept,
    InverseQualifiedExistentialConcept,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    MinCardinalityConcept,
    NegatedConcept,
    QualifiedExistentialConcept,
    UnionConcept,
    UniversalConcept,
)

from .axiom_classification import _is_atomic_or_thing, _is_atomic_role
from .fresh_symbols import (
    claim_fresh_symbol,
    eliminate_inverse_role,
    eliminate_to_atomic_concept,
    fresh_complement_concept_for,
    register_concept,
)


def _normalize_negative_concept_inclusions(ontology: Ontology) -> None:
    """Rewrite X1 ⊑ ¬X2 to X1 ⊓ X2 ⊑ ⊥, registering the intersection and
    its negation in ontology.concepts. Deduplicates by axiom id."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []
    for ax in ontology.axioms:
        if not (
            isinstance(ax, ConceptInclusion) and isinstance(ax.sup, NegatedConcept)
        ):
            new_axioms.append(ax)
            continue
        inter = IntersectionConcept((ax.sub, ax.sup.concept))
        rewritten = ConceptInclusion(inter, OWL_NOTHING)
        if rewritten.id not in seen_ids:
            seen_ids.add(rewritten.id)
            register_concept(ontology, inter)
            new_axioms.append(rewritten)
        # original X1 ⊑ ¬X2 is dropped regardless
    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_intersection_sub / _normalize_intersection_sup
# _normalize_union_sub / _normalize_union_sup
# ---------------------------------------------------------------------------


def _normalize_intersection_sub(ontology: Ontology) -> None:
    """Rewrite C1 ⊓ … ⊓ Cn ⊑ … (n>=2) by replacing each non-atomic Ci
    with a fresh A_Ci ≡ Ci. Atomic conjuncts and axioms with <2 conjuncts
    are untouched; sup is never rewritten. Single pass; idempotent."""
    seen_ids = {ax.id for ax in ontology.axioms}
    defining_axioms = []
    rewritten_axioms = []

    def add(defining_axiom: ConceptInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            defining_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not (
            isinstance(ax, ConceptInclusion)
            and isinstance(ax.sub, IntersectionConcept)
            and len(ax.sub.operands) >= 2
        ):
            rewritten_axioms.append(ax)
            continue

        new_conjuncts = []
        changed = False
        for conjunct in ax.sub.operands:
            if _is_atomic_or_thing(conjunct):
                new_conjuncts.append(conjunct)
                continue
            changed = True
            new_conjuncts.append(eliminate_to_atomic_concept(ontology, add, conjunct))

        if not changed:
            rewritten_axioms.append(ax)
            continue

        rewritten_axioms.append(
            ConceptInclusion(IntersectionConcept(tuple(new_conjuncts)), ax.sup)
        )

    ontology.axioms = defining_axioms + rewritten_axioms


def _normalize_intersection_sup(ontology: Ontology) -> None:
    """Split C ⊑ C1 ⊓ … ⊓ Cn (n>=2 — Table 1 has no row for a conjunction
    on the sup side at all) into C ⊑ C1, …, C ⊑ Cn, replacing the
    original — an exact equivalence, no fresh concept needed. Each Ci is
    then handled, if it still needs it, by the other concept-
    normalization passes. Axioms whose sup isn't an IntersectionConcept
    are untouched. May produce duplicate axioms (e.g. a Ci shared with
    another axiom already in the ontology) — see
    _normalize_complex_concepts_to_fixpoint's closing deduplication."""
    new_axioms = []

    for ax in ontology.axioms:
        if not (
            isinstance(ax, ConceptInclusion) and isinstance(ax.sup, IntersectionConcept)
        ):
            new_axioms.append(ax)
            continue

        for conjunct in ax.sup.operands:
            new_axioms.append(ConceptInclusion(ax.sub, conjunct))

    ontology.axioms = new_axioms


def _normalize_union_sub(ontology: Ontology) -> None:
    """Split C1 ⊔ … ⊔ Cn ⊑ C (n>=2) into C1 ⊑ C, …, Cn ⊑ C."""
    new_axioms = []

    for ax in ontology.axioms:
        if not (isinstance(ax, ConceptInclusion) and isinstance(ax.sub, UnionConcept)):
            new_axioms.append(ax)
            continue

        for disjunct in ax.sub.operands:
            new_axioms.append(ConceptInclusion(disjunct, ax.sup))

    ontology.axioms = new_axioms


def _normalize_union_sup(ontology: Ontology) -> None:
    """Rewrite … ⊑ D1 ⊔ … ⊔ Dm (m>=2) by replacing each non-atomic Dj
    with a fresh A_Dj ≡ Dj. Atomic disjuncts and axioms with <2 disjuncts
    are untouched; sub is never rewritten. Single pass; idempotent."""
    seen_ids = {ax.id for ax in ontology.axioms}
    defining_axioms = []
    rewritten_axioms = []

    def add(defining_axiom: ConceptInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            defining_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not (
            isinstance(ax, ConceptInclusion)
            and isinstance(ax.sup, UnionConcept)
            and len(ax.sup.operands) >= 2
        ):
            rewritten_axioms.append(ax)
            continue

        new_disjuncts = []
        changed = False
        for disjunct in ax.sup.operands:
            if _is_atomic_or_thing(disjunct):
                new_disjuncts.append(disjunct)
                continue
            changed = True
            new_disjuncts.append(eliminate_to_atomic_concept(ontology, add, disjunct))

        if not changed:
            rewritten_axioms.append(ax)
            continue

        rewritten_axioms.append(
            ConceptInclusion(ax.sub, UnionConcept(tuple(new_disjuncts)))
        )

    ontology.axioms = defining_axioms + rewritten_axioms


# ---------------------------------------------------------------------------
# _normalize_restriction_concept_filler
# ---------------------------------------------------------------------------

# Concept restrictions with an explicit filler (each dataclass's .concept
# field) that Table 1 requires atomic: ∃R.X/∃R⁻.X (O3/O10), ∀R.X/∀R⁻.X
# (O13, or _normalize_universal_concept's contrapositive rewrite), ≥nR.X/
# ≥nR⁻.X (O14), ≤nR.X/≤nR⁻.X (O11).
_RESTRICTION_TYPES = (
    QualifiedExistentialConcept,
    InverseQualifiedExistentialConcept,
    UniversalConcept,
    InverseUniversalConcept,
    MinCardinalityConcept,
    InverseMinCardinalityConcept,
    MaxCardinalityConcept,
    InverseMaxCardinalityConcept,
)


def _normalize_restriction_concept_filler(ontology: Ontology) -> None:
    """Eliminate a non-atomic filler X from any of ∃R.X, ∀R.X, ≤nR.X,
    ≥nR.X (and their R⁻ variants) wherever the restriction sits directly
    on a ConceptInclusion's sub or sup, per distinct filler via a fresh
    atomic concept A ≡ X. Part of the concept-normalization fixpoint — a
    restriction nested inside another restriction's filler (e.g.
    ∃R1.(∃R2.C ⊔ D) ⊑ B) surfaces its inner ∃R2.C as a fresh defining
    axiom's own sub (via _normalize_union_sub/_normalize_intersection_sup),
    which this same pass then handles on a later iteration."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def add(defining_axiom: ConceptInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    def rewrite(concept: ConceptExpression) -> ConceptExpression:
        if not (
            isinstance(concept, _RESTRICTION_TYPES)
            and not _is_atomic_or_thing(concept.concept)
        ):
            return concept
        fresh = eliminate_to_atomic_concept(ontology, add, concept.concept)
        return replace(concept, concept=fresh)

    for ax in ontology.axioms:
        if not isinstance(ax, ConceptInclusion):
            new_axioms.append(ax)
            continue

        sub = rewrite(ax.sub)
        sup = rewrite(ax.sup)

        changed = sub is not ax.sub or sup is not ax.sup
        new_axioms.append(ConceptInclusion(sub, sup) if changed else ax)

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_inverse_role_concept
# ---------------------------------------------------------------------------

# Each of ∃R⁻.X, ≤nR⁻.X, ≥nR⁻.X has a direct (non-inverse) counterpart
# dataclass with the same fields, just without the R⁻ — this maps one to
# the other so a single pass can handle all three the same way.
_INVERSE_ROLE_CONCEPT_TYPES = {
    InverseQualifiedExistentialConcept: QualifiedExistentialConcept,
    InverseMaxCardinalityConcept: MaxCardinalityConcept,
    InverseMinCardinalityConcept: MinCardinalityConcept,
}


def _direct_form(concept, fresh_role):
    """concept's direct-role counterpart (per _INVERSE_ROLE_CONCEPT_TYPES),
    with its role replaced by fresh_role."""
    direct_cls = _INVERSE_ROLE_CONCEPT_TYPES[type(concept)]
    if hasattr(concept, "n"):
        return direct_cls(fresh_role, concept.n, concept.concept)
    return direct_cls(fresh_role, concept.concept)


def _normalize_inverse_role_concept(ontology: Ontology) -> None:
    """Eliminate ∃R⁻.X / ≤nR⁻.X / ≥nR⁻.X from a ConceptInclusion's sub or
    sup, per distinct R via a fresh atomic role R' ≡ R⁻:

        ∃R⁻.A ⊑ B   →  R ≡ R'⁻  +  ∃R'.A ⊑ B    (O3)
        A ⊑ ∃R⁻.B   →  R ≡ R'⁻  +  A ⊑ ∃R'.B    (O10)
        ≤nR⁻.A ⊑ B  →  R ≡ R'⁻  +  ≤nR'.A ⊑ B   (UNCLASSIFIED, further normalized)
        A ⊑ ≤nR⁻.B  →  R ≡ R'⁻  +  A ⊑ ≤nR'.B   (O11)
        ≥nR⁻.A ⊑ B  →  R ≡ R'⁻  +  ≥nR'.A ⊑ B   (UNCLASSIFIED, further normalized)
        A ⊑ ≥nR⁻.B  →  R ≡ R'⁻  +  A ⊑ ≥nR'.B   (O14)

    Part of the concept-normalization fixpoint."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def add(defining_axiom) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not isinstance(ax, ConceptInclusion):
            new_axioms.append(ax)
            continue

        sub, sup = ax.sub, ax.sup
        changed = False

        if type(sub) in _INVERSE_ROLE_CONCEPT_TYPES:
            fresh = eliminate_inverse_role(ontology, add, sub.role)
            sub = _direct_form(sub, fresh)
            changed = True

        if type(sup) in _INVERSE_ROLE_CONCEPT_TYPES:
            fresh = eliminate_inverse_role(ontology, add, sup.role)
            sup = _direct_form(sup, fresh)
            changed = True

        new_axioms.append(ConceptInclusion(sub, sup) if changed else ax)

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_min_cardinality_LHS / _normalize_max_cardinality_LHS
# ---------------------------------------------------------------------------


def _normalize_min_cardinality_LHS(ontology: Ontology) -> None:
    """Rewrite ≥nR.A ⊑ B via its contrapositive, replacing the original
    with:

        B' ⊑ ≤(n-1)R.A   (O11)
        B ⊓ B' ⊑ ⊥        (O1)
        ⊤ ⊑ B ⊔ B'        (O2)

    n=0 special-cases to ⊤ ⊑ B (O2) directly; n=1 special-cases to
    ∃R.A ⊑ B (O3) directly — ≥1R.A is exactly ∃R.A, so no contrapositive
    or fresh B' is needed either way."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def complement_for(concept: AtomicConcept) -> AtomicConcept:
        comp = fresh_complement_concept_for(concept)
        claim_fresh_symbol(ontology, comp.id, NegatedConcept(concept))
        register_concept(ontology, comp)
        return comp

    def add(new_axiom) -> None:
        if new_axiom.id not in seen_ids:
            seen_ids.add(new_axiom.id)
            new_axioms.append(new_axiom)

    for ax in ontology.axioms:
        if not (
            isinstance(ax, ConceptInclusion)
            and isinstance(ax.sub, MinCardinalityConcept)
            and _is_atomic_role(ax.sub.role)
            and _is_atomic_or_thing(ax.sub.concept)
            and _is_atomic_or_thing(ax.sup)
        ):
            new_axioms.append(ax)
            continue

        role, n, a, b = ax.sub.role, ax.sub.n, ax.sub.concept, ax.sup

        if n == 0:
            add(ConceptInclusion(OWL_THING, b))
            continue

        if n == 1:
            add(ConceptInclusion(QualifiedExistentialConcept(role, a), b))
            continue

        b_comp = complement_for(b)
        add(ConceptInclusion(b_comp, MaxCardinalityConcept(role, n - 1, a)))
        add(ConceptInclusion(IntersectionConcept((b, b_comp)), OWL_NOTHING))
        add(ConceptInclusion(OWL_THING, UnionConcept((b, b_comp))))

    ontology.axioms = new_axioms


def _normalize_max_cardinality_LHS(ontology: Ontology) -> None:
    """Rewrite ≤nR.A ⊑ B via its contrapositive, replacing the original
    with:

        B' ⊑ ≥(n+1)R.A   (O14)
        B ⊓ B' ⊑ ⊥        (O1)
        ⊤ ⊑ B ⊔ B'        (O2)"""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def complement_for(concept: AtomicConcept) -> AtomicConcept:
        comp = fresh_complement_concept_for(concept)
        claim_fresh_symbol(ontology, comp.id, NegatedConcept(concept))
        register_concept(ontology, comp)
        return comp

    def add(new_axiom) -> None:
        if new_axiom.id not in seen_ids:
            seen_ids.add(new_axiom.id)
            new_axioms.append(new_axiom)

    for ax in ontology.axioms:
        if not (
            isinstance(ax, ConceptInclusion)
            and isinstance(ax.sub, MaxCardinalityConcept)
            and _is_atomic_role(ax.sub.role)
            and _is_atomic_or_thing(ax.sub.concept)
            and _is_atomic_or_thing(ax.sup)
        ):
            new_axioms.append(ax)
            continue

        role, n, a, b = ax.sub.role, ax.sub.n, ax.sub.concept, ax.sup
        b_comp = complement_for(b)

        add(ConceptInclusion(b_comp, MinCardinalityConcept(role, n + 1, a)))
        add(ConceptInclusion(IntersectionConcept((b, b_comp)), OWL_NOTHING))
        add(ConceptInclusion(OWL_THING, UnionConcept((b, b_comp))))

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_universal_concept
# ---------------------------------------------------------------------------


def _normalize_universal_concept(ontology: Ontology) -> None:
    """Rewrite ∀R.A ⊑ B and B ⊑ ∀R.A via their contrapositive, replacing
    the original:

        ∀R.A ⊑ B   →   B' ⊑ ∃R.A'   (O10)
        B ⊑ ∀R.A   →   ∃R.A' ⊑ B'   (O3)
        A ⊓ A' ⊑ ⊥ (O1), ⊤ ⊑ A ⊔ A' (O2)   (and likewise for B, B')

    ⊤ ⊑ ∀R.A (O13) is untouched. InverseUniversalConcept (∀R⁻.A) is not
    handled. Part of the concept-normalization fixpoint."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def complement_for(concept: AtomicConcept) -> AtomicConcept:
        comp = fresh_complement_concept_for(concept)
        claim_fresh_symbol(ontology, comp.id, NegatedConcept(concept))
        register_concept(ontology, comp)
        return comp

    def add(new_axiom) -> None:
        if new_axiom.id not in seen_ids:
            seen_ids.add(new_axiom.id)
            new_axioms.append(new_axiom)

    def add_complement_constraints(concept: AtomicConcept, comp: AtomicConcept) -> None:
        add(ConceptInclusion(IntersectionConcept((concept, comp)), OWL_NOTHING))
        add(ConceptInclusion(OWL_THING, UnionConcept((concept, comp))))

    for ax in ontology.axioms:
        if not isinstance(ax, ConceptInclusion):
            new_axioms.append(ax)
            continue

        sub, sup = ax.sub, ax.sup

        if (
            isinstance(sub, UniversalConcept)
            and _is_atomic_role(sub.role)
            and _is_atomic_or_thing(sub.concept)
            and _is_atomic_or_thing(sup)
        ):
            # ∀R.A ⊑ B  →  B' ⊑ ∃R.A'  (O10)
            role, a, b = sub.role, sub.concept, sup
            a_comp, b_comp = complement_for(a), complement_for(b)
            add_complement_constraints(a, a_comp)
            add_complement_constraints(b, b_comp)
            add(ConceptInclusion(b_comp, QualifiedExistentialConcept(role, a_comp)))
            continue

        if (
            isinstance(sup, UniversalConcept)
            and sub is not OWL_THING
            and _is_atomic_or_thing(sub)
            and _is_atomic_role(sup.role)
            and _is_atomic_or_thing(sup.concept)
        ):
            # B ⊑ ∀R.A  →  ∃R.A' ⊑ B'  (O3)
            role, a, b = sup.role, sup.concept, sub
            a_comp, b_comp = complement_for(a), complement_for(b)
            add_complement_constraints(a, a_comp)
            add_complement_constraints(b, b_comp)
            add(ConceptInclusion(QualifiedExistentialConcept(role, a_comp), b_comp))
            continue

        new_axioms.append(ax)

    ontology.axioms = new_axioms
