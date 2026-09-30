"""
Assemble a whole normalized owl.Ontology's rule set: table1_rules.py's
per-axiom translation plus the auxiliary rules — top_population.py's, and
table1_rules.neq_denial_rules if some rule uses neq_. This is
the pi(O) knowledge base from Zhou et al. 2015, page 7, minus the
equality axioms (EQ1)-(EQ4) for congruence of ≈ over every predicate in
the final knowledge base — those need the full final predicate
signature (this module's rules plus whatever else the assembled program
uses), so they belong to whatever assembles the complete knowledge base,
not to this ontology-level translation.
"""

from __future__ import annotations

from owl import Ontology, ensure_fully_supported

from ..atoms import NEQ_PREDICATE
from ..disjunctive_existential_rule import DisjunctiveExistentialRule
from .table1_rules import TRANSLATORS, neq_denial_rules
from .top_population import top_population_rules


def translate_ontology_by_label(
    ontology: Ontology,
) -> dict[str, list[DisjunctiveExistentialRule]]:
    """Like translate_ontology, but the per-axiom rules grouped by their
    Table 1 label instead of flattened into one list — one entry per
    label in Table 1 order, always present, possibly empty. Excludes the
    auxiliary top-population rules (call top_population_rules separately
    for those; they aren't tied to a single Table 1 label). Raises the
    same as translate_ontology."""
    ensure_fully_supported(ontology)
    return {
        label: [translator(ax) for ax in ontology.axiom_types.get(label, ())]
        for label, translator in TRANSLATORS.items()
    }


def translate_ontology(ontology: Ontology) -> list[DisjunctiveExistentialRule]:
    """Every rule of pi(ontology): one DisjunctiveExistentialRule per
    Table 1 - classified axiom, plus the auxiliary top-population rules and,
    if some O14 axiom has m >= 2, the neq_ denials.
    Raises UnsupportedConstructError (via ensure_fully_supported) if the
    ontology has any UNCLASSIFIED axiom or parse warning — translating a
    partially-unsupported ontology would otherwise silently drop those
    axioms instead of failing loudly."""
    ensure_fully_supported(ontology)
    rules = top_population_rules(ontology)
    for label_rules in translate_ontology_by_label(ontology).values():
        rules.extend(label_rules)
    if any(a.predicate == NEQ_PREDICATE for rule in rules for a in rule.effect):
        rules.extend(neq_denial_rules())
    return rules
