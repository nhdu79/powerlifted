"""
The auxiliary top-population rules Zhou et al. 2015 (page 7) requires
alongside Table 1's per-axiom rules (table1_rules.py): "a rule
A(x)->⊤(x) for each atomic concept A [in the ontology]... and rules
R(x,y)->⊤(x) and R(x,y)->⊤(y) for each atomic role R". Without these,
any rule using ⊤ in its body (e.g. ⊤ ⊑ B's thing(x) -> b(x), or
∃R.⊤ ⊑ B's r(x,y) ∧ thing(y) -> b(x)) would be unreachable, since ⊤ is "translated as an ordinary
unary predicate, the meaning of which is axiomatised" rather than a
built-in symbol (same page).

Conversely, the top-population rules are only needed if some rule reads ⊤
in its body (reads_top): otherwise the ⊤ facts they derive are never used.
"""

from __future__ import annotations

from collections.abc import Iterable

from owl import OWL_THING, Ontology

from ..atoms import X, Y, concept_atom, role_atom
from ..disjunctive_existential_rule import DisjunctiveExistentialRule


def reads_top(rules: Iterable[DisjunctiveExistentialRule]) -> bool:
    """Whether some rule has ⊤ in its body."""
    return any(a.predicate == OWL_THING.id for rule in rules for a in rule.body)


def top_population_rules(ontology: Ontology) -> list[DisjunctiveExistentialRule]:
    """A(x) -> ⊤(x) for each atomic concept A, and R(x,y) -> ⊤(x),
    R(x,y) -> ⊤(y) for each atomic role R in the ontology."""
    rules = []
    thing_x = (concept_atom(OWL_THING, X),)
    thing_y = (concept_atom(OWL_THING, Y),)
    for concept in ontology.atomic_concepts.values():
        if concept == OWL_THING:
            continue
        body = (concept_atom(concept, X),)
        rules.append(DisjunctiveExistentialRule(effect=thing_x, body=body))
    for role in ontology.atomic_roles.values():
        edge = (role_atom(role, X, Y),)
        rules.append(DisjunctiveExistentialRule(effect=thing_x, body=edge))
        rules.append(DisjunctiveExistentialRule(effect=thing_y, body=edge))
    return rules
