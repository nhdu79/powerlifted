"""
Role-side normalization passes: eliminating an inverse role from a
RoleInclusion's LHS, from a disjoint-role axiom, and from an
inverse-functional-role axiom, and binarizing long role chains. Each runs
once, before the concept-normalization fixpoint, in normalize_ontology.
"""

from __future__ import annotations

from owl.axioms import FunctionalRole, InverseFunctionalRole, Ontology, RoleInclusion
from owl.expressions import (
    CHAIN_SEP,
    AtomicRole,
    InverseRole,
    NegatedRole,
    RoleChain,
)

from .fresh_symbols import (
    DEFINED_ROLE_PREFIX,
    claim_fresh_symbol,
    eliminate_inverse_role,
    register_role,
)


def _normalize_inverse_role_LHS(ontology: Ontology) -> None:
    """Replace an inverse role R⁻ on a RoleInclusion's LHS — bare, or as a
    RoleChain member — with a fresh atomic role R' ≡ R⁻ per distinct R⁻.
    Axioms with no inverse-role LHS are untouched. Single pass; idempotent."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def add(defining_axiom: RoleInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    def eliminate(inverse_role: InverseRole) -> AtomicRole:
        return eliminate_inverse_role(ontology, add, inverse_role.role)

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


def _normalize_inverse_disjoint_role(ontology: Ontology) -> None:
    """Eliminate an inverse role from a disjoint-role RoleInclusion (sup a
    NegatedRole) — O9 needs both roles atomic. Per distinct R⁻, introduces
    a fresh atomic role R' ≡ R⁻ (same fresh_role_for naming as
    _normalize_inverse_role_LHS) and rewrites:

        R⁻ ⊓ S ⊑ ⊥  →  R ≡ R'⁻  +  R' ⊓ S ⊑ ⊥   (O9)
        R ⊓ S⁻ ⊑ ⊥  →  S ≡ S'⁻  +  R ⊓ S' ⊑ ⊥   (O9)

    Each side is rewritten independently, only if it is actually an
    inverse role. Single pass; idempotent."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def add(defining_axiom: RoleInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not (isinstance(ax, RoleInclusion) and isinstance(ax.sup, NegatedRole)):
            new_axioms.append(ax)
            continue

        sub, negated = ax.sub, ax.sup.role
        changed = False

        if isinstance(sub, InverseRole):
            sub = eliminate_inverse_role(ontology, add, sub.role)
            changed = True

        if isinstance(negated, InverseRole):
            negated = eliminate_inverse_role(ontology, add, negated.role)
            changed = True

        new_axioms.append(RoleInclusion(sub, NegatedRole(negated)) if changed else ax)

    ontology.axioms = new_axioms


def _normalize_inverse_functional_role(ontology: Ontology) -> None:
    """Eliminate InverseFunctionalRole(P) — O11 needs an atomic role, but
    invFunct(P) means P⁻ is functional. Per distinct P, introduces a
    fresh atomic role P' ≡ P⁻ (same fresh_role_for naming as
    _normalize_inverse_role_LHS) and rewrites:

        invFunct(P)  →  P ≡ P'⁻  +  funct(P')   (O11)

    Single pass; idempotent."""
    seen_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    def add(defining_axiom: RoleInclusion) -> None:
        if defining_axiom.id not in seen_ids:
            seen_ids.add(defining_axiom.id)
            new_axioms.append(defining_axiom)

    for ax in ontology.axioms:
        if not isinstance(ax, InverseFunctionalRole):
            new_axioms.append(ax)
            continue

        fresh = eliminate_inverse_role(ontology, add, ax.role)

        functional_axiom = FunctionalRole(fresh)
        if functional_axiom.id not in seen_ids:
            seen_ids.add(functional_axiom.id)
            new_axioms.append(functional_axiom)

    ontology.axioms = new_axioms


def _normalize_role_chain_length(ontology: Ontology) -> None:
    """Binarize R1∘…∘Rn ⊑ T (n>2) into n-1 two-role RoleInclusion axioms
    via n-2 fresh atomic roles, replacing the original:

        R1∘R2 ⊑ U1,  U1∘R3 ⊑ U2,  …,  U_{n-2}∘Rn ⊑ T

    Chains of length <=2 are untouched. Single pass; idempotent."""
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
        prefix_id = acc.id  # roles[0].id ∘ … ∘ roles[i].id, built up incrementally
        for i in range(1, len(roles)):
            pair_chain = RoleChain((acc, roles[i]))
            if pair_chain.id not in ontology.roles:
                ontology.roles[pair_chain.id] = pair_chain

            prefix_id = f"{prefix_id}{CHAIN_SEP}{roles[i].id}"
            is_last = i == len(roles) - 1
            target = (
                ax.sup if is_last else AtomicRole(f"{DEFINED_ROLE_PREFIX}_{prefix_id}")
            )
            if not is_last:
                claim_fresh_symbol(ontology, target.id, RoleChain(roles[: i + 1]))
                register_role(ontology, target)

            binary_axiom = RoleInclusion(pair_chain, target)
            if binary_axiom.id not in seen_ids:
                seen_ids.add(binary_axiom.id)
                new_axioms.append(binary_axiom)

            acc = target

    ontology.axioms = new_axioms
