"""
Regression tests for queries.datalog's rewriting of Clipper's inequality
denials (move_inequalities_to_effect, lowerbound_una_rules) and for keeping
the rewritten rules through filter_irrelevant_rules.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/queries/tests/test_datalog.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from pddl.conditions import Atom, NegatedAtom  # noqa: E402
from queries.datalog import (  # noqa: E402
    filter_irrelevant_rules,
    lowerbound_una_rules,
    move_inequalities_to_effect,
)
from rules import DisjunctiveExistentialRule, una_rules  # noqa: E402

# team.owl's at-most-one-captain denial, as Clipper returns it.
BODY = (
    Atom("team", ("?x",)),
    Atom("hascaptain", ("?x", "?z")),
    Atom("hascaptain", ("?x", "?y")),
)
DENIAL = DisjunctiveExistentialRule(
    effect=(), body=(NegatedAtom("=", ("?y", "?z")),) + BODY
)
REWRITTEN = DisjunctiveExistentialRule(effect=(Atom("=", ("?y", "?z")),), body=BODY)


class MoveInequalitiesToEffectTest(unittest.TestCase):
    def test_denial_becomes_equality_rule(self):
        self.assertEqual(move_inequalities_to_effect([DENIAL]), [REWRITTEN])

    def test_other_rules_unchanged(self):
        rules = [
            DisjunctiveExistentialRule(effect=(Atom("player", ("?y",)),), body=BODY),
            DisjunctiveExistentialRule(effect=(), body=BODY),
        ]
        self.assertEqual(move_inequalities_to_effect(rules), rules)

    def test_trivial_inequality_dropped(self):
        rule = DisjunctiveExistentialRule(
            effect=(), body=(NegatedAtom("=", ("?x", "?x")),) + BODY
        )
        self.assertEqual(move_inequalities_to_effect([rule]), [])

    def test_inequality_with_effect_rejected(self):
        rule = DisjunctiveExistentialRule(
            effect=(Atom("player", ("?y",)),), body=DENIAL.body
        )
        with self.assertRaises(ValueError):
            move_inequalities_to_effect([rule])

    def test_several_inequalities_rejected(self):
        rule = DisjunctiveExistentialRule(
            effect=(), body=(NegatedAtom("=", ("?x", "?y")),) + DENIAL.body
        )
        with self.assertRaises(ValueError):
            move_inequalities_to_effect([rule])


class LowerboundUnaRulesTest(unittest.TestCase):
    def test_added_when_equality_derived(self):
        self.assertEqual(
            lowerbound_una_rules([REWRITTEN], ["a", "b"]), una_rules(["a", "b"])
        )

    def test_none_without_equality(self):
        self.assertEqual(lowerbound_una_rules([DENIAL], ["a", "b"]), [])


class FilterIrrelevantRulesTest(unittest.TestCase):
    def test_equality_rule_is_relevant(self):
        relevant, irrelevant = filter_irrelevant_rules([REWRITTEN], set(), 0)
        self.assertEqual((relevant, irrelevant), ([REWRITTEN], []))


if __name__ == "__main__":
    unittest.main()
