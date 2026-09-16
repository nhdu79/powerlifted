"""
TBox saturation: derives implicit concept/role inclusions from role inclusions,
and normalises negative concept inclusions.

Implements the structural rules from t_closure.rls (lines 122-128) that lift
role inclusions R ⊑ P into concept and inverse-role inclusions:

  sub(?X1,?Y1) :- sub(?X,?Y), domOf(?X1,?X), domOf(?Y1,?Y)   →  ∃R ⊑ ∃P
  sub(?X1,?Y1) :- sub(?X,?Y), rngOf(?X1,?X), rngOf(?Y1,?Y)   →  ∃R⁻ ⊑ ∃P⁻
  sub(?X1,?Y1) :- sub(?X,?Y), invOf(?X1,?X), invOf(?Y1,?Y)   →  R⁻ ⊑ P⁻

A single pass over the original axioms suffices; newly derived axioms produce
no further novel conclusions beyond those derived in the same pass.
"""

from __future__ import annotations

from owl.axioms import ConceptInclusion, Ontology, RoleInclusion
from owl.expressions import (
    OWL_THING,
    AtomicRole,
    ConceptExpression,
    InverseQualifiedExistentialConcept,
    InverseRole,
    QualifiedExistentialConcept,
    RoleExpression,
)


def _dom_of(role: RoleExpression) -> ConceptExpression:
    """Domain concept of a role: AtomicRole(R) → ∃R,  InverseRole(R) → ∃R⁻."""
    if isinstance(role, AtomicRole):
        return QualifiedExistentialConcept(role, OWL_THING)
    return InverseQualifiedExistentialConcept(role.role, OWL_THING)


def _rng_of(role: RoleExpression) -> ConceptExpression:
    """Range concept of a role: AtomicRole(R) → ∃R⁻,  InverseRole(R) → ∃R."""
    if isinstance(role, AtomicRole):
        return InverseQualifiedExistentialConcept(role, OWL_THING)
    return QualifiedExistentialConcept(role.role, OWL_THING)


def _inv_of(role: RoleExpression) -> RoleExpression:
    """Inverse of a role (invOf symmetry): AtomicRole(R) → R⁻,  InverseRole(R) → R."""
    if isinstance(role, AtomicRole):
        return InverseRole(role)
    return role.role


def saturate_role_inclusions(ontology: Ontology) -> None:
    """
    Extend ontology.axioms in-place with concept/role inclusions implied by
    every RoleInclusion R ⊑ P where R and P are AtomicRole or InverseRole.
    """
    existing_ids = {ax.id for ax in ontology.axioms}
    new_axioms = []

    for ax in list(ontology.axioms):  # snapshot — original axioms only
        if not isinstance(ax, RoleInclusion):
            continue
        if not isinstance(ax.sub, (AtomicRole, InverseRole)):
            continue
        if not isinstance(ax.sup, (AtomicRole, InverseRole)):
            continue
        r, p = ax.sub, ax.sup

        candidates = [
            ConceptInclusion(_dom_of(r), _dom_of(p)),  # ∃R ⊑ ∃P
            ConceptInclusion(_rng_of(r), _rng_of(p)),  # ∃R⁻ ⊑ ∃P⁻
            RoleInclusion(_inv_of(r), _inv_of(p)),  # R⁻ ⊑ P⁻
        ]
        for candidate in candidates:
            if candidate.id not in existing_ids:
                new_axioms.append(candidate)
                existing_ids.add(candidate.id)

    ontology.axioms.extend(new_axioms)
