#! /usr/bin/env python

from collections import defaultdict

import pddl

## Preprocess object types of the task.
## The following operations are performed:
##
##   - Compile types into unary predicates;
##   - Add unary type predicates as action preconditions;
##   - Replace types in MKO existential quantifiers with unary predicate;
##   - Add unary type and supertype predicates to initial state;
##   - Remove types from action parameters (see comment in __str__ of
# TypedObject);

name_to_type_pred = {}


class TypesGraph(object):
    """
    Create a graph representing the hierarchy of types and supertypes.  Every
    type points to its supertype.
    """

    def __init__(self, types):
        # self.type is list of types and self.edges is a dictionary where
        # each type points to its supertype.
        self.types = types
        self.edges = self.create_graph(self.types)

    def create_graph(self, types):
        g = defaultdict(str)
        for t in types:
            g[t.name] = t.basetype_name
        return g


def compile_into_unary_predicates(task):
    """Create one new unary predicate for each object type."""
    for t in task.types:
        type = str(t)
        pred_name = _get_type_predicate_name(type)
        task.predicates.append(pddl.Predicate(pred_name, [pddl.TypedObject('?x', type)]))
        name_to_type_pred[pred_name] = task.predicates[-1]
    return

def add_conditions_to_actions(task, graph):
    """Add unary type conditions to each action schema according to their
    parameters.

    """
    for action in task.actions:
        # types set by axiom parameters (covering the variables)
        terms_in_action = set((param.type_name, param.name) for param in action.parameters)

        # types induced by objects occuring in the precondition
        objects = set()
        action.precondition.collect_objects(objects)

        for effect in action.effects:
            effect.condition.collect_objects(objects)
        objects.update(arg for arg in effect.literal.args if arg[0] != "?")

        if objects:
            type_by_obj_name = {x.name: x.type_name for x in task.objects}
            terms_in_action.update((type_by_obj_name[name], name) for name in objects)

        condition = [pddl.Atom(_get_type_predicate_name(param_type), [name])
                                for param_type, name in terms_in_action]
        condition.append(action.precondition)
        action.precondition = pddl.Conjunction(condition).simplified()

def add_conditions_to_axioms(task, graph):
    """Add unary type conditions to each axiom schema according to their
    parameters.

    """
    for axiom in task.axioms:
        # types set by axiom parameters (covering the variables)
        terms_in_axiom = set((param.type_name, param.name) for param in axiom.parameters)

        # types induced by objects occuring in the body
        objects = set()
        axiom.condition.collect_objects(objects)
        if objects:
            type_by_obj_name = {x.name: x.type_name for x in task.objects}
            terms_in_axiom.update((type_by_obj_name[name], name) for name in objects)

        condition = [pddl.Atom(_get_type_predicate_name(param_type), [name])
                                for param_type, name in terms_in_axiom]
        condition.append(axiom.condition)
        axiom.condition = pddl.Conjunction(condition).simplified()
    return

def add_effects_to_actions(task, graph):
    """
    Add type predicates to effect of actions with object creation effects.
    """
    for action in task.actions:
        new_eff = action.effects
        new_vars = set()
        for effect in action.effects:
            new_vars = new_vars.union(set(effect.parameters))
        types = set()
        for typed_obj in new_vars:
            name = typed_obj.name
            type_name = typed_obj.type_name
            while type_name != 'object':
                types.add(type_name)
                type_name = graph.edges[type_name]
            if type_name == 'object' and typed_obj not in action.parameters:
                # If this is a fresh variable, we need to add it to the type-object
                # predicate in its effect.
                types.add(type_name)
            for t in types:
                atom = pddl.Atom(_get_type_predicate_name(t), [name])
                new_eff.append(pddl.Effect([], pddl.Truth(), atom))
        action.effects = new_eff


def adjust_initial_state(task, graph):
    """Creates the unary predicates for types and supertypes of each object and
    append them to the initial state description.

    """
    for obj in task.objects:
        type_name = obj.type_name
        name = obj.name
        types = set()
        types.add(type_name)
        while type_name != 'object':
            # While there is a supertype, append this to the list of predicates
            # being added in the initial state.
            types.add(type_name)
            type_name = graph.edges[type_name]
        for t in types:
            task.init.append(pddl.Atom(_get_type_predicate_name(t), [name]))


def _get_type_predicate_name(t):
    return 'type@' + t


def remove_trivially_inapplicable_actions(task, graph):
    """
    Remove actions that are never instantiated.  This occurs once a parameter
    has a given type T but there is no object with such parameter.

    :param task:
    :param graph:
    :return:
    """
    object_types_in_task = set()
    for obj in task.objects:
        type_name = obj.type_name
        object_types_in_task.add(type_name)
        while type_name != 'object':
            # While there is a supertype, append this to the list of types
            # appearing in any object of the task
            object_types_in_task.add(type_name)
            type_name = graph.edges[type_name]

    new_actions = set()
    for action in task.actions:
        keep_action = True
        for param in action.parameters:
            if param.type_name not in object_types_in_task:
                keep_action = False
        if keep_action:
            new_actions.add(action)
        else:
            print ("Removing action %s" % action.name)

    task.actions = new_actions

def compile_types(task):
    """
    Compile types into static unary predicates, modify the precondition of
    actions and the initial state accordingly.

    It also creates a graph where each node is a type and it has an outgoing
    edge to its unique supertype.

    :param task: STRIPS task
    :return: void
    """
    graph = TypesGraph(task.types)
    compile_into_unary_predicates(task)
    add_conditions_to_actions(task, graph)
    add_conditions_to_axioms(task, graph)
    add_effects_to_actions(task, graph)
    adjust_initial_state(task, graph)
    return graph
