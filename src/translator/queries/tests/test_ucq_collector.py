"""
Regression tests for queries.ucq_collector.UCQCollector.replacement: an mko
becomes a literal over the same predicate, flagged mko (no DATALOG_ copy).

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/queries/tests/test_ucq_collector.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from pddl import (  # noqa: E402
    Atom,
    Conjunction,
    Disjunction,
    ExistentialCondition,
    MinimalKnowledgeOperator,
    NegatedAtom,
    TypedObject,
)
from queries.ucq_collector import UCQCollector  # noqa: E402
from rules import DisjunctiveExistentialRule  # noqa: E402


def _replace(*mkos):
    """Collect every mko, then return the replacement of each."""
    collector = UCQCollector()
    for mko in mkos:
        collector(mko)
    collector.number_queries()
    return [collector.replacement(mko) for mko in mkos]


class ReplacementTest(unittest.TestCase):
    def test_single_atom_keeps_its_predicate_and_is_flagged(self):
        mko = MinimalKnowledgeOperator([Atom("p", ("?x",))], negated=False)

        (literal,) = _replace(mko)

        self.assertEqual(literal, Atom("p", ("?x",), mko=True))

    def test_negated_mko_stays_flagged(self):
        mko = MinimalKnowledgeOperator([Atom("p", ("?x",))], negated=True)

        (literal,) = _replace(mko)

        self.assertEqual(literal, NegatedAtom("p", ("?x",), mko=True))

    def test_equality_is_read_without_the_flag(self):
        mko = MinimalKnowledgeOperator([Atom("=", ("?x", "?y"))], negated=True)

        (literal,) = _replace(mko)

        self.assertEqual(literal, NegatedAtom("=", ("?x", "?y")))
        self.assertFalse(literal.mko)

    def test_query_reads_its_flagged_query_predicate(self):
        query = Conjunction([Atom("p", ("?x",)), Atom("r", ("?x", "?y"))])
        mko = MinimalKnowledgeOperator([query], negated=False)

        (literal,) = _replace(mko)

        self.assertEqual(literal, Atom("QUERY0", ("?x", "?y"), mko=True))


class LiteralFlagTest(unittest.TestCase):
    def test_flag_distinguishes_otherwise_equal_literals(self):
        plain, flagged = Atom("p", ("?x",)), Atom("p", ("?x",), mko=True)

        self.assertNotEqual(plain, flagged)
        self.assertEqual(len({plain, flagged}), 2)

    def test_flag_survives_negation_and_renaming(self):
        flagged = Atom("p", ("?x",), mko=True)

        self.assertTrue(flagged.negate().mko)
        self.assertTrue(flagged.negate().positive().mko)
        self.assertTrue(flagged.rename_variables({"?x": "?y"}).mko)


def _collector(*mkos):
    collector = UCQCollector()
    for mko in mkos:
        collector(mko)
    collector.number_queries()
    return collector


class QueryRulesTest(unittest.TestCase):
    def test_conjunctive_query_derives_its_query_atom_as_replacement_reads_it(self):
        query = Conjunction([Atom("r", ("?y", "?x")), Atom("p", ("?x",))])
        mko = MinimalKnowledgeOperator([query], negated=False)
        collector = _collector(mko)

        (rule,) = collector.query_rules()

        # The head is the unflagged atom replacement reads, same argument order.
        self.assertEqual(rule.effect, (Atom("QUERY0", ("?x", "?y")),))
        self.assertEqual(rule.effect[0].args, collector.replacement(mko).args)
        self.assertEqual(rule.body, (Atom("r", ("?y", "?x")), Atom("p", ("?x",))))

    def test_one_rule_per_disjunct(self):
        ucq = Disjunction([Atom("p", ("?x",)), Atom("q", ("?x",))])
        collector = _collector(MinimalKnowledgeOperator([ucq], negated=False))

        self.assertEqual(
            collector.query_rules(),
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("QUERY0", ("?x",)),), body=(Atom("p", ("?x",)),)
                ),
                DisjunctiveExistentialRule(
                    effect=(Atom("QUERY0", ("?x",)),), body=(Atom("q", ("?x",)),)
                ),
            ],
        )

    def test_boolean_query_has_a_nullary_head(self):
        query = ExistentialCondition(
            [TypedObject("?y", "object")],
            [Conjunction([Atom("p", ("?y",)), Atom("r", ("?y", "?y"))])],
        )
        collector = _collector(MinimalKnowledgeOperator([query], negated=True))

        self.assertEqual(
            collector.query_rules(),
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("QUERY0", ()),),
                    body=(Atom("p", ("?y",)), Atom("r", ("?y", "?y"))),
                )
            ],
        )

    def test_single_atom_mkos_need_no_query_rule(self):
        collector = _collector(MinimalKnowledgeOperator([Atom("p", ("?x",))], negated=False))

        self.assertEqual(collector.query_rules(), [])


if __name__ == "__main__":
    unittest.main()
