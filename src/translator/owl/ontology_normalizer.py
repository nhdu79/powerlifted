"""
Normalize an ontology towards the 14 axiom forms (O1)-(O14) of Table 1,
page 7, Zhou et al. 2015 ("Pay-as-you-go ABox Reasoning"), and classify
each axiom into its Table 1 bucket.

Table 1 (n, m > 0; A, B atomic concepts or ⊤; R, S, T atomic roles):

    O1    A1 ⊓ … ⊓ An        ⊑ ⊥
    O2    A1 ⊓ … ⊓ An        ⊑ B1 ⊔ … ⊔ Bm
    O3    ∃R.A                ⊑ B
    O4    A                   ⊑ Self(R)
    O5    Self(R)              ⊑ A
    O6    R                   ⊑ S
    O7    R                   ⊑ S⁻
    O8    R ∘ S                ⊑ T
    O9    R ⊓ S                ⊑ ⊥
    O10   A                   ⊑ ∃R.B
    O11   A                   ⊑ ≤m R.B
    O12   A                   ⊑ {a}
    O13   ⊤                   ⊑ ∀R.A
    O14   A                   ⊑ ≥m R.B

An axiom not shaped like one of O1-O14 after normalization is classified
UNCLASSIFIED.
"""

from __future__ import annotations

from owl.axioms import (
    ConceptInclusion,
    FunctionalRole,
    InverseFunctionalRole,
    Ontology,
    RoleInclusion,
)
from owl.expressions import (
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    AtomicRole,
    ConceptExpression,
    IntersectionConcept,
    InverseMaxCardinalityConcept,
    InverseMinCardinalityConcept,
    InverseQualifiedExistentialConcept,
    InverseRole,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    MinCardinalityConcept,
    NegatedConcept,
    NegatedRole,
    Nominal,
    QualifiedExistentialConcept,
    RoleChain,
    RoleExpression,
    SelfConcept,
    UnionConcept,
    UniversalConcept,
)
from owl.parser import UnsupportedConstructError

# ---------------------------------------------------------------------------
# Table 1 labels
# ---------------------------------------------------------------------------

O1 = "O1"
O2 = "O2"
O3 = "O3"
O4 = "O4"
O5 = "O5"
O6 = "O6"
O7 = "O7"
O8 = "O8"
O9 = "O9"
O10 = "O10"
O11 = "O11"
O12 = "O12"
O13 = "O13"
O14 = "O14"
UNCLASSIFIED = "unclassified"

TABLE1_LABELS = (O1, O2, O3, O4, O5, O6, O7, O8, O9, O10, O11, O12, O13, O14)


def normalize_ontology(ontology: Ontology) -> None:
    """
    Normalize the ontology in-place towards Table 1 and classify every axiom
    into ontology.axiom_types: rewrite negative concept inclusions
    (X1 ⊑ ¬X2 → X1 ⊓ X2 ⊑ ⊥), eliminate inverse roles from role-axiom LHSs,
    binarize role chains longer than 2, then eliminate complex conjuncts/
    disjuncts, ∃R⁻.X, ≤nR⁻.X, and ≥nR⁻.X to a fixpoint, then classify. Never
    raises — see ensure_fully_supported to check the result before using it.
    """
    _normalize_negative_concept_inclusions(ontology)
    _normalize_inverse_role_LHS(ontology)
    _normalize_role_chain_length(ontology)
    _normalize_complex_concepts_to_fixpoint(ontology)
    _classify_axioms(ontology)


def _normalize_negative_concept_inclusions(ontology: Ontology) -> None:
    """Rewrite ConceptInclusion X1 ⊑ ¬X2 to X1 ⊓ X2 ⊑ ⊥ in-place, registering
    the new IntersectionConcept and its negation in ontology.concepts.
    Deduplicates by axiom id."""
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
            if inter.id not in ontology.concepts:
                ontology.concepts[inter.id] = inter
                ontology.concepts[NegatedConcept(inter).id] = NegatedConcept(inter)
            new_axioms.append(rewritten)
        # original X1 ⊑ ¬X2 is dropped regardless
    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_complex_concept_LHS: eliminate complex conjuncts from
# conjunctive left-hand sides
# ---------------------------------------------------------------------------

_DEFINED_CONCEPT_PREFIX = "def"


def _fresh_concept_for(conjunct: ConceptExpression) -> AtomicConcept:
    """Fresh atomic concept A_Ci for Ci, deterministic on Ci.id."""
    return AtomicConcept(f"{_DEFINED_CONCEPT_PREFIX}_{conjunct.id}")


def _normalize_complex_concept_LHS(ontology: Ontology) -> None:
    """Rewrite C1 ⊓ … ⊓ Cn ⊑ … (n >= 2) with a non-atomic Ci: add
    Ci ⊑ A_Ci per distinct complex Ci (A_Ci fresh, registered in
    ontology.concepts with its negation), and replace Ci by A_Ci. Atomic
    conjuncts and axioms with < 2 conjuncts are untouched; RHS never
    rewritten. Single pass: a nested Ci needs another call, via
    normalize_ontology's fixpoint. Idempotent by conjunct .id."""
    seen_ids = {ax.id for ax in ontology.axioms}
    defining_axioms = []
    rewritten_axioms = []

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
            fresh = _fresh_concept_for(conjunct)
            new_conjuncts.append(fresh)
            if fresh.id not in ontology.concepts:
                ontology.concepts[fresh.id] = fresh
                ontology.concepts[NegatedConcept(fresh).id] = NegatedConcept(fresh)
            defining_axiom = ConceptInclusion(conjunct, fresh)
            if defining_axiom.id not in seen_ids:
                seen_ids.add(defining_axiom.id)
                defining_axioms.append(defining_axiom)

        if not changed:
            rewritten_axioms.append(ax)
            continue

        rewritten_axioms.append(
            ConceptInclusion(IntersectionConcept(tuple(new_conjuncts)), ax.sup)
        )

    ontology.axioms = defining_axioms + rewritten_axioms


# ---------------------------------------------------------------------------
# _normalize_complex_concept_RHS: eliminate complex disjuncts from
# disjunctive right-hand sides
# ---------------------------------------------------------------------------


def _normalize_complex_concept_RHS(ontology: Ontology) -> None:
    """Rewrite … ⊑ C'1 ⊔ … ⊔ C'm (m >= 2) with a non-atomic C'j: add
    A'_{C'j} ⊑ C'j per distinct complex C'j (fresh, registered in
    ontology.concepts with its negation; shares _fresh_concept_for with the
    LHS pass), and replace C'j by A'_{C'j}. Atomic disjuncts and axioms
    with < 2 disjuncts are untouched; LHS never rewritten.

    Direction is reversed from LHS's Ci ⊑ A_Ci: C'j occurs positively, so
    C'j ⊑ A'_{C'j} alone would only be sound, not equivalence-preserving.
    A compound C'j (nested conjunction/union) has no Table 1 row and stays
    UNCLASSIFIED.

    Single pass — see _normalize_complex_concepts_to_fixpoint. Idempotent
    by disjunct .id."""
    seen_ids = {ax.id for ax in ontology.axioms}
    defining_axioms = []
    rewritten_axioms = []

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
            fresh = _fresh_concept_for(disjunct)
            new_disjuncts.append(fresh)
            if fresh.id not in ontology.concepts:
                ontology.concepts[fresh.id] = fresh
                ontology.concepts[NegatedConcept(fresh).id] = NegatedConcept(fresh)
            defining_axiom = ConceptInclusion(fresh, disjunct)
            if defining_axiom.id not in seen_ids:
                seen_ids.add(defining_axiom.id)
                defining_axioms.append(defining_axiom)

        if not changed:
            rewritten_axioms.append(ax)
            continue

        rewritten_axioms.append(
            ConceptInclusion(ax.sub, UnionConcept(tuple(new_disjuncts)))
        )

    ontology.axioms = defining_axioms + rewritten_axioms


# ---------------------------------------------------------------------------
# _normalize_inverse_existential_concept: eliminate ∃R⁻.X from a
# ConceptInclusion's sub or sup
# ---------------------------------------------------------------------------


def _normalize_inverse_existential_concept(ontology: Ontology) -> None:
    """Eliminate InverseQualifiedExistentialConcept (∃R⁻.X) from a
    ConceptInclusion's sub or sup — O3/O10 read ∃R.A with R atomic. Per
    distinct R, introduces a fresh atomic role R' (same _fresh_role_for
    naming as _normalize_inverse_role_LHS, registered with its negation)
    and rewrites:

        ∃R⁻.A ⊑ B  →  R ⊑ R'⁻  (O7)  +  ∃R'.A ⊑ B   (O3)
        A ⊑ ∃R⁻.B  →  R' ⊑ R⁻  (O7)  +  A ⊑ ∃R'.B   (O10)

    The two directions are not interchangeable (verified by finite-model
    check) — each is the one sound and complete for where R⁻ sits.

    Part of the shared concept-normalization fixpoint: a LHS/RHS pass can
    surface a fresh ∃R⁻.A ⊑ (…) defining axiom needing this pass too."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def role_for(r: AtomicRole) -> AtomicRole:
        fresh = _fresh_role_for(InverseRole(r))
        if fresh.id not in ontology.roles:
            ontology.roles[fresh.id] = fresh
            ontology.roles[NegatedRole(fresh).id] = NegatedRole(fresh)
        return fresh

    def add_defining(defining_axiom: RoleInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not isinstance(ax, ConceptInclusion):
            new_axioms.append(ax)
            continue

        sub, sup = ax.sub, ax.sup
        changed = False

        if isinstance(sub, InverseQualifiedExistentialConcept):
            fresh = role_for(sub.role)
            add_defining(RoleInclusion(sub.role, InverseRole(fresh)))
            sub = QualifiedExistentialConcept(fresh, sub.concept)
            changed = True

        if isinstance(sup, InverseQualifiedExistentialConcept):
            fresh = role_for(sup.role)
            add_defining(RoleInclusion(fresh, InverseRole(sup.role)))
            sup = QualifiedExistentialConcept(fresh, sup.concept)
            changed = True

        new_axioms.append(ConceptInclusion(sub, sup) if changed else ax)

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_inverse_max_cardinality_concept: eliminate ≤nR⁻.X from a
# ConceptInclusion's sub or sup
# ---------------------------------------------------------------------------


def _normalize_inverse_max_cardinality_concept(ontology: Ontology) -> None:
    """Eliminate InverseMaxCardinalityConcept (≤nR⁻.X) from a
    ConceptInclusion's sub or sup. Per distinct R, introduces a fresh
    atomic role R' (same _fresh_role_for naming as
    _normalize_inverse_existential_concept, registered with its negation)
    and rewrites:

        ≤nR⁻.A ⊑ B  →  R' ⊑ R⁻  (O7)  +  ≤nR'.A ⊑ B   (still UNCLASSIFIED —
                                            Table 1 has no row for a
                                            cardinality restriction on the
                                            sub side; left for a later pass)
        A ⊑ ≤nR⁻.B  →  R ⊑ R'⁻  (O7)  +  A ⊑ ≤nR'.B   (O11)

    Unlike ∃ (monotone increasing in the role), ≤n is monotone decreasing,
    so the directions are swapped relative to
    _normalize_inverse_existential_concept: sup uses R ⊑ R'⁻ (that
    function's sub-case direction), sub uses R' ⊑ R⁻ (its sup-case
    direction) — verified by finite-model check."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def role_for(r: AtomicRole) -> AtomicRole:
        fresh = _fresh_role_for(InverseRole(r))
        if fresh.id not in ontology.roles:
            ontology.roles[fresh.id] = fresh
            ontology.roles[NegatedRole(fresh).id] = NegatedRole(fresh)
        return fresh

    def add_defining(defining_axiom: RoleInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not isinstance(ax, ConceptInclusion):
            new_axioms.append(ax)
            continue

        sub, sup = ax.sub, ax.sup
        changed = False

        if isinstance(sub, InverseMaxCardinalityConcept):
            fresh = role_for(sub.role)
            add_defining(RoleInclusion(fresh, InverseRole(sub.role)))
            sub = MaxCardinalityConcept(fresh, sub.n, sub.concept)
            changed = True

        if isinstance(sup, InverseMaxCardinalityConcept):
            fresh = role_for(sup.role)
            add_defining(RoleInclusion(sup.role, InverseRole(fresh)))
            sup = MaxCardinalityConcept(fresh, sup.n, sup.concept)
            changed = True

        new_axioms.append(ConceptInclusion(sub, sup) if changed else ax)

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_inverse_min_cardinality_concept: eliminate ≥nR⁻.X from a
# ConceptInclusion's sub or sup
# ---------------------------------------------------------------------------


def _normalize_inverse_min_cardinality_concept(ontology: Ontology) -> None:
    """Eliminate InverseMinCardinalityConcept (≥nR⁻.X) from a
    ConceptInclusion's sub or sup. Per distinct R, introduces a fresh
    atomic role R' (same _fresh_role_for naming as
    _normalize_inverse_max_cardinality_concept /
    _normalize_inverse_existential_concept, registered with its negation)
    and rewrites:

        ≥nR⁻.A ⊑ B  →  R ⊑ R'⁻  (O7)  +  ≥nR'.A ⊑ B   (still UNCLASSIFIED —
                                            Table 1 has no row for a
                                            cardinality restriction on the
                                            sub side; left for a later pass)
        A ⊑ ≥nR⁻.B  →  R' ⊑ R⁻  (O7)  +  A ⊑ ≥nR'.B   (O14)

    Unlike ≤n (anti-monotone — see
    _normalize_inverse_max_cardinality_concept), ≥n is monotone increasing,
    same as ∃, so this matches _normalize_inverse_existential_concept's
    direction split exactly (sub: R ⊑ R'⁻; sup: R' ⊑ R⁻) — both opposite
    of the max-cardinality function."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def role_for(r: AtomicRole) -> AtomicRole:
        fresh = _fresh_role_for(InverseRole(r))
        if fresh.id not in ontology.roles:
            ontology.roles[fresh.id] = fresh
            ontology.roles[NegatedRole(fresh).id] = NegatedRole(fresh)
        return fresh

    def add_defining(defining_axiom: RoleInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not isinstance(ax, ConceptInclusion):
            new_axioms.append(ax)
            continue

        sub, sup = ax.sub, ax.sup
        changed = False

        if isinstance(sub, InverseMinCardinalityConcept):
            fresh = role_for(sub.role)
            add_defining(RoleInclusion(sub.role, InverseRole(fresh)))
            sub = MinCardinalityConcept(fresh, sub.n, sub.concept)
            changed = True

        if isinstance(sup, InverseMinCardinalityConcept):
            fresh = role_for(sup.role)
            add_defining(RoleInclusion(fresh, InverseRole(sup.role)))
            sup = MinCardinalityConcept(fresh, sup.n, sup.concept)
            changed = True

        new_axioms.append(ConceptInclusion(sub, sup) if changed else ax)

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_min_cardinality_LHS: rewrite ≥nR.A ⊑ B (R, A, B atomic) via the
# contrapositive, into forms already covered by O1/O2/O11
# ---------------------------------------------------------------------------

_COMPLEMENT_CONCEPT_PREFIX = "comp"


def _fresh_complement_concept_for(concept: AtomicConcept) -> AtomicConcept:
    """Fresh atomic concept B' standing in for ¬B, deterministic on B's
    .id. Uses a distinct prefix from _fresh_concept_for's def_ family so an
    unrelated concept can't collide with some B's complement by .id."""
    return AtomicConcept(f"{_COMPLEMENT_CONCEPT_PREFIX}_{concept.id}")


def _normalize_min_cardinality_LHS(ontology: Ontology) -> None:
    """Rewrite ≥nR.A ⊑ B (R, A, B atomic — Table 1 has no row for a
    cardinality restriction on the sub side) via its contrapositive into
    three already-classifiable axioms, replacing the original:

        B' ⊑ ≤(n-1)R.A   (O11)
        B ⊓ B' ⊑ ⊥        (O1)
        ⊤ ⊑ B ⊔ B'        (O2)

    B' is fresh per distinct B (shared across axioms via
    _fresh_complement_concept_for), forced to be exactly ¬B by the
    disjointness + covering pair together — an exact equivalence.

    n=0 is a degenerate special case, not the general contrapositive above:
    "≥0R.A" holds vacuously for every individual (a count is always >= 0),
    so ≥0R.A ⊑ B is just ⊤ ⊑ B (O2) — R and A drop out entirely, no fresh
    concept needed. OWL2 allows minQualifiedCardinality="0", so this does
    come up."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def complement_for(concept: AtomicConcept) -> AtomicConcept:
        comp = _fresh_complement_concept_for(concept)
        if comp.id not in ontology.concepts:
            ontology.concepts[comp.id] = comp
            ontology.concepts[NegatedConcept(comp).id] = NegatedConcept(comp)
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

        b_comp = complement_for(b)
        add(ConceptInclusion(b_comp, MaxCardinalityConcept(role, n - 1, a)))
        add(ConceptInclusion(IntersectionConcept((b, b_comp)), OWL_NOTHING))
        add(ConceptInclusion(OWL_THING, UnionConcept((b, b_comp))))

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_max_cardinality_LHS: rewrite ≤nR.A ⊑ B (R, A, B atomic) via the
# contrapositive, into forms already covered by O1/O2/O14
# ---------------------------------------------------------------------------


def _normalize_max_cardinality_LHS(ontology: Ontology) -> None:
    """Rewrite ≤nR.A ⊑ B (R, A, B atomic, n >= 0 — Table 1 has no row for a
    cardinality restriction on the sub side) via its contrapositive into
    three already-classifiable axioms, replacing the original:

        B' ⊑ ≥(n+1)R.A   (O14)
        B ⊓ B' ⊑ ⊥        (O1)
        ⊤ ⊑ B ⊔ B'        (O2)

    Mirrors _normalize_min_cardinality_LHS exactly (same B'=¬B
    construction via _fresh_complement_concept_for, A untouched), just
    with the threshold flipped the other way (n → n+1, ≤ → ≥) since
    ¬(count ≤ n) ≡ count ≥ n+1 rather than ≤ n-1. Unlike the min-cardinality
    case, n=0 needs no special casing here: ≤0R.A is a real constraint
    ("no R-successors in A"), not a vacuous one, so the general rewrite
    (giving ≥1R.A, a valid O14 axiom) applies uniformly."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def complement_for(concept: AtomicConcept) -> AtomicConcept:
        comp = _fresh_complement_concept_for(concept)
        if comp.id not in ontology.concepts:
            ontology.concepts[comp.id] = comp
            ontology.concepts[NegatedConcept(comp).id] = NegatedConcept(comp)
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


def _normalize_complex_concepts_to_fixpoint(ontology: Ontology) -> None:
    """Run the concept-normalization passes together, repeatedly, until
    none adds an axiom — a defining axiom introduced by one pass can
    itself need another (e.g. its subject is a further
    conjunction/disjunction, contains ∃R⁻.X / ≤nR⁻.X / ≥nR⁻.X, or is
    itself a ≥nR.A ⊑ B / ≤nR.A ⊑ B shape once atomic)."""
    while True:
        axiom_count_before = len(ontology.axioms)
        # TODO(dnh): Rewrite this into recursive?
        _normalize_complex_concept_LHS(ontology)
        _normalize_complex_concept_RHS(ontology)
        _normalize_inverse_existential_concept(ontology)
        _normalize_inverse_max_cardinality_concept(ontology)
        _normalize_inverse_min_cardinality_concept(ontology)
        _normalize_min_cardinality_LHS(ontology)
        _normalize_max_cardinality_LHS(ontology)
        if len(ontology.axioms) == axiom_count_before:
            break


# ---------------------------------------------------------------------------
# _normalize_inverse_role_LHS: eliminate inverse roles from role-axiom LHSs
# ---------------------------------------------------------------------------

_DEFINED_ROLE_PREFIX = "defr"


def _fresh_role_for(role_expr: RoleExpression) -> AtomicRole:
    """Fresh atomic role for a role expression, deterministic on its .id."""
    return AtomicRole(f"{_DEFINED_ROLE_PREFIX}_{role_expr.id}")


def _normalize_inverse_role_LHS(ontology: Ontology) -> None:
    """Replace an inverse role R⁻ on a RoleInclusion's LHS — bare, or as a
    RoleChain member — with a fresh atomic role R' (registered in
    ontology.roles with its negation), adding R ⊑ R'⁻ per distinct R⁻ (the
    O7-shaped equivalent of R⁻ ⊑ R', since R⁻⊑R' and R⊑R'⁻ are the same
    containment fact). Axioms with no inverse-role LHS are untouched.

    Single pass, idempotent: the defining axiom's LHS (R, atomic) never
    itself matches this pass's target, so re-running is a no-op; a repeated
    R⁻ (across a chain, axioms, or calls) reuses the same R'."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def eliminate(inverse_role: InverseRole) -> AtomicRole:
        fresh = _fresh_role_for(inverse_role)
        if fresh.id not in ontology.roles:
            ontology.roles[fresh.id] = fresh
            ontology.roles[NegatedRole(fresh).id] = NegatedRole(fresh)
        defining_axiom = RoleInclusion(inverse_role.role, InverseRole(fresh))
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)
        return fresh

    for ax in ontology.axioms:
        if not isinstance(ax, RoleInclusion):
            new_axioms.append(ax)
            continue

        if isinstance(ax.sub, RoleChain):
            if not any(isinstance(r, InverseRole) for r in ax.sub.roles):
                new_axioms.append(ax)
                continue
            new_members = tuple(
                eliminate(r) if isinstance(r, InverseRole) else r for r in ax.sub.roles
            )
            new_axioms.append(RoleInclusion(RoleChain(new_members), ax.sup))
            continue

        if isinstance(ax.sub, InverseRole):
            new_axioms.append(RoleInclusion(eliminate(ax.sub), ax.sup))
            continue

        new_axioms.append(ax)

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# _normalize_role_chain_length: binarize role chains longer than 2
# ---------------------------------------------------------------------------


def _normalize_role_chain_length(ontology: Ontology) -> None:
    """Binarize R1∘…∘Rn ⊑ T (n > 2; O8 only covers a 2-role chain) into
    n-1 two-role RoleInclusion axioms via n-2 fresh atomic roles
    (registered in ontology.roles with their negations):

        R1∘R2 ⊑ U1,  U1∘R3 ⊑ U2,  …,  U_{n-2}∘Rn ⊑ T

    replacing the original axiom. Chains of length <= 2 are untouched. Each
    Ui is keyed on its prefix chain's .id — idempotent, and a repeated
    prefix across axioms reuses the same role/axiom. One-directional
    (prefix ⊑ Ui, not the reverse) suffices for equivalence, same as
    _normalize_complex_concept_LHS. Single pass: every RoleChain produced
    has length 2, so no fixpoint is needed."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    for ax in ontology.axioms:
        if not (
            isinstance(ax, RoleInclusion)
            and isinstance(ax.sub, RoleChain)
            and len(ax.sub.roles) > 2
        ):
            new_axioms.append(ax)
            continue

        roles = ax.sub.roles
        acc = roles[0]
        for i in range(1, len(roles)):
            pair_chain = RoleChain((acc, roles[i]))
            if pair_chain.id not in ontology.roles:
                ontology.roles[pair_chain.id] = pair_chain

            is_last = i == len(roles) - 1
            target = ax.sup if is_last else _fresh_role_for(RoleChain(roles[: i + 1]))
            if not is_last and target.id not in ontology.roles:
                ontology.roles[target.id] = target
                ontology.roles[NegatedRole(target).id] = NegatedRole(target)

            binary_axiom = RoleInclusion(pair_chain, target)
            if binary_axiom.id not in seen_ids:
                seen_ids.add(binary_axiom.id)
                new_axioms.append(binary_axiom)

            acc = target

    ontology.axioms = new_axioms


# ---------------------------------------------------------------------------
# Table 1 classification
# ---------------------------------------------------------------------------


def _is_atomic_or_thing(concept: ConceptExpression) -> bool:
    """A / B in Table 1: an atomic concept or ⊤ (⊥ is also an AtomicConcept,
    but it never legitimately appears here except as O1's fixed RHS, which
    callers check for separately)."""
    return isinstance(concept, AtomicConcept)


def _is_atomic_role(role: RoleExpression) -> bool:
    """R / S / T in Table 1: strictly an atomic role, never an inverse —
    O7's R ⊑ S⁻ is the only place Table 1 allows an inverse, and that's
    checked directly (isinstance(ax.sup, InverseRole)), not via this."""
    return isinstance(role, AtomicRole)


def classify_axiom(ax) -> str:
    """Return the Table 1 label (O1-O14) for a single normalized axiom, or
    UNCLASSIFIED if it doesn't (yet) match one of those forms."""
    if isinstance(ax, RoleInclusion):
        if isinstance(ax.sub, RoleChain):
            if (
                len(ax.sub.roles) == 2
                and all(_is_atomic_role(r) for r in ax.sub.roles)
                and _is_atomic_role(ax.sup)
            ):
                return O8
            return UNCLASSIFIED
        if not _is_atomic_role(ax.sub):
            return UNCLASSIFIED
        if isinstance(ax.sup, InverseRole):
            return O7
        if isinstance(ax.sup, AtomicRole):
            return O6
        return UNCLASSIFIED

    if isinstance(ax, (FunctionalRole, InverseFunctionalRole)):
        # ⊤ ⊑ ≤1 P.⊤  /  ⊤ ⊑ ≤1 P⁻.⊤
        return O11

    if isinstance(ax, ConceptInclusion):
        sub, sup = ax.sub, ax.sup

        if isinstance(sub, SelfConcept):
            return O5 if _is_atomic_or_thing(sup) else UNCLASSIFIED
        if isinstance(sup, SelfConcept):
            return O4 if _is_atomic_or_thing(sub) else UNCLASSIFIED

        if isinstance(sup, Nominal):
            return O12 if _is_atomic_or_thing(sub) else UNCLASSIFIED

        if isinstance(sup, (UniversalConcept, InverseUniversalConcept)):
            return (
                O13
                if sub is OWL_THING
                and _is_atomic_role(sup.role)
                and _is_atomic_or_thing(sup.concept)
                else UNCLASSIFIED
            )

        if isinstance(sup, MaxCardinalityConcept):
            return (
                O11
                if _is_atomic_or_thing(sub)
                and _is_atomic_role(sup.role)
                and _is_atomic_or_thing(sup.concept)
                else UNCLASSIFIED
            )

        if isinstance(sup, MinCardinalityConcept):
            return (
                O14
                if _is_atomic_or_thing(sub)
                and _is_atomic_role(sup.role)
                and _is_atomic_or_thing(sup.concept)
                else UNCLASSIFIED
            )

        if isinstance(sup, QualifiedExistentialConcept):
            return (
                O10
                if _is_atomic_or_thing(sub)
                and _is_atomic_role(sup.role)
                and _is_atomic_or_thing(sup.concept)
                else UNCLASSIFIED
            )

        if isinstance(sub, QualifiedExistentialConcept):
            return (
                O3
                if _is_atomic_role(sub.role)
                and _is_atomic_or_thing(sub.concept)
                and _is_atomic_or_thing(sup)
                else UNCLASSIFIED
            )

        conjuncts = sub.operands if isinstance(sub, IntersectionConcept) else (sub,)
        if not all(_is_atomic_or_thing(c) for c in conjuncts):
            return UNCLASSIFIED

        if sup is OWL_NOTHING:
            return O1

        disjuncts = sup.operands if isinstance(sup, UnionConcept) else (sup,)
        if all(_is_atomic_or_thing(d) for d in disjuncts):
            return O2

    return UNCLASSIFIED


def _classify_axioms(ontology: Ontology) -> None:
    """Populate ontology.axiom_types: {label -> [axioms]}, one entry per
    Table 1 label (always present, possibly empty) plus UNCLASSIFIED."""
    axiom_types: dict[str, list] = {label: [] for label in TABLE1_LABELS}
    axiom_types[UNCLASSIFIED] = []
    for ax in ontology.axioms:
        axiom_types[classify_axiom(ax)].append(ax)
    ontology.axiom_types = axiom_types


def ensure_fully_supported(ontology: Ontology) -> None:
    """Raise UnsupportedConstructError if ontology has any parse warning or
    any UNCLASSIFIED axiom (call after normalize_ontology). Parsing and
    normalization never raise on their own — call this only where an
    ontology is actually about to be used, e.g. for planning."""
    unclassified = ontology.axiom_types.get(UNCLASSIFIED, [])
    if not ontology.warnings and not unclassified:
        return
    problems = list(ontology.warnings) + [
        f"unclassified axiom: {ax}" for ax in unclassified
    ]
    raise UnsupportedConstructError(
        f"ontology {ontology.iri!r} is not fully supported:\n  " + "\n  ".join(problems)
    )
