"""
Translate a single normalized DL axiom (one of owl.ontology_normalizer's
O1-O14 - classified axioms) into its DisjunctiveExistentialRule — the pi
mapping from Table 1, page 7, of Zhou et al. 2015 ("Pay-as-you-go ABox
Reasoning"):

    O1    A1 ⊓ … ⊓ An  ⊑ ⊥          ⋀Ai(x) → ⊥
    O2    A1 ⊓ … ⊓ An  ⊑ B1 ⊔ … ⊔ Bm ⋀Ai(x) → ⋁Bj(x)
    O3    ∃R.A          ⊑ B          R(x,y) ∧ A(y) → B(x)
    O4    A             ⊑ Self(R)    A(x) → R(x,x)
    O5    Self(R)         ⊑ A          R(x,x) → A(x)
    O6    R             ⊑ S          R(x,y) → S(x,y)
    O7    R             ⊑ S⁻          R(x,y) → S(y,x)
    O8    R ∘ S          ⊑ T          R(x,z) ∧ S(z,y) → T(x,y)
    O9    R ⊓ S          ⊑ ⊥          R(x,y) ∧ S(x,y) → ⊥
    O10   A             ⊑ ∃R.B        A(x) → ∃y (R(x,y) ∧ B(y))
    O11   A             ⊑ ≤m R.B      A(x) ∧ ⋀_{i=1}^{m+1}[R(x,yi)∧B(yi)]
                                         → ⋁_{i<j} yi ≈ yj
    O12   A             ⊑ {a}         A(x) → x ≈ a
    O13   ⊤             ⊑ ∀R.A        R(x,y) → A(y)

O14 (A ⊑ ≥m R.B) is not in the paper's own Table 1: the generalisation of
O10 to m fillers, with their pairwise distinctness recorded by the
auxiliary predicate neq_ instead of an inequality:

    O14   A ⊑ ≥m R.B    A(x) → ∃y1…ym (⋀[R(x,yi)∧B(yi)] ∧ ⋀_{i<j} neq_(yi,yj))

neq_ keeps the vars from being equated, which neq_denial_rules' two shared
rules enforce:

    neq_(y,z) ∧ y ≈ z → ⊥        neq_(y,z) ∧ z ≈ y → ⊥

so no rule needs negation.

Each axiom translates to exactly one rule (neq_denial_rules aside). This module only constructs a
rule per axiom it's handed — it doesn't normalize DL axioms (that's
owl.ontology_normalizer's job) and it doesn't assemble a whole
ontology's rule set (that's ontology_rules.py's job, which also adds the
auxiliary top-population rules from top_population.py).
"""

from __future__ import annotations

from owl import (
    O1,
    O2,
    O3,
    O4,
    O5,
    O6,
    O7,
    O8,
    O9,
    O10,
    O11,
    O12,
    O13,
    O14,
    OWL_THING,
    ConceptInclusion,
    FunctionalRole,
    IntersectionConcept,
    InverseUniversalConcept,
    Nominal,
    RoleInclusion,
    UnionConcept,
)
from pddl.conditions import Atom

from ..atoms import (
    EQUALITY_PREDICATE,
    NEQ_PREDICATE,
    X,
    Y,
    Z,
    concept_atom,
    role_atom,
)
from ..disjunctive_existential_rule import DisjunctiveExistentialRule


def _conjuncts(concept) -> tuple:
    """The conjuncts of an O1/O2-shaped sub: itself, or an
    IntersectionConcept's operands."""
    return concept.operands if isinstance(concept, IntersectionConcept) else (concept,)


def _disjuncts(concept) -> tuple:
    """The disjuncts of an O2-shaped sup: itself, or a UnionConcept's
    operands."""
    return concept.operands if isinstance(concept, UnionConcept) else (concept,)


def _filler_variables(count: int) -> list[str]:
    """count distinct filler variables, "?y1".."?y{count}"."""
    return [f"?y{i}" for i in range(1, count + 1)]


def _pairwise(variables: list[str]) -> list[tuple[str, str]]:
    return [(vi, vj) for i, vi in enumerate(variables) for vj in variables[i + 1 :]]


def translate_o1(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    body = tuple(concept_atom(a, X) for a in _conjuncts(ax.sub))
    return DisjunctiveExistentialRule(effect=(), body=body)


def translate_o2(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    body = tuple(concept_atom(a, X) for a in _conjuncts(ax.sub))
    effect = tuple(concept_atom(b, X) for b in _disjuncts(ax.sup))
    return DisjunctiveExistentialRule(effect=effect, body=body)


def translate_o3(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    exists = ax.sub
    body = (role_atom(exists.role, X, Y), concept_atom(exists.concept, Y))
    return DisjunctiveExistentialRule(effect=(concept_atom(ax.sup, X),), body=body)


def translate_o4(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    role = ax.sup.role
    body = (concept_atom(ax.sub, X),)
    return DisjunctiveExistentialRule(effect=(role_atom(role, X, X),), body=body)


def translate_o5(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    role = ax.sub.role
    body = (role_atom(role, X, X),)
    return DisjunctiveExistentialRule(effect=(concept_atom(ax.sup, X),), body=body)


def translate_o6(ax: RoleInclusion) -> DisjunctiveExistentialRule:
    body = (role_atom(ax.sub, X, Y),)
    return DisjunctiveExistentialRule(effect=(role_atom(ax.sup, X, Y),), body=body)


def translate_o7(ax: RoleInclusion) -> DisjunctiveExistentialRule:
    body = (role_atom(ax.sub, X, Y),)
    effect = (role_atom(ax.sup.role, Y, X),)
    return DisjunctiveExistentialRule(effect=effect, body=body)


def translate_o8(ax: RoleInclusion) -> DisjunctiveExistentialRule:
    r, s = ax.sub.roles
    body = (role_atom(r, X, Z), role_atom(s, Z, Y))
    return DisjunctiveExistentialRule(effect=(role_atom(ax.sup, X, Y),), body=body)


def translate_o9(ax: RoleInclusion) -> DisjunctiveExistentialRule:
    body = (role_atom(ax.sub, X, Y), role_atom(ax.sup.role, X, Y))
    return DisjunctiveExistentialRule(effect=(), body=body)


def translate_o10(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    exists = ax.sup
    effect = (role_atom(exists.role, X, Y), concept_atom(exists.concept, Y))
    return DisjunctiveExistentialRule(effect=effect, body=(concept_atom(ax.sub, X),))


def translate_o11(ax: ConceptInclusion | FunctionalRole) -> DisjunctiveExistentialRule:
    if isinstance(ax, FunctionalRole):
        sub, role, n, filler = OWL_THING, ax.role, 1, OWL_THING
    else:
        sub, restriction = ax.sub, ax.sup
        role, n, filler = restriction.role, restriction.n, restriction.concept

    variables = _filler_variables(n + 1)
    body = [concept_atom(sub, X)]
    for var in variables:
        body.append(role_atom(role, X, var))
        body.append(concept_atom(filler, var))
    effect = tuple(Atom(EQUALITY_PREDICATE, pair) for pair in _pairwise(variables))
    return DisjunctiveExistentialRule(effect=effect, body=tuple(body))


def translate_o12(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    a: Nominal = ax.sup
    body = (concept_atom(ax.sub, X),)
    effect = (Atom(EQUALITY_PREDICATE, (X, a.individual.id)),)
    return DisjunctiveExistentialRule(effect=effect, body=body)


def translate_o13(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    restriction = ax.sup
    body = (role_atom(restriction.role, X, Y),)
    subject = X if isinstance(restriction, InverseUniversalConcept) else Y
    return DisjunctiveExistentialRule(
        effect=(concept_atom(restriction.concept, subject),), body=body
    )


def translate_o14(ax: ConceptInclusion) -> DisjunctiveExistentialRule:
    restriction = ax.sup
    role, n, filler = restriction.role, restriction.n, restriction.concept

    variables = _filler_variables(n)
    body = (concept_atom(ax.sub, X),)
    effect = []
    for var in variables:
        effect.append(role_atom(role, X, var))
        effect.append(concept_atom(filler, var))
    for vi, vj in _pairwise(variables):
        effect.append(Atom(NEQ_PREDICATE, (vi, vj)))
    return DisjunctiveExistentialRule(effect=tuple(effect), body=body)


def neq_denial_rules() -> list[DisjunctiveExistentialRule]:
    """The denials making neq_ (see translate_o14) mean distinctness, in
    both argument orders, as ≈ may be derived either way round."""
    return [
        DisjunctiveExistentialRule(
            effect=(),
            body=(Atom(NEQ_PREDICATE, (Y, Z)), Atom(EQUALITY_PREDICATE, pair)),
        )
        for pair in ((Y, Z), (Z, Y))
    ]


TRANSLATORS = {
    O1: translate_o1,
    O2: translate_o2,
    O3: translate_o3,
    O4: translate_o4,
    O5: translate_o5,
    O6: translate_o6,
    O7: translate_o7,
    O8: translate_o8,
    O9: translate_o9,
    O10: translate_o10,
    O11: translate_o11,
    O12: translate_o12,
    O13: translate_o13,
    O14: translate_o14,
}


def translate_axiom(ax, label: str) -> DisjunctiveExistentialRule:
    """ax's rule per Table 1, given the Table 1 label classify_axiom (or
    ontology.axiom_types) already assigned it."""
    return TRANSLATORS[label](ax)
