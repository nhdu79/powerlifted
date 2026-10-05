"""
Post-processing of the rules Clipper returns for the ontology and the mko
queries (mirrors pddl-horndl's compilation/datalog.py and Compiler.
_compile_datalog_rules), on DisjunctiveExistentialRule objects instead of
pddl-horndl's raw rule strings and derived predicates.

Every step here works in the task's spelling, i.e. after rename_rules.
"""

from pddl import Atom, Predicate, TypedObject
from rules import DisjunctiveExistentialRule, una_rules
from rules.atoms import EQUALITY_PREDICATE

from .naming import get_query_id, query_predicate_name


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


def _is_inequality(atom):
    return atom.negated and atom.predicate == EQUALITY_PREDICATE


def move_inequalities_to_effect(rules):
    """Rewrite each denial y ≠ z ∧ B → ⊥ (e.g. Clipper's rewriting of a
    functionality or at-most-one restriction) as B → y = z, as the search
    doesn't support negated atoms.

    Both are the same formula (¬(y ≠ z ∧ B) ≡ B → y = z); the derived y = z
    is an inconsistency for distinct constants once the UNA rules are added
    (see lowerbound_una_rules), and harmless for y = z. A rule with x ≠ x is
    dropped, as its body never holds.

    Raises ValueError for an inequality in a rule with a non-empty effect, or
    for several inequalities in one rule (that would need a disjunction of
    equalities over different arguments, which the search doesn't support).
    """
    rewritten = []
    for rule in rules:
        inequalities = [a for a in rule.body if _is_inequality(a)]
        if not inequalities:
            rewritten.append(rule)
            continue
        if rule.effect or len(inequalities) > 1:
            raise ValueError(
                "only denials with a single inequality are supported: "
                f"{rule}"
            )
        left, right = inequalities[0].args
        if left == right:
            continue
        rewritten.append(
            DisjunctiveExistentialRule(
                effect=(Atom(EQUALITY_PREDICATE, (left, right)),),
                body=tuple(a for a in rule.body if not _is_inequality(a)),
            )
        )
    return rewritten


def _derives_equality(rule):
    return any(a.predicate == EQUALITY_PREDICATE for a in rule.effect)


def lowerbound_una_rules(rules, constants):
    """The UNA rules (rules.una_rules) over constants if some rule derives
    "=" (see move_inequalities_to_effect), else none."""
    if any(_derives_equality(rule) for rule in rules):
        return una_rules(constants)
    return []


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
    detects inconsistency, and so is a rule deriving "=" (a denial under UNA,
    see move_inequalities_to_effect). The body predicates of relevant rules
    become needed in turn.

    Returns (relevant_rules, irrelevant_rules), both in input order.
    """
    needed = set(queried_predicates)
    needed |= {query_predicate_name(i) for i in range(num_ucqs)}

    def is_relevant(rule):
        return (
            not rule.effect
            or _derives_equality(rule)
            or any(a.predicate in needed for a in rule.effect)
        )

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


def predicate_declarations(rules, task_predicates):
    """pddl.Predicate declarations, with untyped arguments, of the predicates
    the rules use that the task doesn't declare (e.g. the QUERY<i> heads and
    the ontology's own and generated names), in name order.

    Rules read and derive the task's predicates under their own names: the
    search tells an mko-flagged atom (evaluated w.r.t. the rules) apart from
    a plain one (evaluated on the state), so no primed copy is needed.
    """
    declared = {p.name for p in task_predicates}
    arity = {}
    for rule in rules:
        for a in rule.body + rule.effect:
            if a.predicate not in declared and a.predicate != EQUALITY_PREDICATE:
                arity[a.predicate] = len(a.args)
    return [untyped_predicate(name, arity[name]) for name in sorted(arity)]


def untyped_predicate(name, arity):
    """Declaration of name, with untyped arguments."""
    return Predicate(name, [TypedObject(f"?x{i}", "object") for i in range(arity)])
