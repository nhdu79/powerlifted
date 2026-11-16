"""
Render DisjunctiveExistentialRule objects (e.g. the output of
rules.upperbound.compute_upperbound_rules) as human-readable first-order
rules, using the same logical notation as Zhou et al. 2015's Table 1 and
owl.axioms' DL-notation rendering (_dl_axiom &c.): ∧, ∨, ¬, →, ∃, ≈, ≠.

Whether a rule's effect reads as a disjunction or as a conjunction under
a shared existential isn't stored on DisjunctiveExistentialRule — same as
the C++ class it mirrors, it's derived from whether some effect atom's
argument is a variable absent from body (see disjunctive_existential_
rule.py's own module docstring).
"""

from __future__ import annotations

from collections.abc import Iterable

from pddl.conditions import Literal

from .atoms import EQUALITY_PREDICATE, existential_variables, is_variable
from .disjunctive_existential_rule import DisjunctiveExistentialRule


def _display_term(term: str) -> str:
    """Strip the "?" a variable is stored with; a constant passes through
    unchanged."""
    return term[1:] if is_variable(term) else term


def format_atom(atom: Literal) -> str:
    """predicate(arg1, arg2) — or "arg1 ≈ arg2" / "arg1 ≠ arg2" for the
    reserved equality predicate — ¬ prefixed for a NegatedAtom."""
    args = [_display_term(a) for a in atom.args]
    if atom.predicate == EQUALITY_PREDICATE:
        symbol = "≠" if atom.negated else "≈"
        return f"{args[0]} {symbol} {args[1]}"
    text = f"{atom.predicate}({', '.join(args)})"
    return f"¬{text}" if atom.negated else text


def format_effect(rule: DisjunctiveExistentialRule) -> str:
    """⊥ for an empty effect; a bare atom for a single non-existential
    one; ∃ over a conjunction when effect has existential variables;
    otherwise a disjunction."""
    if not rule.effect:
        return "⊥"

    existential = existential_variables(rule)
    if not existential and len(rule.effect) == 1:
        return format_atom(rule.effect[0])

    conjunction = " ∧ ".join(format_atom(atom) for atom in rule.effect)
    if existential:
        variables = ", ".join(_display_term(v) for v in existential)
        return f"∃{variables} ({conjunction})"
    return " ∨ ".join(format_atom(atom) for atom in rule.effect)


def format_rule(rule: DisjunctiveExistentialRule) -> str:
    """ "body → effect", e.g. "R(x, y) ∧ A(y) → B(x)"."""
    body = " ∧ ".join(format_atom(atom) for atom in rule.body) if rule.body else "⊤"
    return f"{body} → {format_effect(rule)}"


def print_rules(rules: Iterable[DisjunctiveExistentialRule]) -> None:
    """Print one formatted, 0-indexed line per rule."""
    for index, rule in enumerate(rules):
        print(f"{index}: {format_rule(rule)}")
