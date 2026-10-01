"""
Regression tests for rules.normal_form — the normalised rule forms (2)-(4),
Zhou et al. 2015, page 5.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/tests/test_normal_form.py
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
from rules.normal_form import (  # noqa: E402
    BOTTOM,
    DISJUNCTIVE,
    EXISTENTIAL,
    group_by_normal_form,
    normal_form,
)

A_X = Atom("a", ("?x",))
B_X = Atom("b", ("?x",))
R_XY = Atom("r", ("?x", "?y"))

DENIAL = DisjunctiveExistentialRule(effect=(), body=(A_X, B_X))
EXISTENTIAL_RULE = DisjunctiveExistentialRule(effect=(R_XY,), body=(A_X,))
DATALOG = DisjunctiveExistentialRule(effect=(B_X,), body=(A_X,))
DISJUNCTION = DisjunctiveExistentialRule(effect=(A_X, B_X), body=(R_XY,))
CONJUNCTION = DisjunctiveExistentialRule(effect=(R_XY, Atom("b", ("?y",))), body=(A_X,))


class NormalFormTest(unittest.TestCase):
    def test_empty_head_is_form_2(self):
        self.assertEqual(normal_form(DENIAL), BOTTOM)

    def test_single_atom_with_existential_is_form_3(self):
        self.assertEqual(normal_form(EXISTENTIAL_RULE), EXISTENTIAL)

    def test_head_without_existential_is_form_4(self):
        # A datalog rule fits (3) with no existential too; it counts as (4).
        self.assertEqual(normal_form(DATALOG), DISJUNCTIVE)
        self.assertEqual(normal_form(DISJUNCTION), DISJUNCTIVE)

    def test_conjunction_under_existential_is_not_normalised(self):
        with self.assertRaises(ValueError):
            normal_form(CONJUNCTION)

    def test_grouping_keeps_every_form_and_rule_order(self):
        rules = [DATALOG, DENIAL, DISJUNCTION, EXISTENTIAL_RULE]
        self.assertEqual(
            group_by_normal_form(rules),
            {
                BOTTOM: [DENIAL],
                EXISTENTIAL: [EXISTENTIAL_RULE],
                DISJUNCTIVE: [DATALOG, DISJUNCTION],
            },
        )
        self.assertEqual(
            group_by_normal_form([]), {BOTTOM: [], EXISTENTIAL: [], DISJUNCTIVE: []}
        )


if __name__ == "__main__":
    unittest.main()
