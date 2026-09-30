"""
Python mirror of datalog::DisjunctiveExistentialRule (see
src/search/datalog/rules/disjunctive_existential_rule.h) — only the two
constructor fields needed to build a rule; everything else that C++
class stores (rule index, variable-position map, skolem mapping, whether
the head has existential variables) is derived there once a rule like
this is parsed, not something Python needs to compute or pass over.

A rule is body -> effect, where:
  - effect is a single atom: an ordinary derivation rule (Table 1's
    O3-O9, O13).
  - effect is several atoms, none of whose arguments is missing from
    body: a disjunctive rule — the atoms are read as OR'd together, all
    sharing the same arguments (Table 1's O2, and each pairwise equality
    disjunct of O11).
  - effect is several atoms where some argument doesn't occur in body: an
    existential rule — the atoms are read as AND'd together under one
    shared existential quantifier (Table 1's O10, and the >=m extension
    used for O14).
  - effect is empty: the special nullary head bottom (a denial/constraint
    rule; Table 1's O1, O9).

Which of these applies is not encoded in this class — same as the C++
side, it falls out of whether any effect atom's argument is a variable
absent from body (see disjunctive_existential_rule.h's constructor,
which computes has_existential_variables() this same way). This is why
the class is named after both cases at once: one DisjunctiveExistentialRule
object can be either, or (for O10-shaped rules) a conjunction under an
existential — never a mix of OR and existential quantification in the
same rule, matching the normalised rule forms (2)-(4) in Zhou et al.
2015, page 5.
"""

from __future__ import annotations

from dataclasses import dataclass

from pddl.conditions import Literal


@dataclass(frozen=True)
class DisjunctiveExistentialRule:
    """Mirrors DisjunctiveExistentialRule(std::vector<DatalogAtom> effect,
    RuleBody body) — body is always a flat conjunction, the
    datalog::GenericBody shape (possibly including a NegatedAtom, e.g.
    an inequality condition — see rules.lowerbound.clipper_rules, which parses
    Clipper's own "!=" denial rules this way); the C++ program builder
    is responsible for picking a specialised Join/Product/Project body
    itself (see DisjunctiveExistentialProgram::convert_rules_to_normal_
    form), so Python never needs to construct those directly."""

    effect: tuple[Literal, ...]
    body: tuple[Literal, ...]
