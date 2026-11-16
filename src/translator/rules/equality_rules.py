"""
The axioms of equality (EQ1)-(EQ4) of Zhou et al. 2015, page 4, which a
knowledge base using ≈ must contain — needed for the upperbound whenever
equality can be derived (the domain or problem uses "=", or the ontology has
number restrictions or nominals):

    P(x1,…,xn) → xi ≈ xi                          (EQ1)  per P, 1 ≤ i ≤ n
    x ≈ y → y ≈ x                                 (EQ2)
    x ≈ y ∧ y ≈ z → x ≈ z                         (EQ3)
    P(x1,…,xi,…,xn) ∧ xi ≈ y → P(x1,…,y,…,xn)     (EQ4)  per P, 1 ≤ i ≤ n

All are datalog rules with a single head atom over body variables, i.e.
already normalised (form (4) with m = 1, page 5). EQ1 and EQ4 are not
instantiated for ≈ itself, whose instances follow from EQ2 and EQ3.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pddl.conditions import Atom

from .atoms import EQUALITY_PREDICATE, X, Y, Z
from .disjunctive_existential_rule import DisjunctiveExistentialRule


def _eq(a: str, b: str) -> Atom:
    return Atom(EQUALITY_PREDICATE, (a, b))


def equality_rules(arities: Mapping[str, int]) -> list[DisjunctiveExistentialRule]:
    """(EQ1)-(EQ4) for the predicates in arities ({name: arity}): EQ2 and
    EQ3, then EQ1 and EQ4 per argument of each predicate, by name. Nullary
    predicates have no argument to instantiate them for."""
    rules = [
        DisjunctiveExistentialRule(effect=(_eq(Y, X),), body=(_eq(X, Y),)),
        DisjunctiveExistentialRule(effect=(_eq(X, Z),), body=(_eq(X, Y), _eq(Y, Z))),
    ]
    for name in sorted(arities):
        if name == EQUALITY_PREDICATE:
            continue
        args = tuple(f"?x{i}" for i in range(1, arities[name] + 1))
        atom = Atom(name, args)
        for i, xi in enumerate(args):
            rules.append(DisjunctiveExistentialRule(effect=(_eq(xi, xi),), body=(atom,)))
            replaced = Atom(name, args[:i] + (Y,) + args[i + 1 :])
            rules.append(
                DisjunctiveExistentialRule(effect=(replaced,), body=(atom, _eq(xi, Y)))
            )
    return rules


def rule_arities(rules: Iterable[DisjunctiveExistentialRule]) -> dict[str, int]:
    """{name: arity} of every predicate the rules use."""
    return {a.predicate: len(a.args) for rule in rules for a in rule.body + rule.effect}
