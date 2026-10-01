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
    O10   A             ⊑ ∃R.B        A(x) → ∃y (R(x,y) ∧ B(y))   [normalised, below]
    O11   A             ⊑ ≤m R.B      A(x) ∧ ⋀_{i=1}^{m+1}[R(x,yi)∧B(yi)]
                                         → ⋁_{i<j} yi ≈ yj
    O12   A             ⊑ {a}         A(x) → x ≈ a
    O13   ⊤             ⊑ ∀R.A        R(x,y) → A(y)

O14 (A ⊑ ≥m R.B) is not in the paper's own Table 1: the generalisation of
O10 to m fillers, with their pairwise distinctness recorded by the
auxiliary predicate neq@ instead of an inequality:

    O14   A ⊑ ≥m R.B    A(x) → ∃y1…ym (⋀[R(x,yi)∧B(yi)] ∧ ⋀_{i<j} neq@(yi,yj))

neq@ keeps the vars from being equated, which neq_denial_rules' two shared
rules enforce:

    neq@(y,z) ∧ y ≈ z → ⊥

so no rule needs negation.

The O10 and O14 rules above are not in the paper's rule normal form
(forms (2)-(4), page 5): their heads are conjunctions, where form (3)
allows a single atom. They are therefore normalised as the paper does for
its own (R6)/(R8), page 13 — with a fresh head predicate head@<restriction
id> over x and the fillers (see _normalized_existential):

    O10   A(x) → ∃y head@(x,y)          head@(x,y) → R(x,y)
                                         head@(x,y) → B(y)
                                         R(x,y) ∧ B(y) → head@(x,y)

and likewise for O14 with fillers y1…ym (m ≥ 2) and every conjunct of its
head above, neq@ ones included. O14 with m = 1 is O10, and with m = 0 a
tautology, which translates to no rule. Every rule this module constructs
is thus normalised.

Each axiom translates to a list of rules — one, except for O10/O14
(and neq_denial_rules aside). This module only constructs the rules per
axiom it's handed — it doesn't normalize DL axioms (that's
owl.ontology_normalizer's job) and it doesn't assemble a whole
ontology's rule set (that's rules.upperbound.upperbound_rules's job, which
also adds the auxiliary top-population rules from top_population.py).
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
    QualifiedExistentialConcept,
    RoleInclusion,
    UnionConcept,
)
from pddl.conditions import Atom

from ..atoms import (
    EQUALITY_PREDICATE,
    HEAD_PREDICATE_PREFIX,
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


def translate_o1(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    body = tuple(concept_atom(a, X) for a in _conjuncts(ax.sub))
    return [DisjunctiveExistentialRule(effect=(), body=body)]


def translate_o2(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    body = tuple(concept_atom(a, X) for a in _conjuncts(ax.sub))
    effect = tuple(concept_atom(b, X) for b in _disjuncts(ax.sup))
    return [DisjunctiveExistentialRule(effect=effect, body=body)]


def translate_o3(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    exists = ax.sub
    body = (role_atom(exists.role, X, Y), concept_atom(exists.concept, Y))
    return [DisjunctiveExistentialRule(effect=(concept_atom(ax.sup, X),), body=body)]


def translate_o4(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    role = ax.sup.role
    body = (concept_atom(ax.sub, X),)
    return [DisjunctiveExistentialRule(effect=(role_atom(role, X, X),), body=body)]


def translate_o5(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    role = ax.sub.role
    body = (role_atom(role, X, X),)
    return [DisjunctiveExistentialRule(effect=(concept_atom(ax.sup, X),), body=body)]


def translate_o6(ax: RoleInclusion) -> list[DisjunctiveExistentialRule]:
    body = (role_atom(ax.sub, X, Y),)
    return [DisjunctiveExistentialRule(effect=(role_atom(ax.sup, X, Y),), body=body)]


def translate_o7(ax: RoleInclusion) -> list[DisjunctiveExistentialRule]:
    body = (role_atom(ax.sub, X, Y),)
    effect = (role_atom(ax.sup.role, Y, X),)
    return [DisjunctiveExistentialRule(effect=effect, body=body)]


def translate_o8(ax: RoleInclusion) -> list[DisjunctiveExistentialRule]:
    r, s = ax.sub.roles
    body = (role_atom(r, X, Z), role_atom(s, Z, Y))
    return [DisjunctiveExistentialRule(effect=(role_atom(ax.sup, X, Y),), body=body)]


def translate_o9(ax: RoleInclusion) -> list[DisjunctiveExistentialRule]:
    body = (role_atom(ax.sub, X, Y), role_atom(ax.sup.role, X, Y))
    return [DisjunctiveExistentialRule(effect=(), body=body)]


def _normalized_existential(
    sub, restriction_id: str, fillers: list[str], phi: list[Atom]
) -> list[DisjunctiveExistentialRule]:
    """sub(x) → ∃fillers phi, normalised by norm(), page 6, with head@…
    as C_phi:

        sub(x)         → ∃y⃗ head@…(x,y⃗)     (5)+(6), form (3)
        head@…(x,y⃗)   → γ                  (7), for each atom γ of phi
        phi            → head@…(x,y⃗)       (9)

    The head is a single conjunction (m = 1), not a disjunction, so (5) is
    the datalog rule sub(x) → E_phi(x), merged with (6) E_phi(x) → ∃y⃗
    C_phi(x,y⃗) — as the paper's (R6a)/(R8a), page 13, do. (8) phi →
    E_phi(x) only lets the c-chase see a disjunction (5) is satisfied,
    which m = 1 never needs, so it's dropped along with E_phi; (5)-(7)
    alone are a conservative extension (footnote 3).

    (9) lets the c-chase see that phi already holds for x, so it doesn't
    apply (5)+(6) there. head@… depends on phi alone, so axioms with the
    same restriction share it."""
    head = Atom(HEAD_PREDICATE_PREFIX + restriction_id, (X, *fillers))
    return [
        DisjunctiveExistentialRule(effect=(head,), body=(concept_atom(sub, X),)),
        *(DisjunctiveExistentialRule(effect=(atom,), body=(head,)) for atom in phi),
        DisjunctiveExistentialRule(effect=(head,), body=tuple(phi)),
    ]


def translate_o10(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    exists = ax.sup
    phi = [role_atom(exists.role, X, Y), concept_atom(exists.concept, Y)]
    return _normalized_existential(ax.sub, exists.id, [Y], phi)


def translate_o11(ax: ConceptInclusion | FunctionalRole) -> list[DisjunctiveExistentialRule]:
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
    return [DisjunctiveExistentialRule(effect=effect, body=tuple(body))]


def translate_o12(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    a: Nominal = ax.sup
    body = (concept_atom(ax.sub, X),)
    effect = (Atom(EQUALITY_PREDICATE, (X, a.individual.id)),)
    return [DisjunctiveExistentialRule(effect=effect, body=body)]


def translate_o13(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    restriction = ax.sup
    body = (role_atom(restriction.role, X, Y),)
    subject = X if isinstance(restriction, InverseUniversalConcept) else Y
    return [
        DisjunctiveExistentialRule(
            effect=(concept_atom(restriction.concept, subject),), body=body
        )
    ]


def translate_o14(ax: ConceptInclusion) -> list[DisjunctiveExistentialRule]:
    restriction = ax.sup
    role, n, filler = restriction.role, restriction.n, restriction.concept
    if n == 0:
        # ≥0 R.B is ⊤: the axiom is a tautology. (An empty effect would
        # instead read as ⊥, i.e. A ⊑ ⊥.)
        return []
    if n == 1:
        # ≥1 R.B is ∃R.B: share O10's rules and head predicate.
        exists = QualifiedExistentialConcept(role, filler)
        return translate_o10(ConceptInclusion(ax.sub, exists))

    variables = _filler_variables(n)
    phi = []
    for var in variables:
        phi.append(role_atom(role, X, var))
        phi.append(concept_atom(filler, var))
    for vi, vj in _pairwise(variables):
        phi.append(Atom(NEQ_PREDICATE, (vi, vj)))
    return _normalized_existential(ax.sub, restriction.id, variables, phi)


def neq_denial_rules() -> list[DisjunctiveExistentialRule]:
    """The denials making neq@ (see translate_o14) mean distinctness, in
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


def translate_axiom(ax, label: str) -> list[DisjunctiveExistentialRule]:
    """ax's normalised rules per Table 1, given the Table 1 label
    classify_axiom (or ontology.axiom_types) already assigned it."""
    return TRANSLATORS[label](ax)
