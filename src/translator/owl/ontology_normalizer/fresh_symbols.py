"""
Helpers shared by concept_normalization.py and role_normalization.py for
introducing a fresh atomic concept/role in place of a compound expression.

Every introduction here is a full equivalence (both ⊑ directions), not a
one-directional approximation, so the fresh symbol is always safe to
substitute for what it stands in for.
"""

from __future__ import annotations

from typing import Callable

from owl.axioms import ConceptInclusion, Ontology, RoleInclusion
from owl.expressions import (
    AtomicConcept,
    AtomicRole,
    ConceptExpression,
    InverseRole,
    NegatedConcept,
    NegatedRole,
    RoleExpression,
)

DEFINED_CONCEPT_PREFIX = "def"
COMPLEMENT_CONCEPT_PREFIX = "comp"
DEFINED_ROLE_PREFIX = "defr"


def fresh_concept_for(expr: ConceptExpression) -> AtomicConcept:
    """Fresh atomic concept standing for expr, deterministic on expr.id."""
    return AtomicConcept(f"{DEFINED_CONCEPT_PREFIX}_{expr.id}")


def fresh_complement_concept_for(concept: AtomicConcept) -> AtomicConcept:
    """Fresh atomic concept for ¬concept, deterministic on concept.id."""
    return AtomicConcept(f"{COMPLEMENT_CONCEPT_PREFIX}_{concept.id}")


def fresh_role_for(role_expr: RoleExpression) -> AtomicRole:
    """Fresh atomic role standing for role_expr, deterministic on its .id."""
    return AtomicRole(f"{DEFINED_ROLE_PREFIX}_{role_expr.id}")


class FreshSymbolClashError(ValueError):
    pass


def claim_fresh_symbol(ontology: Ontology, fresh_id: str, expr) -> None:
    """Record that fresh_id stands for expr, or raise FreshSymbolClashError
    if it already stands for a different expression.

    Fresh ids are derived from expression ids, which don't bracket nested
    compounds and so aren't injective in general (see the naming constants
    in owl.expressions); without this, two expressions sharing an id would
    silently be defined through one symbol, i.e. made equivalent."""
    known = ontology.fresh_definitions.setdefault(fresh_id, expr)
    if known != expr:
        raise FreshSymbolClashError(
            f"fresh symbol '{fresh_id}' would stand for both {known} and {expr}"
        )


def register_concept(ontology: Ontology, concept: AtomicConcept) -> None:
    """Register concept and its negation in ontology.concepts, if new."""
    if concept.id not in ontology.concepts:
        ontology.concepts[concept.id] = concept
        ontology.concepts[NegatedConcept(concept).id] = NegatedConcept(concept)


def register_role(ontology: Ontology, role: AtomicRole) -> None:
    """Register role and its negation in ontology.roles, if new."""
    if role.id not in ontology.roles:
        ontology.roles[role.id] = role
        ontology.roles[NegatedRole(role).id] = NegatedRole(role)


def eliminate_to_atomic_concept(
    ontology: Ontology,
    add: Callable[[ConceptInclusion], None],
    expr: ConceptExpression,
) -> AtomicConcept:
    """Fresh atomic concept A with A ≡ expr — adds both A⊑expr and expr⊑A
    via add, and registers A (with its negation) in ontology.concepts."""
    fresh = fresh_concept_for(expr)
    claim_fresh_symbol(ontology, fresh.id, expr)
    register_concept(ontology, fresh)
    add(ConceptInclusion(expr, fresh))
    add(ConceptInclusion(fresh, expr))
    return fresh


def eliminate_inverse_role(
    ontology: Ontology,
    add: Callable[[RoleInclusion], None],
    role: AtomicRole,
) -> AtomicRole:
    """Fresh atomic role R' with R' ≡ role⁻ — adds both role⊑R'⁻ and
    R'⊑role⁻ via add, and registers R' (with its negation) in
    ontology.roles."""
    fresh = fresh_role_for(InverseRole(role))
    claim_fresh_symbol(ontology, fresh.id, InverseRole(role))
    register_role(ontology, fresh)
    add(RoleInclusion(role, InverseRole(fresh)))
    add(RoleInclusion(fresh, InverseRole(role)))
    return fresh
