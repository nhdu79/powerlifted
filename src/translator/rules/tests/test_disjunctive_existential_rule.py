"""
Regression tests for rules.disjunctive_existential_rule.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/tests/test_disjunctive_existential_rule.py

from anywhere (the `owl`/`pddl`/`rules` package paths are resolved
relative to this file, not the current working directory).
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

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402


class DisjunctiveExistentialRuleTest(unittest.TestCase):
    def test_fields_round_trip(self):
        body = (Atom("edge", ("?x", "?y")),)
        effect = (Atom("node", ("?x",)),)
        rule = DisjunctiveExistentialRule(effect=effect, body=body)
        self.assertEqual(rule.body, body)
        self.assertEqual(rule.effect, effect)

    def test_empty_effect_represents_bottom(self):
        body = (Atom("a", ("?x",)), Atom("b", ("?x",)))
        rule = DisjunctiveExistentialRule(effect=(), body=body)
        self.assertEqual(rule.effect, ())

    def test_effect_accepts_negated_atoms(self):
        # A negated effect atom (e.g. an inequality) is a NegatedAtom.
        rule = DisjunctiveExistentialRule(
            effect=(NegatedAtom("=", ("?y1", "?y2")),),
            body=(Atom("a", ("?x",)),),
        )
        self.assertIsInstance(rule.effect[0], NegatedAtom)

    def test_frozen_and_hashable(self):
        rule = DisjunctiveExistentialRule(
            effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
        )
        with self.assertRaises(Exception):
            rule.body = ()
        hash(rule)  # must not raise

    def test_equal_rules_compare_equal(self):
        rule1 = DisjunctiveExistentialRule(
            effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
        )
        rule2 = DisjunctiveExistentialRule(
            effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
        )
        self.assertEqual(rule1, rule2)


if __name__ == "__main__":
    unittest.main()
