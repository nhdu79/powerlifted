"""
Regression tests for the syntax of mkos, which follows the grammar of ECQs:

    Q ::= p(x) | [q] | not Q | Q and Q | exists y. Q

where [q] is (mko q) and q is a union of conjunctive queries (UCQ):
existentials, conjunctions and disjunctions of atoms, without negation.

* A disjunction inside an mko used to crash normalize.build_DNF, which
  pulled it out of the mko. It must stay inside: [q1 or q2] is not
  [q1] or [q2]. The query is put into DNF within the mko instead.
* Negation inside an mko (other than of an equality) used to be accepted
  by the parser and fail late, sometimes as a bare AssertionError. The
  parser rejects it now.

Each test parses a domain and problem from text, normalizes the task as the
translator does, and hands its mkos to the UCQ collector (which only needs
the parser and normalize, not Clipper).

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/pddl_parser/tests/test_mko_syntax.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

import normalize  # noqa: E402
from pddl import (  # noqa: E402
    Atom,
    Conjunction,
    Disjunction,
    ExistentialCondition,
    MinimalKnowledgeOperator,
    NegatedAtom,
)
from pddl_parser.lisp_parser import parse_nested_list  # noqa: E402
from pddl_parser.parsing_functions import parse_task  # noqa: E402
from queries.ucq_collector import UCQCollector  # noqa: E402

DOMAIN = """
(define (domain team)
  (:predicates
    (Team ?x) (Player ?x) (Captain ?x) (Substitute ?x)
    (hasCaptain ?x ?y) (hasMember ?x ?y))
  (:action Recruit
    :parameters (?t ?p)
    :precondition (and %s)
    :effect (and (hasMember ?t ?p))))
"""

PROBLEM = """
(define (problem team_problem)
  (:domain team)
  (:objects red alice)
  (:init (hasCaptain red alice))
  (:goal (and (hasMember red alice))))
"""


def normalized_task(precondition):
    """The team task with Recruit's precondition (and precondition),
    parsed and normalized."""
    with contextlib.redirect_stdout(io.StringIO()):
        task = parse_task(
            parse_nested_list(io.StringIO(DOMAIN % precondition)),
            parse_nested_list(io.StringIO(PROBLEM)),
        )
        normalize.normalize(task)
    return task


def mkos(condition):
    """The mkos of condition, outermost only."""
    if isinstance(condition, MinimalKnowledgeOperator):
        return [condition]
    return [mko for part in condition.parts for mko in mkos(part)]


def collect(task):
    """The UCQs of the task's action preconditions (raises if one isn't
    a UCQ)."""
    collector = UCQCollector()
    for action in task.actions:
        for mko in mkos(action.precondition):
            collector(mko)
    return collector.ucqs


def the_query(task):
    """The query of the task's only action's only mko."""
    (action,) = task.actions
    (mko,) = mkos(action.precondition)
    (query,) = mko.parts
    return query


class DisjunctionInsideMkoTest(unittest.TestCase):
    def test_union_stays_inside_the_mko(self):
        task = normalized_task("(mko (or (Captain ?p) (Substitute ?p)))")
        # Not split into one action per disjunct.
        self.assertEqual(len(task.actions), 1)
        self.assertEqual(
            the_query(task),
            Disjunction([Atom("captain", ["?p"]), Atom("substitute", ["?p"])]),
        )
        self.assertEqual(len(collect(task)), 1)

    def test_conjunction_over_union_becomes_a_union_of_cqs(self):
        task = normalized_task("(mko (and (Team ?t) (or (Player ?p) (Captain ?p))))")
        self.assertEqual(len(task.actions), 1)
        query = the_query(task)
        self.assertIsInstance(query, Disjunction)
        self.assertEqual(
            {frozenset(cq.parts) for cq in query.parts},
            {
                frozenset([Atom("team", ["?t"]), Atom("player", ["?p"])]),
                frozenset([Atom("team", ["?t"]), Atom("captain", ["?p"])]),
            },
        )
        self.assertTrue(all(isinstance(cq, Conjunction) for cq in query.parts))
        self.assertEqual(len(collect(task)), 1)

    def test_existential_over_union_is_distributed(self):
        task = normalized_task(
            "(mko (exists (?y) (or (hasMember ?t ?y) (hasCaptain ?t ?y))))"
        )
        self.assertEqual(len(task.actions), 1)
        query = the_query(task)
        self.assertIsInstance(query, Disjunction)
        self.assertTrue(
            all(isinstance(cq, ExistentialCondition) for cq in query.parts)
        )
        self.assertEqual(
            {cq.parts[0].predicate for cq in query.parts},
            {"hasmember", "hascaptain"},
        )
        self.assertEqual(len(collect(task)), 1)

    def test_disjunction_outside_still_splits_the_action(self):
        task = normalized_task("(or (Team ?t) (mko (or (Captain ?p) (Substitute ?p))))")
        # One action per disjunct outside the mko; the mko's union is kept.
        self.assertEqual(len(task.actions), 2)
        queries = [
            mko.parts[0]
            for action in task.actions
            for mko in mkos(action.precondition)
        ]
        self.assertEqual(
            queries,
            [Disjunction([Atom("captain", ["?p"]), Atom("substitute", ["?p"])])],
        )

    def test_negated_mko_of_a_union(self):
        task = normalized_task("(not (mko (or (Captain ?p) (Substitute ?p))))")
        (action,) = task.actions
        (mko,) = mkos(action.precondition)
        self.assertTrue(mko.negated)
        self.assertIsInstance(mko.parts[0], Disjunction)


class NegationInsideMkoTest(unittest.TestCase):
    def assert_rejected(self, precondition):
        with self.assertRaises(SystemExit) as raised:
            normalized_task(precondition)
        self.assertIn("negation inside an mko", str(raised.exception))

    def test_negated_atom_is_rejected(self):
        self.assert_rejected("(mko (not (Player ?p)))")

    def test_negated_conjunct_is_rejected(self):
        self.assert_rejected("(mko (and (Team ?t) (not (Player ?p))))")

    def test_negated_conjunction_is_rejected(self):
        # In negation normal form a disjunction of negated atoms; used to
        # crash build_DNF.
        self.assert_rejected("(mko (not (and (Team ?t) (Player ?p))))")

    def test_negated_existential_is_rejected(self):
        self.assert_rejected("(mko (not (exists (?y) (hasMember ?t ?y))))")

    def test_negated_equality_is_accepted(self):
        task = normalized_task("(mko (not (= ?t ?p)))")
        self.assertEqual(the_query(task), NegatedAtom("=", ["?t", "?p"]))

    def test_negated_mko_is_accepted(self):
        task = normalized_task("(not (mko (and (Team ?t) (Player ?p))))")
        (action,) = task.actions
        (mko,) = mkos(action.precondition)
        self.assertTrue(mko.negated)


if __name__ == "__main__":
    unittest.main()
