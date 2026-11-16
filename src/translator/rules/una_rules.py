"""
The unique name assumption (UNA) as rules: a = b → ⊥ for every ordered pair
of distinct constants a, b.

The knowledge base assumes UNA, but the search doesn't: there, distinct
objects may be equal. Wherever equality can be derived — the domain uses
"=", or the ontology has number restrictions or nominals — these rules make
deriving a = b for distinct a, b an inconsistency, as UNA demands. Both
orders are needed, as no symmetry rule for ≈ is assumed.
"""

from __future__ import annotations

from collections.abc import Iterable

from pddl.conditions import Atom

from .atoms import EQUALITY_PREDICATE
from .disjunctive_existential_rule import DisjunctiveExistentialRule


def una_rules(constants: Iterable[str]) -> list[DisjunctiveExistentialRule]:
    """a = b → ⊥ for every ordered pair of distinct constants, in the
    order of constants."""
    constants = list(dict.fromkeys(constants))
    return [
        DisjunctiveExistentialRule(effect=(), body=(Atom(EQUALITY_PREDICATE, (a, b)),))
        for a in constants
        for b in constants
        if a != b
    ]
