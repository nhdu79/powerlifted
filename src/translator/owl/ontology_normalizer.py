"""
Normalize an ontology towards the 13 axiom forms (O1)-(O13) of Table 1,
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

"R atomic" is strict — never an inverse role, except O7's explicit S⁻ on the
right. owl:FunctionalProperty(P) / owl:InverseFunctionalProperty(P) are the
O11 special case ⊤ ⊑ ≤1 P.⊤ / ⊤ ⊑ ≤1 P⁻.⊤.

_normalize_complex_concept_LHS / _RHS eliminate non-atomic conjuncts/disjuncts
from a conjunctive LHS / disjunctive RHS via a fresh atomic concept, defined
by Ci ⊑ A_Ci (LHS) or A'_{C'j} ⊑ C'j (RHS) — direction flips by polarity;
either way one-directional keeps the rewrite equivalence-preserving.
_normalize_inverse_existential_concept and
_normalize_inverse_max_cardinality_concept eliminate ∃R⁻.X and ≤nR⁻.X
similarly, via a fresh atomic role rather than a fresh concept — see each's
own docstring for its defining-axiom direction; these are NOT
interchangeable between the two functions, or between a function's own
sub/sup cases, despite the superficial similarity.

_normalize_inverse_role_LHS replaces an inverse role R⁻ on a role axiom's
LHS (bare, or as a chain member) with a fresh atomic role R', adding
R ⊑ R'⁻ (the O7-shaped equivalent of R⁻ ⊑ R'). _normalize_role_chain_length
then binarizes a (now all-atomic) role chain longer than 2 via fresh atomic
roles (O8 covers only R∘S⊑T).

An axiom not shaped like one of O1-O13 after normalization is classified
UNCLASSIFIED rather than dropped or mis-bucketed — this includes a
cardinality restriction as a ConceptInclusion's sub (≤nR.B ⊑ A / ≤nR⁻.B
⊑ A), which has no Table 1 row at all (unlike ∃R.A, which has both O3 and
O10) since it's inherently non-Horn there. normalize_ontology itself never
raises; call ensure_fully_supported afterwards to abort (with
UnsupportedConstructError) once an ontology is actually about to be used,
e.g. for planning.
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
    InverseQualifiedExistentialConcept,
    InverseRole,
    InverseUniversalConcept,
    MaxCardinalityConcept,
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
UNCLASSIFIED = "unclassified"

TABLE1_LABELS = (O1, O2, O3, O4, O5, O6, O7, O8, O9, O10, O11, O12, O13)


def normalize_ontology(ontology: Ontology) -> None:
    """
    Normalize the ontology in-place towards Table 1 and classify every axiom
    into ontology.axiom_types: rewrite negative concept inclusions
    (X1 ⊑ ¬X2 → X1 ⊓ X2 ⊑ ⊥), eliminate inverse roles from role-axiom LHSs,
    binarize role chains longer than 2, then eliminate complex conjuncts/
    disjuncts, ∃R⁻.X, and ≤nR⁻.X to a fixpoint, then classify. Never raises
    — see ensure_fully_supported to check the result before using it.
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
# ConceptInclusion's sup
# ---------------------------------------------------------------------------


def _normalize_inverse_max_cardinality_concept(ontology: Ontology) -> None:
    """Eliminate InverseMaxCardinalityConcept (≤nR⁻.X) from a
    ConceptInclusion's sup — O11 reads ≤mR.B with R atomic (Table 1 has no
    row for a cardinality restriction on the sub side, so that's not
    handled here). Per distinct R, introduces a fresh atomic role R' (same
    _fresh_role_for naming as _normalize_inverse_existential_concept,
    registered with its negation) and rewrites:

        A ⊑ ≤nR⁻.B  →  R ⊑ R'⁻  (O7)  +  A ⊑ ≤nR'.B   (O11)

    Unlike ∃ (monotone increasing in the role), ≤n is monotone decreasing,
    so — despite R⁻ sitting in the sup position, same as
    _normalize_inverse_existential_concept's ∃-sup case — this needs the
    R ⊑ R'⁻ direction, not that case's R' ⊑ R⁻ (verified by finite-model
    check; the two functions are not interchangeable by structural
    position alone)."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    for ax in ontology.axioms:
        if not (
            isinstance(ax, ConceptInclusion)
            and isinstance(ax.sup, InverseMaxCardinalityConcept)
        ):
            new_axioms.append(ax)
            continue

        sup = ax.sup
        fresh = _fresh_role_for(InverseRole(sup.role))
        if fresh.id not in ontology.roles:
            ontology.roles[fresh.id] = fresh
            ontology.roles[NegatedRole(fresh).id] = NegatedRole(fresh)

        defining_axiom = RoleInclusion(sup.role, InverseRole(fresh))
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

        new_axioms.append(
            ConceptInclusion(ax.sub, MaxCardinalityConcept(fresh, sup.n, sup.concept))
        )

    ontology.axioms = new_axioms


def _normalize_complex_concepts_to_fixpoint(ontology: Ontology) -> None:
    """Run the LHS, RHS, inverse-existential, and inverse-max-cardinality
    passes together, repeatedly, until none adds an axiom — a defining
    axiom introduced by one can itself need another (e.g. its own subject
    is a further conjunction/disjunction, or contains ∃R⁻.X / ≤nR⁻.X)."""
    while True:
        axiom_count_before = len(ontology.axioms)
        _normalize_complex_concept_LHS(ontology)
        _normalize_complex_concept_RHS(ontology)
        _normalize_inverse_existential_concept(ontology)
        _normalize_inverse_max_cardinality_concept(ontology)
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
    """Return the Table 1 label (O1-O13) for a single normalized axiom, or
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
