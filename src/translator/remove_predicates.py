#! /usr/bin/env python
import pddl

# TODO: we will have to adapt this to axioms and conditional effects.
# Why is the goal not considered?
def remove_unused_predicate_symbols(task):
    used_predicates = set()
    used_predicates2 = set()
    for a in task.actions:
        for p in a.get_action_preconditions:
            p.collect_predicates(used_predicates)
        for e in a.effects:
            l = e.literal
            pred = l.predicate
            used_predicates.add(pred)
    for p in task.init:
        pred = p.predicate
        used_predicates.add(pred)
    new_predicates = []
    for pred in task.predicates:
        if pred.name in used_predicates:
            new_predicates.append(pred)
    task.predicates = new_predicates
