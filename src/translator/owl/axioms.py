"""
TBox axiom types, the Ontology container, and DL notation rendering.

Axioms are normalised into a uniform `sub` (subsumption/inclusion) form:

  rdfs:subClassOf           →  ConceptInclusion(X, Y)
  rdfs:subClassOf owl:Nothing →  ConceptInclusion(X, ⊥)   (unsatisfiable concept)
  rdfs:domain               →  ConceptInclusion(∃P, Y)
  rdfs:range                →  ConceptInclusion(∃P⁻, Y)
  owl:disjointWith          →  ConceptInclusion(X, ¬Y)
  rdfs:subPropertyOf        →  RoleInclusion(P, Q)
  owl:propertyChainAxiom    →  RoleInclusion(RoleChain(P₁,…,Pₙ), Q)
  owl:FunctionalProperty    →  FunctionalRole(P)
  owl:InverseFunctional…    →  InverseFunctionalRole(P)
"""

from __future__ import annotations

from dataclasses import dataclass, field

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

# ---------------------------------------------------------------------------
# Axiom types
# ---------------------------------------------------------------------------


@dataclass
class ConceptInclusion:
    """sub(X, Y) for concept expressions."""

    sub: ConceptExpression
    sup: ConceptExpression

    @property
    def id(self) -> str:
        return f"{self.sub.id}_sub_{self.sup.id}"

    def __str__(self) -> str:
        return self.id


@dataclass
class RoleInclusion:
    """sub(P, Q) for role expressions; arises from rdfs:subPropertyOf."""

    sub: RoleExpression
    sup: RoleExpression

    @property
    def id(self) -> str:
        return f"{self.sub.id}_sub_{self.sup.id}"

    def __str__(self) -> str:
        return self.id


@dataclass
class FunctionalRole:
    """funct(P); from rdf:type owl:FunctionalProperty."""

    role: AtomicRole

    @property
    def id(self) -> str:
        return f"func_{self.role.id}"

    def __str__(self) -> str:
        return self.id


@dataclass
class InverseFunctionalRole:
    """invFunct(P); from rdf:type owl:InverseFunctionalProperty."""

    role: AtomicRole

    @property
    def id(self) -> str:
        return f"inv_func_{self.role.id}"

    def __str__(self) -> str:
        return self.id


# ---------------------------------------------------------------------------
# DL notation rendering  (used by Ontology.print_ontology)
# ---------------------------------------------------------------------------


def _dl_filler(expr: ConceptExpression) -> str:
    """Render a restriction filler (the A in ∃P.A / ∀P.A), parenthesizing ⊓/⊔ so
    the "." doesn't appear to bind more loosely than it does."""
    inner = _dl_concept(expr)
    if isinstance(expr, (IntersectionConcept, UnionConcept)):
        return f"({inner})"
    return inner


def _dl_concept(expr: ConceptExpression) -> str:
    """Render a concept expression in standard DL notation."""
    if isinstance(expr, AtomicConcept):
        if expr == OWL_THING:
            return "⊤"
        if expr == OWL_NOTHING:
            return "⊥"
        return expr.id
    if isinstance(expr, QualifiedExistentialConcept):
        return f"∃{expr.role.id}.{_dl_filler(expr.concept)}"
    if isinstance(expr, InverseQualifiedExistentialConcept):
        return f"∃{expr.role.id}⁻.{_dl_filler(expr.concept)}"
    if isinstance(expr, UniversalConcept):
        return f"∀{expr.role.id}.{_dl_filler(expr.concept)}"
    if isinstance(expr, InverseUniversalConcept):
        return f"∀{expr.role.id}⁻.{_dl_filler(expr.concept)}"
    if isinstance(expr, MaxCardinalityConcept):
        return f"≤{expr.n}{expr.role.id}.{_dl_filler(expr.concept)}"
    if isinstance(expr, InverseMaxCardinalityConcept):
        return f"≤{expr.n}{expr.role.id}⁻.{_dl_filler(expr.concept)}"
    if isinstance(expr, MinCardinalityConcept):
        return f"≥{expr.n}{expr.role.id}.{_dl_filler(expr.concept)}"
    if isinstance(expr, InverseMinCardinalityConcept):
        return f"≥{expr.n}{expr.role.id}⁻.{_dl_filler(expr.concept)}"
    if isinstance(expr, SelfConcept):
        return f"Self({expr.role.id})"
    if isinstance(expr, Nominal):
        return f"{{{expr.individual.id}}}"
    if isinstance(expr, NegatedConcept):
        inner = _dl_concept(expr.concept)
        if isinstance(expr.concept, (IntersectionConcept, UnionConcept)):
            return f"¬({inner})"  # ¬(A ⊓ B), ¬(A ⊔ B) — parens needed
        return f"¬{inner}"  # ¬A
    if isinstance(expr, IntersectionConcept):
        return " ⊓ ".join(_dl_concept(op) for op in expr.operands)
    if isinstance(expr, UnionConcept):
        return " ⊔ ".join(_dl_concept(op) for op in expr.operands)
    return str(expr)


def _dl_role(expr: RoleExpression) -> str:
    """Render a role expression in standard DL notation."""
    if isinstance(expr, AtomicRole):
        return expr.id
    if isinstance(expr, InverseRole):
        return f"{expr.role.id}⁻"
    if isinstance(expr, NegatedRole):
        return f"¬{_dl_role(expr.role)}"  # recursive: NegatedRole(InverseRole(P)) → ¬P⁻
    if isinstance(expr, RoleChain):
        return " ∘ ".join(_dl_role(r) for r in expr.roles)
    return str(expr)


def _dl_axiom(ax) -> str:
    """Render a TBox axiom in standard DL notation."""
    if isinstance(ax, ConceptInclusion):
        return f"{_dl_concept(ax.sub)} ⊑ {_dl_concept(ax.sup)}"
    if isinstance(ax, RoleInclusion):
        return f"{_dl_role(ax.sub)} ⊑ {_dl_role(ax.sup)}"
    if isinstance(ax, FunctionalRole):
        return f"func({_dl_role(ax.role)})"
    if isinstance(ax, InverseFunctionalRole):
        return f"func({ax.role.id}⁻)"
    return str(ax)


# ---------------------------------------------------------------------------
# Ontology container
# ---------------------------------------------------------------------------


@dataclass
class Ontology:
    """
    Parsed OWL ontology, normalised into the uniform `sub`-predicate form
    described at the top of this module.

    concepts  — all supported concept expressions keyed by their .id, including:
                AtomicConcept, QualifiedExistentialConcept (∃P.A, and ∃P.⊤ when
                A is ⊤), InverseQualifiedExistentialConcept (∃P⁻.A / ∃P⁻.⊤),
                UniversalConcept, InverseUniversalConcept,
                MaxCardinalityConcept (≤nP.A), InverseMaxCardinalityConcept (≤nP⁻.A),
                MinCardinalityConcept (≥nP.A), InverseMinCardinalityConcept (≥nP⁻.A),
                SelfConcept (Self(P)), Nominal, NegatedConcept of each of the
                above, IntersectionConcept, and UnionConcept.
    roles     — all supported role expressions keyed by their .id, including:
                AtomicRole, InverseRole, NegatedRole, RoleChain (R₁∘…∘Rₙ).
    axioms    — ConceptInclusion | RoleInclusion | FunctionalRole |
                InverseFunctionalRole, each carrying an .id.
    warnings  — messages for OWL constructs that were outside the supported
                fragment and silently skipped during parsing.
    axiom_types — axioms bucketed by their Table 1 (PaGoDa paper, page 7)
                normal form label ("O1".."O13", or "unclassified"); empty
                until owl.normalizer.normalize_ontology is called.
    fresh_definitions — the expression each fresh symbol introduced by
                normalization stands for.
    """

    iri: str
    concepts: dict[str, ConceptExpression] = field(default_factory=dict)
    roles: dict[str, RoleExpression] = field(default_factory=dict)
    axioms: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    axiom_types: dict[str, list] = field(default_factory=dict)
    # fresh symbol id -> the expression it stands for; see
    # owl.ontology_normalizer.fresh_symbols.claim_fresh_symbol.
    fresh_definitions: dict[str, object] = field(default_factory=dict)

    # Convenience filters ---------------------------------------------------

    @property
    def atomic_concepts(self) -> dict[str, AtomicConcept]:
        return {k: v for k, v in self.concepts.items() if isinstance(v, AtomicConcept)}

    @property
    def atomic_roles(self) -> dict[str, AtomicRole]:
        return {k: v for k, v in self.roles.items() if isinstance(v, AtomicRole)}

    @property
    def is_supported(self) -> bool:
        """False when the ontology contains constructs outside the supported Horn DL-Lite fragment."""
        return len(self.warnings) == 0

    # Query -----------------------------------------------------------------

    def find(self, id_string: str):
        """Return the concept, role, or axiom whose .id matches id_string, or None."""
        if id_string in self.concepts:
            return self.concepts[id_string]
        if id_string in self.roles:
            return self.roles[id_string]
        for ax in self.axioms:
            if ax.id == id_string:
                return ax
        return None

    def __repr__(self) -> str:
        warn_part = f", warnings={len(self.warnings)}" if self.warnings else ""
        return (
            f"Ontology(iri={self.iri!r}, "
            f"concepts={len(self.concepts)}, "
            f"roles={len(self.roles)}, "
            f"axioms={len(self.axioms)}"
            f"{warn_part})"
        )

    def print_ontology(self) -> None:
        """Print TBox axioms in Description Logics notation."""
        print(f"Ontology: {self.iri}")

        role_incls = [ax for ax in self.axioms if isinstance(ax, RoleInclusion)]
        concept_incls = [ax for ax in self.axioms if isinstance(ax, ConceptInclusion)]
        functionals = [
            ax
            for ax in self.axioms
            if isinstance(ax, (FunctionalRole, InverseFunctionalRole))
        ]

        if role_incls:
            print("  Role inclusions:")
            for ax in role_incls:
                print(f"    {_dl_axiom(ax)}")

        if concept_incls:
            print("  Concept inclusions:")
            for ax in concept_incls:
                print(f"    {_dl_axiom(ax)}")

        if functionals:
            print("  Role characteristics:")
            for ax in functionals:
                print(f"    {_dl_axiom(ax)}")

        if not self.axioms:
            print("  (no axioms)")

        if self.warnings:
            print(
                f"  Warnings — {len(self.warnings)} unsupported construct(s) ignored:"
            )
            for w in self.warnings:
                print(f"    ! {w}")
