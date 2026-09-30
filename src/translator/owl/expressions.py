"""
Concept and role expression types used in TBox representation.

    AtomicConcept                  A | ⊤ | ⊥ (A atomic)
    QualifiedExistentialConcept(P, X)         ∃P.X   (∃P.⊤ when X is ⊤ — domain concept of P)
    InverseQualifiedExistentialConcept(P, X)  ∃P⁻.X  (∃P⁻.⊤ when X is ⊤ — range concept of P)
    UniversalConcept(P, X)                    ∀P.X
    InverseUniversalConcept(P, X)             ∀P⁻.X
    MaxCardinalityConcept(P, n, X)            ≤nP.X   (qualified number restriction)
    InverseMaxCardinalityConcept(P, n, X)     ≤nP⁻.X
    MinCardinalityConcept(P, n, X)            ≥nP.X
    InverseMinCardinalityConcept(P, n, X)     ≥nP⁻.X
    SelfConcept(P)                  Self(P)  (P atomic; owl:hasSelf / ObjectHasSelf)
    NegatedConcept(X)              ¬X
    IntersectionConcept(ops)       X₁ ⊓ … ⊓ Xₙ
    UnionConcept(ops)              X₁ ⊔ … ⊔ Xₙ
    Nominal(a)                     {a}

    AtomicRole                     P
    InverseRole(P)                 P⁻
    NegatedRole(P)                 ¬P
    RoleChain(roles)                R₁∘R₂∘…∘Rₙ  (role composition; owl:propertyChainAxiom)

    Individual                     a  (named individual, used by Nominal)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from rdflib.namespace import OWL

# ---------------------------------------------------------------------------
# Naming constants — used to build compound expression IDs and importable
# by any module that needs to construct or recognise those names.
# ---------------------------------------------------------------------------

#
# Every constant contains "_", while a user name never does (parse_name
# drops it), so no compound or generated id can equal a user name. Every
# prefix ends in "_" as well, so that no prefix is a prefix of another one
# followed by a user name ("exists_" + "invr" vs. "existsinv_" + "r").
# Nested compounds aren't bracketed, though, so the ids are not injective
# in general; owl.ontology_normalizer.fresh_symbols' register_* guard
# against two expressions sharing one fresh symbol.
EXISTENTIAL_PREFIX = "exists_"
INVERSE_EXISTENTIAL_PREFIX = "existsinv_"
INVERSE_PREFIX = "inv_"
NOT_PREFIX = "not_"
AND_SEP = "_and_"
OR_SEP = "_or_"
QUALIFIED_SEP = "_dot_"
FORALL_PREFIX = "forall_"
INVERSE_FORALL_PREFIX = "forallinv_"
NOMINAL_PREFIX = "nom_"
SELF_PREFIX = "self_"
MAX_CARDINALITY_PREFIX = "maxcard_"
INVERSE_MAX_CARDINALITY_PREFIX = "maxcardinv_"
MIN_CARDINALITY_PREFIX = "mincard_"
INVERSE_MIN_CARDINALITY_PREFIX = "mincardinv_"
CARD_SEP = "_"
CHAIN_SEP = "_o_"


def parse_name(name):
    """Normalize a user name: lowercase, keep only [a-z0-9] (mirrors
    pddl-horndl's normalize_user_name). Apply it exactly once, to user
    names only — never to a generated name, whose "_" it would erase."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _local_name(iri: str) -> str:
    """Return the id of an entity named iri.

    For an absolute IRI (a user entity), the fragment (after #) or last
    path segment (after /), normalized with parse_name. Anything else is a
    fresh symbol minted by owl.ontology_normalizer (e.g. "def_exists_r_dot_a"),
    whose name is already an id and is kept verbatim, "_" included.
    """
    if ":" not in iri:
        return iri
    for sep in ("#", "/"):
        if sep in iri:
            return parse_name(iri.rsplit(sep, 1)[-1])
    return parse_name(iri)


# ---------------------------------------------------------------------------
# Concept expressions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AtomicConcept:
    """Named (atomic) concept."""

    iri: str

    @property
    def id(self) -> str:
        return _local_name(self.iri)

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class NegatedConcept:
    """¬X — negation of any concept expression."""

    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return f"{NOT_PREFIX}{self.concept.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class IntersectionConcept:
    """X₁ ⊓ … ⊓ Xₙ — conjunction of concepts (Horn DL-Lite); from owl:intersectionOf."""

    operands: tuple  # tuple[ConceptExpression, ...]

    @property
    def id(self) -> str:
        return AND_SEP.join(o.id for o in self.operands)

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class UnionConcept:
    """X₁ ⊔ … ⊔ Xₙ — disjunction of concepts; from owl:unionOf."""

    operands: tuple  # tuple[ConceptExpression, ...]

    @property
    def id(self) -> str:
        return OR_SEP.join(o.id for o in self.operands)

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class QualifiedExistentialConcept:
    """∃P.X — existential restriction with an explicit filler concept (owl:someValuesFrom).

    A filler of ⊤ (OWL_THING) is the unqualified ∃P.⊤ — domain concept of role P;
    OWL_THING's own id ("thing", from str(OWL.Thing)) is a plain AtomicConcept id,
    so no special-casing is needed here — the general formula already produces a
    stable id ("existsP_dot_thing") for it.
    """

    role: "AtomicRole"
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return f"{EXISTENTIAL_PREFIX}{self.role.id}{QUALIFIED_SEP}{self.concept.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class InverseQualifiedExistentialConcept:
    """∃P⁻.X — existential restriction on the inverse role (owl:someValuesFrom on [owl:inverseOf P]).

    A filler of ⊤ (OWL_THING) is the unqualified ∃P⁻.⊤ — range concept of role P;
    see QualifiedExistentialConcept.id for why OWL_THING needs no special-casing.
    """

    role: "AtomicRole"
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return f"{INVERSE_EXISTENTIAL_PREFIX}{self.role.id}{QUALIFIED_SEP}{self.concept.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class UniversalConcept:
    """∀P.X — universal restriction with an explicit filler concept (owl:allValuesFrom)."""

    role: "AtomicRole"
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return f"{FORALL_PREFIX}{self.role.id}{QUALIFIED_SEP}{self.concept.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class InverseUniversalConcept:
    """∀P⁻.X — universal restriction on the inverse role (owl:allValuesFrom on [owl:inverseOf P])."""

    role: "AtomicRole"
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return f"{INVERSE_FORALL_PREFIX}{self.role.id}{QUALIFIED_SEP}{self.concept.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class MaxCardinalityConcept:
    """≤n P.X — qualified max-cardinality restriction (owl:maxQualifiedCardinality
    on P with owl:onClass X)."""

    role: "AtomicRole"
    n: int
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return (
            f"{MAX_CARDINALITY_PREFIX}{self.n}{CARD_SEP}{self.role.id}"
            f"{QUALIFIED_SEP}{self.concept.id}"
        )

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class InverseMaxCardinalityConcept:
    """≤n P⁻.X — qualified max-cardinality restriction on the inverse role
    (owl:maxQualifiedCardinality on [owl:inverseOf P] with owl:onClass X)."""

    role: "AtomicRole"
    n: int
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return (
            f"{INVERSE_MAX_CARDINALITY_PREFIX}{self.n}{CARD_SEP}{self.role.id}"
            f"{QUALIFIED_SEP}{self.concept.id}"
        )

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class MinCardinalityConcept:
    """≥n P.X — qualified min-cardinality restriction (owl:minQualifiedCardinality
    on P with owl:onClass X)."""

    role: "AtomicRole"
    n: int
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return (
            f"{MIN_CARDINALITY_PREFIX}{self.n}{CARD_SEP}{self.role.id}"
            f"{QUALIFIED_SEP}{self.concept.id}"
        )

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class InverseMinCardinalityConcept:
    """≥n P⁻.X — qualified min-cardinality restriction on the inverse role
    (owl:minQualifiedCardinality on [owl:inverseOf P] with owl:onClass X)."""

    role: "AtomicRole"
    n: int
    concept: "ConceptExpression"

    @property
    def id(self) -> str:
        return (
            f"{INVERSE_MIN_CARDINALITY_PREFIX}{self.n}{CARD_SEP}{self.role.id}"
            f"{QUALIFIED_SEP}{self.concept.id}"
        )

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class SelfConcept:
    """Self(P) — local reflexivity of role P (owl:hasSelf / OWL2 ObjectHasSelf); P is atomic."""

    role: "AtomicRole"

    @property
    def id(self) -> str:
        return f"{SELF_PREFIX}{self.role.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class Individual:
    """Named individual — a member of an owl:oneOf enumeration."""

    iri: str

    @property
    def id(self) -> str:
        return _local_name(self.iri)

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class Nominal:
    """{a} — singleton concept containing exactly the individual a; from owl:oneOf."""

    individual: Individual

    @property
    def id(self) -> str:
        return f"{NOMINAL_PREFIX}{self.individual.id}"

    def __str__(self) -> str:
        return self.id


ConceptExpression = Union[
    AtomicConcept,
    QualifiedExistentialConcept,
    InverseQualifiedExistentialConcept,
    UniversalConcept,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    InverseMaxCardinalityConcept,
    MinCardinalityConcept,
    InverseMinCardinalityConcept,
    SelfConcept,
    NegatedConcept,
    IntersectionConcept,
    UnionConcept,
    Nominal,
]

OWL_THING = AtomicConcept(str(OWL.Thing))
OWL_NOTHING = AtomicConcept(str(OWL.Nothing))


# ---------------------------------------------------------------------------
# Role expressions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AtomicRole:
    """Named (atomic) role."""

    iri: str

    @property
    def id(self) -> str:
        return _local_name(self.iri)

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class InverseRole:
    """P⁻ — inverse of a role."""

    role: AtomicRole

    @property
    def id(self) -> str:
        return f"{INVERSE_PREFIX}{self.role.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class NegatedRole:
    """¬P — negation of a role."""

    role: AtomicRole | InverseRole

    @property
    def id(self) -> str:
        return f"{NOT_PREFIX}{self.role.id}"

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class RoleChain:
    """R₁∘R₂∘…∘Rₙ — role composition (property chain); from owl:propertyChainAxiom.

    Order matters (composition is not commutative in general) — roles is a
    tuple, not a set, and members may themselves be complex (e.g. InverseRole).
    """

    roles: tuple  # tuple[RoleExpression, ...]

    @property
    def id(self) -> str:
        return CHAIN_SEP.join(r.id for r in self.roles)

    def __str__(self) -> str:
        return self.id


RoleExpression = Union[AtomicRole, InverseRole, NegatedRole, RoleChain]
