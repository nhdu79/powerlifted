"""
Regression tests for rules.print_rules.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/tests/test_print_rules.py

from anywhere (the `owl`/`pddl`/`rules` package paths are resolved
relative to this file, not the current working directory).
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

from pddl.conditions import Atom, NegatedAtom  # noqa: E402

from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402
from rules.print_rules import (  # noqa: E402
    format_atom,
    format_effect,
    format_rule,
    print_rules,
)


class FormatAtomTest(unittest.TestCase):
    def test_positive_atom(self):
        self.assertEqual(format_atom(Atom("r", ("?x", "?y"))), "r(x, y)")

    def test_negated_atom(self):
        self.assertEqual(format_atom(NegatedAtom("r", ("?x", "?y"))), "¬r(x, y)")

    def test_positive_equality_uses_approx_symbol(self):
        self.assertEqual(format_atom(Atom("=", ("?x", "a"))), "x ≈ a")

    def test_negated_equality_uses_not_equal_symbol(self):
        self.assertEqual(format_atom(NegatedAtom("=", ("?y1", "?y2"))), "y1 ≠ y2")

    def test_constant_arguments_are_not_stripped(self):
        self.assertEqual(format_atom(Atom("p", ("a", "?x"))), "p(a, x)")


class FormatEffectTest(unittest.TestCase):
    def test_empty_effect_is_bottom(self):
        rule = DisjunctiveExistentialRule(effect=(), body=(Atom("a", ("?x",)),))
        self.assertEqual(format_effect(rule), "⊥")

    def test_single_non_existential_atom_has_no_quantifier(self):
        rule = DisjunctiveExistentialRule(
            effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
        )
        self.assertEqual(format_effect(rule), "b(x)")

    def test_multiple_non_existential_atoms_are_disjoined(self):
        rule = DisjunctiveExistentialRule(
            effect=(Atom("b", ("?x",)), Atom("c", ("?x",))),
            body=(Atom("a", ("?x",)),),
        )
        self.assertEqual(format_effect(rule), "b(x) ∨ c(x)")

    def test_existential_variable_is_quantified_over_a_conjunction(self):
        rule = DisjunctiveExistentialRule(
            effect=(Atom("r", ("?x", "?y")), Atom("b", ("?y",))),
            body=(Atom("a", ("?x",)),),
        )
        self.assertEqual(format_effect(rule), "∃y (r(x, y) ∧ b(y))")

    def test_multiple_existential_variables_are_all_quantified(self):
        rule = DisjunctiveExistentialRule(
            effect=(
                Atom("r", ("?x", "?y1")),
                Atom("b", ("?y1",)),
                Atom("r", ("?x", "?y2")),
                Atom("b", ("?y2",)),
                NegatedAtom("=", ("?y1", "?y2")),
            ),
            body=(Atom("a", ("?x",)),),
        )
        self.assertEqual(
            format_effect(rule),
            "∃y1, y2 (r(x, y1) ∧ b(y1) ∧ r(x, y2) ∧ b(y2) ∧ y1 ≠ y2)",
        )


class FormatRuleTest(unittest.TestCase):
    def test_conjunctive_body_and_existential_effect(self):
        rule = DisjunctiveExistentialRule(
            effect=(Atom("r", ("?x", "?y")), Atom("b", ("?y",))),
            body=(Atom("a", ("?x",)),),
        )
        self.assertEqual(format_rule(rule), "a(x) → ∃y (r(x, y) ∧ b(y))")

    def test_empty_body_is_top(self):
        # A nullary effect atom has no argument to be existential over.
        rule = DisjunctiveExistentialRule(effect=(Atom("a", ()),), body=())
        self.assertEqual(format_rule(rule), "⊤ → a()")

    def test_empty_body_makes_every_effect_variable_existential(self):
        # With no body atoms to ground x, "x" can only be read as fresh —
        # this is the correct, not a surprising, reading (per the safety
        # condition in Zhou et al. 2015's rule form (1): a variable can
        # only be free/universal if it's mentioned in body).
        rule = DisjunctiveExistentialRule(effect=(Atom("a", ("?x",)),), body=())
        self.assertEqual(format_rule(rule), "⊤ → ∃x (a(x))")

    def test_denial_rule_body_conjunction_to_bottom(self):
        rule = DisjunctiveExistentialRule(
            effect=(), body=(Atom("a", ("?x",)), Atom("b", ("?x",)))
        )
        self.assertEqual(format_rule(rule), "a(x) ∧ b(x) → ⊥")


class PrintRulesTest(unittest.TestCase):
    def test_prints_one_numbered_line_per_rule(self):
        rules = [
            DisjunctiveExistentialRule(
                effect=(Atom("b", ("?x",)),), body=(Atom("a", ("?x",)),)
            ),
            DisjunctiveExistentialRule(
                effect=(), body=(Atom("c", ("?x",)),)
            ),
        ]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_rules(rules)
        self.assertEqual(
            out.getvalue().splitlines(),
            ["0: a(x) → b(x)", "1: c(x) → ⊥"],
        )


if __name__ == "__main__":
    unittest.main()
