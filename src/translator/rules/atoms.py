"""
Shared building blocks for rule body/effect atoms: concept_atom/
role_atom (used by table1_rules.py's per-axiom translation and
top_population.py's auxiliary rules) and the variable helpers is_
variable/body_variables/existential_variables (used by print_rules.py
to tell a rule's effect apart as a disjunction vs. an existential
conjunction) — which is why they all live here rather than in any one
of those modules.
"""

from __future__ import annotations

from owl import AtomicConcept, AtomicRole
from pddl.conditions import Atom, Literal

from .disjunctive_existential_rule import DisjunctiveExistentialRule

X = "?x"
Y = "?y"
Z = "?z"

# The predicate name this codebase already uses for object equality (see
# pddl_parser/parsing_functions.py's handling of `(= ?x ?y)`); reused
# here for O11/O12/O14's equality/inequality atoms.
EQUALITY_PREDICATE = "="
# Predicates only the Table 1 rules use, never Clipper (which only takes an
# ontology and conjunctive queries). Like the translator's own type@<type>,
# they contain "@", which no (normalized) OWL name contains and standard
# PDDL doesn't allow — though the PDDL parser accepts it, so
# queries.names.check_names reserves them (see is_reserved_rule_predicate).
#
# Pairwise distinctness of O14's fillers (see table1_rules.translate_o14).
NEQ_PREDICATE = "neq@"
# Prefix of the fresh head predicate that normalises an O10/O14 rule (see
# table1_rules._normalized_existential); followed by the id of the
# restriction it stands for.
HEAD_PREDICATE_PREFIX = "head@"


def is_reserved_rule_predicate(name: str) -> bool:
    """True for NEQ_PREDICATE and every HEAD_PREDICATE_PREFIX name."""
    return name == NEQ_PREDICATE or name.startswith(HEAD_PREDICATE_PREFIX)


def concept_atom(concept: AtomicConcept, var: str) -> Atom:
    return Atom(concept.id, (var,))


def role_atom(role: AtomicRole, var1: str, var2: str) -> Atom:
    return Atom(role.id, (var1, var2))


def is_variable(term: str) -> bool:
    return term.startswith("?")


def body_variables(body: tuple[Literal, ...]) -> set[str]:
    return {arg for atom in body for arg in atom.args if is_variable(arg)}


def existential_variables(rule: DisjunctiveExistentialRule) -> list[str]:
    """Variables in rule.effect absent from rule.body, in first-seen
    order — non-empty iff rule.effect reads as a conjunction under a
    shared existential rather than a disjunction (see disjunctive_
    existential_rule.py's module docstring)."""
    body_vars = body_variables(rule.body)
    seen: list[str] = []
    for atom in rule.effect:
        for arg in atom.args:
            if is_variable(arg) and arg not in body_vars and arg not in seen:
                seen.append(arg)
    return seen
