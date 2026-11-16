"""
Compute the upperbound rules of a normalized ontology:

    pi(O) ∪ (EQ1)-(EQ4) ∪ una_rules

pi(O) (Zhou et al. 2015, page 7) is the Table 1 rule of every axiom
(rules.table1), plus the top-population rules if some of them reads ⊤ in its
body (they derive nothing that is used otherwise), and the neq@ denials if
some rule uses neq@. The equality axioms (rules.equality_rules) and the UNA
rules (rules.una_rules) are added only if equality can be derived: the
ontology has number restrictions or nominals, or the caller says the task
uses "=".
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from owl import O11, O12, O14, Ontology, ensure_fully_supported

from ..atoms import NEQ_PREDICATE
from ..disjunctive_existential_rule import DisjunctiveExistentialRule
from ..equality_rules import equality_rules, rule_arities
from ..table1.table1_rules import TRANSLATORS, neq_denial_rules
from ..table1.top_population import reads_top, top_population_rules
from ..una_rules import una_rules

# Axioms that let equality be derived: number restrictions (O11, O14) and
# nominals (O12).
EQUALITY_AXIOM_LABELS = (O11, O12, O14)


def ontology_derives_equality(ontology: Ontology) -> bool:
    """Whether the ontology has number restrictions or nominals."""
    return any(ontology.axiom_types.get(label) for label in EQUALITY_AXIOM_LABELS)


def translate_ontology_by_label(
    ontology: Ontology,
) -> dict[str, list[DisjunctiveExistentialRule]]:
    """The Table 1 rules of the ontology's axioms, grouped by label in
    Table 1 order (every label present, possibly empty). Raises
    UnsupportedConstructError if some axiom is unclassified."""
    ensure_fully_supported(ontology)
    return {
        label: [
            rule
            for ax in ontology.axiom_types.get(label, ())
            for rule in translator(ax)
        ]
        for label, translator in TRANSLATORS.items()
    }


def _renamed(
    rules: list[DisjunctiveExistentialRule], rename: Callable[[str], str]
) -> list[DisjunctiveExistentialRule]:
    def atom(a):
        return a.__class__(rename(a.predicate), a.args)

    return [
        DisjunctiveExistentialRule(
            effect=tuple(atom(a) for a in rule.effect),
            body=tuple(atom(a) for a in rule.body),
        )
        for rule in rules
    ]


def compute_upperbound_rules(
    ontology: Ontology,
    constants: Iterable[str] = (),
    arities: Mapping[str, int] | None = None,
    uses_equality: bool = False,
    rename: Callable[[str], str] | None = None,
    extra_rules: Iterable[DisjunctiveExistentialRule] = (),
) -> list[DisjunctiveExistentialRule]:
    """pi(ontology), plus (EQ1)-(EQ4) and the UNA rules over constants if
    uses_equality (the task uses "=") or the ontology derives equality. In
    that order: top-population, Table 1 (by label), neq@ denials,
    extra_rules (e.g. the mko query rules, already in the caller's names),
    equality axioms, UNA rules.

    rename, if given, maps the ontology's predicate names to the caller's
    (e.g. the task's spelling); it is applied before (EQ1)/(EQ4) are
    instantiated for every predicate of the rules and of arities ({name:
    arity}, in the caller's names, e.g. the task's own predicates)."""
    table1 = [
        rule
        for rules in translate_ontology_by_label(ontology).values()
        for rule in rules
    ]
    rules = top_population_rules(ontology) if reads_top(table1) else []
    rules += table1
    if any(a.predicate == NEQ_PREDICATE for rule in rules for a in rule.effect):
        rules += neq_denial_rules()
    if rename is not None:
        rules = _renamed(rules, rename)
    rules += extra_rules
    if uses_equality or ontology_derives_equality(ontology):
        rules += equality_rules(rule_arities(rules) | dict(arities or {}))
        rules += una_rules(constants)
    return rules
