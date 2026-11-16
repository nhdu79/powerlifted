"""
Classify a normalized axiom into its Table 1 (O1)-(O14) bucket — see the
table in the owl.ontology_normalizer package's __init__.py docstring — or
UNCLASSIFIED.
"""

from __future__ import annotations

from owl.axioms import ConceptInclusion, FunctionalRole, Ontology, RoleInclusion
from owl.expressions import (
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    AtomicRole,
    ConceptExpression,
    IntersectionConcept,
    InverseRole,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    MinCardinalityConcept,
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


def _is_atomic_or_thing(concept: ConceptExpression) -> bool:
    """True for an atomic concept or ⊤ (Table 1's A / B)."""
    return isinstance(concept, AtomicConcept)


def _is_atomic_role(role: RoleExpression) -> bool:
    """True for a strictly atomic role, never an inverse (Table 1's R / S / T)."""
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
        if isinstance(ax.sup, NegatedRole):
            # R ⊑ ¬S  ≡  R ⊓ S ⊑ ⊥
            return O9 if _is_atomic_role(ax.sup.role) else UNCLASSIFIED
        if isinstance(ax.sup, AtomicRole):
            return O6
        return UNCLASSIFIED

    if isinstance(ax, FunctionalRole):
        # ⊤ ⊑ ≤1 P.⊤
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
