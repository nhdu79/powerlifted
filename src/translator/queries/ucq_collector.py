import contextlib
import io

from pddl import Atom, Conjunction, Disjunction, ExistentialCondition, Literal
from rules import DisjunctiveExistentialRule
from rules.atoms import EQUALITY_PREDICATE

from .naming import query_predicate_name


def _is_cq(condition):
    if isinstance(condition, ExistentialCondition):
        (condition,) = condition.parts
    if isinstance(condition, Conjunction):
        return all(isinstance(part, Literal) for part in condition.parts)
    return isinstance(condition, Literal)


def _check_ucq(formula):
    """Raise NotImplementedError unless formula is a union of conjunctive
    queries over a common set of free variables, the shape
    queries.rewriter hands to Clipper."""
    cqs = formula.parts if isinstance(formula, Disjunction) else (formula,)
    if not all(_is_cq(cq) for cq in cqs):
        raise NotImplementedError(
            "mko queries must be unions of conjunctive queries after "
            "normalization; got:\n" + _dumped(formula)
        )
    if len({frozenset(cq.free_variables()) for cq in cqs}) > 1:
        raise NotImplementedError(
            "all disjuncts of an mko query must have the same free "
            "variables; got:\n" + _dumped(formula)
        )


def _dumped(condition):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        condition.dump()
    return out.getvalue()


class UCQCollector:
    """Collects the query of every mko (mirrors pddl-horndl's
    compilation/ucq_collector.py).

    pddl-horndl replaces each mko right away and repairs the replacement
    once the rules are known; here collecting and replacing are two
    separate calls, as the queries must be numbered (number_queries) first.
    """

    def __init__(self):
        self.ucqs = []
        self.queried_predicates = set()
        self._query_ids = {}  # query formula -> index into self.ucqs

    def __call__(self, mko):
        (formula,) = mko.parts
        if isinstance(formula, Literal):
            if formula.negated and formula.predicate != EQUALITY_PREDICATE:
                raise NotImplementedError(
                    f"negated atoms inside an mko are not supported: {formula}"
                )
            # A single atom needs no query of its own: its predicate is
            # read directly, see replacement.
            if formula.predicate != EQUALITY_PREDICATE:
                self.queried_predicates.add(formula.predicate)
        elif formula not in self._query_ids:
            _check_ucq(formula)
            # Syntactically identical mkos (e.g. a positive and a negated
            # one) share one query.
            self._query_ids[formula] = len(self.ucqs)
            self.ucqs.append(formula)

    def number_queries(self):
        """Renumber the queries by their rendering, so QUERY<i> doesn't
        depend on the order the mkos were visited in (which follows set
        iteration, e.g. normalize.remove_duplicated_preconditions, and so
        the hash seed). Call once all mkos are collected."""
        self.ucqs.sort(key=_dumped)
        self._query_ids = {formula: i for i, formula in enumerate(self.ucqs)}

    def replacement(self, mko):
        """The literal mko stands for: the same predicate (no primed copy),
        flagged mko=True, so the search evaluates it w.r.t. the lowerbound
        rules instead of the state.

        A single-atom mko reads its own atom. (In)equality is the exception:
        under the unique name assumption, mko(= ?x ?y) is just (= ?x ?y),
        read without the flag. Any other mko reads QUERY<i> over its free
        variables, in the order queries.rewriter gives them to Clipper.
        """
        (formula,) = mko.parts
        if isinstance(formula, Literal):
            literal = formula.__class__(
                formula.predicate,
                formula.args,
                mko=formula.predicate != EQUALITY_PREDICATE,
            )
        else:
            name = query_predicate_name(self._query_ids[formula])
            literal = Atom(name, sorted(formula.free_variables()), mko=True)
        return literal.negate() if mko.negated else literal

    def query_rules(self):
        """The query of every QUERY<i> as rules, one per conjunctive query:
        cq → QUERY<i>(free variables), with the head's arguments in the
        order replacement reads them. Clipper rewrites the queries for the
        lowerbound itself; these are for the upperbound. Call once the
        queries are numbered (number_queries)."""
        rules = []
        for i, ucq in enumerate(self.ucqs):
            head = Atom(query_predicate_name(i), sorted(ucq.free_variables()))
            for cq in ucq.parts if isinstance(ucq, Disjunction) else (ucq,):
                if isinstance(cq, ExistentialCondition):
                    (cq,) = cq.parts
                atoms = cq.parts if isinstance(cq, Conjunction) else (cq,)
                body = tuple(Atom(a.predicate, a.args) for a in atoms)
                rules.append(DisjunctiveExistentialRule(effect=(head,), body=body))
        return rules
