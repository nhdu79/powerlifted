"""
Regression tests for rules.equality_rules — the axioms of equality
(EQ1)-(EQ4), Zhou et al. 2015, page 4.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/tests/test_equality_rules.py
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

from rules.atoms import existential_variables  # noqa: E402
from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.equality_rules import equality_rules, rule_arities  # noqa: E402


def _rule(effect, *body):
    return DisjunctiveExistentialRule(effect=(effect,), body=body)


def _eq(a, b):
    return Atom("=", (a, b))


SYMMETRY = _rule(_eq("?y", "?x"), _eq("?x", "?y"))
TRANSITIVITY = _rule(_eq("?x", "?z"), _eq("?x", "?y"), _eq("?y", "?z"))


class EqualityRulesTest(unittest.TestCase):
    def test_binary_predicate_gets_eq1_and_eq4_per_argument(self):
        r = Atom("r", ("?x1", "?x2"))
        self.assertEqual(
            equality_rules({"r": 2}),
            [
                SYMMETRY,
                TRANSITIVITY,
                _rule(_eq("?x1", "?x1"), r),
                _rule(Atom("r", ("?y", "?x2")), r, _eq("?x1", "?y")),
                _rule(_eq("?x2", "?x2"), r),
                _rule(Atom("r", ("?x1", "?y")), r, _eq("?x2", "?y")),
            ],
        )

    def test_equality_itself_and_nullary_predicates_get_only_eq2_eq3(self):
        self.assertEqual(equality_rules({"=": 2, "q": 0}), [SYMMETRY, TRANSITIVITY])

    def test_every_rule_is_normalised(self):
        # Form (4) with m = 1, Zhou et al. 2015, page 5: one effect atom,
        # every variable of which occurs in the body.
        for rule in equality_rules({"a": 1, "r": 2, "t": 3}):
            self.assertEqual(len(rule.effect), 1)
            self.assertEqual(existential_variables(rule), [])

    def test_rule_arities_covers_body_and_effect(self):
        rules = [_rule(Atom("b", ("?x",)), Atom("r", ("?x", "?y")))]
        self.assertEqual(rule_arities(rules), {"r": 2, "b": 1})


if __name__ == "__main__":
    unittest.main()
