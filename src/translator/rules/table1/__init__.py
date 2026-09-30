from rules.table1.ontology_rules import translate_ontology, translate_ontology_by_label
from rules.table1.table1_rules import neq_denial_rules, translate_axiom
from rules.table1.top_population import top_population_rules

__all__ = [
    "neq_denial_rules",
    "top_population_rules",
    "translate_axiom",
    "translate_ontology",
    "translate_ontology_by_label",
]
