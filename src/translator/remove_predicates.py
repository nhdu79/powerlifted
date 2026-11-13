#! /usr/bin/env python
import pddl

def remove_unused_predicate_symbols(task):
    used_predicates = set()
    for a in task.actions:
        for p in a.get_action_preconditions:
            p.collect_predicates(used_predicates)
        for e in a.effects:
            e.condition.collect_predicates(used_predicates)
            used_predicates.add(e.literal.predicate)
    for ax in task.axioms:
        ax.condition.collect_predicates(used_predicates)
        used_predicates.add(ax.name)
    for p in task.init:
        used_predicates.add(p.predicate)
    task.predicates = [p for p in task.predicates if p.name in used_predicates]
