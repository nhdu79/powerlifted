"""
Classify a DisjunctiveExistentialRule by the normalised rule forms of Zhou et
al. 2015, page 5:

    β1 ∧ … ∧ βn → ⊥                     (2)
    β1 ∧ … ∧ βn → ∃z γ1(x, z)            (3)
    β1 ∧ … ∧ βn → γ1(x) ∨ … ∨ γm(x)      (4)

A rule with a single head atom and no existential variable fits both (3)
and (4); it is classified as (4) with m = 1 (a datalog rule).
"""

from __future__ import annotations

from collections.abc import Iterable

from .atoms import existential_variables
from .disjunctive_existential_rule import DisjunctiveExistentialRule

BOTTOM = "(2)"
EXISTENTIAL = "(3)"
DISJUNCTIVE = "(4)"
NORMAL_FORMS = (BOTTOM, EXISTENTIAL, DISJUNCTIVE)


def normal_form(rule: DisjunctiveExistentialRule) -> str:
    """The normal form of rule: BOTTOM, EXISTENTIAL or DISJUNCTIVE. Raises
    ValueError if rule is not normalised, i.e. its head is a conjunction
    under an existential."""
    if not rule.effect:
        return BOTTOM
    if not existential_variables(rule):
        return DISJUNCTIVE
    if len(rule.effect) == 1:
        return EXISTENTIAL
    raise ValueError(f"rule is not normalised: {rule}")


def group_by_normal_form(
    rules: Iterable[DisjunctiveExistentialRule],
) -> dict[str, list[DisjunctiveExistentialRule]]:
    """rules grouped by NORMAL_FORMS, in that order (every form present,
    possibly empty), keeping the rules' own order within a form."""
    groups = {form: [] for form in NORMAL_FORMS}
    for rule in rules:
        groups[normal_form(rule)].append(rule)
    return groups
