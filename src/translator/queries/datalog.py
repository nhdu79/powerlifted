"""
Post-processing of the rules Clipper returns for the ontology and the mko
queries (mirrors pddl-horndl's compilation/datalog.py and Compiler.
_compile_datalog_rules), on DisjunctiveExistentialRule objects instead of
pddl-horndl's raw rule strings and derived predicates.

Every step here works in the task's spelling, i.e. after rename_rules.
"""

from pddl import Atom, Predicate, TypedObject
from rules import DisjunctiveExistentialRule
from rules.atoms import EQUALITY_PREDICATE

from .naming import get_query_id, prime_predicate_name, query_predicate_name


def _map_predicates(rule, fn):
    def atom(a):
        return a.__class__(fn(a.predicate), a.args)

    return DisjunctiveExistentialRule(
        effect=tuple(atom(a) for a in rule.effect),
        body=tuple(atom(a) for a in rule.body),
    )


def rename_rules(rules, spelling):
    """Translate every predicate from Clipper's spelling into the task's (see
    queries.names.ClipperSpelling)."""
    return [_map_predicates(rule, spelling.to_pddl) for rule in rules]


def deduplicate_rules(rules, unparameterized):
    """Drop repeated rules, and the dummy argument Clipper gets for queries
    without free variables (see queries.rewriter._format_cq).

    Returns (rules, duplicate_rules), both in Clipper's order.
    """
    # A dict (not a set) deduplicates while keeping Clipper's rule order, so
    # the output does not depend on string hash randomisation.
    unique = {}
    duplicates = []
    for rule in rules:
        if rule.effect and get_query_id(rule.effect[0].predicate) in unparameterized:
            rule = DisjunctiveExistentialRule(
                effect=(Atom(rule.effect[0].predicate, ()),), body=rule.body
            )
        if rule in unique:
            duplicates.append(rule)
            continue
        unique[rule] = None
    return list(unique), duplicates


def _positive_body_predicates(rule):
    return {
        a.predicate
        for a in rule.body
        if not a.negated and a.predicate != EQUALITY_PREDICATE
    }


def filter_unreachable_rules(rules, reachable_predicates):
    """Keep the rules that can fire: seeded with reachable_predicates (the
    predicates of the initial state and of action effects), a rule is
    reachable once all its positive body predicates are, and then so are
    its effect predicates.

    Returns (reachable_rules, unreachable_rules), both in input order.
    """
    reachable = set(reachable_predicates)
    kept = set()
    changed = True
    while changed:
        changed = False
        for i, rule in enumerate(rules):
            if i not in kept and _positive_body_predicates(rule) <= reachable:
                kept.add(i)
                reachable |= {a.predicate for a in rule.effect}
                changed = True
    return (
        [r for i, r in enumerate(rules) if i in kept],
        [r for i, r in enumerate(rules) if i not in kept],
    )


def filter_irrelevant_rules(rules, queried_predicates, num_ucqs):
    """Remove rules whose effects cannot contribute to anything the compiled
    task reads.

    Backward reachability from the queried atoms and the QUERY<i> heads; a
    denial (empty effect, i.e. bottom) is always relevant, as it's what
    detects inconsistency. The body predicates of relevant rules become
    needed in turn.

    Returns (relevant_rules, irrelevant_rules), both in input order.
    """
    needed = set(queried_predicates)
    needed |= {query_predicate_name(i) for i in range(num_ucqs)}

    def is_relevant(rule):
        return not rule.effect or any(a.predicate in needed for a in rule.effect)

    changed = True
    while changed:
        changed = False
        for rule in rules:
            if not is_relevant(rule):
                continue
            for name in _positive_body_predicates(rule):
                if name not in needed:
                    needed.add(name)
                    changed = True

    relevant, irrelevant = [], []
    for rule in rules:
        (relevant if is_relevant(rule) else irrelevant).append(rule)
    return relevant, irrelevant


def derived_predicates(rules):
    """Every predicate some rule derives."""
    return {a.predicate for rule in rules for a in rule.effect}


def compile_rules(rules, task_predicates):
    """Separate what the ontology entails from what the state holds.

    Every derived predicate P is primed (DATALOG_P) wherever it occurs, so
    the rules never write into the task's own predicates; a predicate no
    rule derives is read straight from the state. For a derived P that is
    also a task predicate, a copy rule P(x..) -> DATALOG_P(x..) feeds the
    state's P-atoms into the primed version.

    Returns (rules, new_predicates): the compiled rules and the
    pddl.Predicate declarations of the primed predicates.
    """
    derived = derived_predicates(rules)
    arity = {}

    def prime(a):
        if a.predicate not in derived:
            return a
        arity[a.predicate] = len(a.args)
        return a.__class__(prime_predicate_name(a.predicate), a.args)

    compiled = [
        DisjunctiveExistentialRule(
            effect=tuple(prime(a) for a in rule.effect),
            body=tuple(prime(a) for a in rule.body),
        )
        for rule in rules
    ]

    task_arity = {p.name: len(p.arguments) for p in task_predicates}
    for name in sorted(derived & set(task_arity)):
        args = tuple(f"?x{i}" for i in range(task_arity[name]))
        compiled.append(
            DisjunctiveExistentialRule(
                effect=(Atom(prime_predicate_name(name), args),),
                body=(Atom(name, args),),
            )
        )

    return compiled, [primed_predicate(name, arity[name]) for name in sorted(arity)]


def primed_predicate(name, arity):
    """Declaration of DATALOG_<name>, with untyped arguments."""
    return Predicate(
        prime_predicate_name(name),
        [TypedObject(f"?x{i}", "object") for i in range(arity)],
    )
