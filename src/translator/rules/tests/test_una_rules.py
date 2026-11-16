"""
Regression tests for rules.una_rules.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/tests/test_una_rules.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from pddl.conditions import Atom  # noqa: E402

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.una_rules import una_rules  # noqa: E402


def _denial(a, b):
    return DisjunctiveExistentialRule(effect=(), body=(Atom("=", (a, b)),))


class UnaRulesTest(unittest.TestCase):
    def test_every_ordered_pair_of_distinct_constants_is_bottom(self):
        self.assertEqual(
            una_rules(["a", "b", "c"]),
            [
                _denial("a", "b"),
                _denial("a", "c"),
                _denial("b", "a"),
                _denial("b", "c"),
                _denial("c", "a"),
                _denial("c", "b"),
            ],
        )

    def test_repeated_constants_count_once(self):
        self.assertEqual(una_rules(["a", "b", "a"]), una_rules(["a", "b"]))

    def test_fewer_than_two_constants_need_no_rule(self):
        self.assertEqual(una_rules([]), [])
        self.assertEqual(una_rules(["a"]), [])


if __name__ == "__main__":
    unittest.main()
