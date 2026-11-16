from pddl import Conjunction, Disjunction, ExistentialCondition, Literal
from rules.atoms import EQUALITY_PREDICATE

from .naming import query_predicate_name


def _format_cq(query_id, cq, spelling):
    """Format a single conjunctive query as a Clipper-compatible Datalog string.

    spelling maps each PDDL predicate name to the name Clipper knows.

    Returns (formatted_string, is_unparameterized).
    """
    free_vars = sorted(cq.free_variables())
    has_free_vars = bool(free_vars)
    if has_free_vars:
        var_map = {x: f"?{i}" for i, x in enumerate(free_vars)}
        next_idx = len(free_vars)
    else:
        var_map = {}
        next_idx = 1
    if isinstance(cq, ExistentialCondition):
        # Clipper knows nothing about PDDL types, so a typed quantified
        # variable would silently lose its type restriction in the rewriting.
        typed = [
            f"{par.name} - {par.type_name}"
            for par in cq.parameters
            if par.type_name not in (None, "object")
        ]
        if typed:
            raise NotImplementedError(
                f"Typed variables inside an mko query are not supported "
                f"({', '.join(typed)}); express the type as an ontology "
                f"concept instead."
            )
        # Inner formula is always of length 1
        cq = cq.parts[0]
        for x in sorted(cq.free_variables()):
            if x not in var_map:
                var_map[x] = f"?{next_idx}"
                next_idx += 1
    elements = cq.parts if isinstance(cq, Conjunction) else [cq]
    for f in elements:
        if f.predicate == EQUALITY_PREDICATE or f.negated:
            raise NotImplementedError(
                f"Only positive, non-equality atoms are supported inside an "
                f"mko query, got {f}."
            )
    head = (
        f"{query_predicate_name(query_id)}"
        f"({','.join(var_map[x] for x in free_vars) if has_free_vars else '?0'})"
    )
    tail = [
        f"{spelling(f.predicate)}({','.join(var_map.get(t, t) for t in f.args)})"
        for f in elements
    ]
    return f"{head} <- {', '.join(tail)}", not has_free_vars


def query_atoms(ucqs):
    """{predicate name: arity} of every atom occurring in the UCQs."""
    atoms = {}

    def record(condition):
        if isinstance(condition, Literal):
            atoms[condition.predicate] = len(condition.args)
        else:
            for part in condition.parts:
                record(part)

    for ucq in ucqs:
        record(ucq)
    return atoms


def prepare_queries(ucqs, spelling=lambda name: name):
    """Format PDDL UCQs as Clipper-compatible Datalog query strings.

    Returns:
        queries: per-UCQ list of formatted CQ strings
        unparameterized: set of UCQ indices with no free variables
    """
    queries = []
    unparameterized = set()
    for idx, ucq in enumerate(ucqs):
        cqs = ucq.parts if isinstance(ucq, Disjunction) else [ucq]
        group = []
        for cq in cqs:
            formatted, is_unparameterized = _format_cq(idx, cq, spelling)
            group.append(formatted)
            if is_unparameterized:
                unparameterized.add(idx)
        queries.append(group)
    return queries, unparameterized
