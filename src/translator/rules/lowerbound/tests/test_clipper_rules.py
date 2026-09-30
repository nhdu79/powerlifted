"""
Regression tests for rules.lowerbound.clipper_rules — parsing Clipper's raw Datalog
rule strings into DisjunctiveExistentialRule objects.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/rules/lowerbound/tests/test_clipper_rules.py

from anywhere (the `owl`/`pddl`/`rules` package paths are resolved
relative to this file, not the current working directory).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from pddl.conditions import Atom, NegatedAtom  # noqa: E402

from rules.lowerbound.clipper_rules import parse_clipper_rules  # noqa: E402
from rules.disjunctive_existential_rule import DisjunctiveExistentialRule  # noqa: E402


class ParseClipperRulesTest(unittest.TestCase):
    def test_plain_rule_with_multiple_body_atoms(self):
        rules = parse_clipper_rules(["b(Y) :- a(X), r(X,Y)"])

        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("b", ("?y",)),),
                    body=(Atom("a", ("?x",)), Atom("r", ("?x", "?y"))),
                )
            ],
        )

    def test_empty_head_is_falsity(self):
        rules = parse_clipper_rules([" :- a(X), b(X)"])

        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(), body=(Atom("a", ("?x",)), Atom("b", ("?x",)))
                )
            ],
        )

    def test_nothing_head_is_also_falsity(self):
        # Clipper renders bottom two ways — a literal empty head and a
        # head atom over owl:Nothing's own predicate ("nothing") — both
        # must normalise to the same empty effect.
        rules = parse_clipper_rules(["nothing(X) :- a(X), b(X)"])

        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(), body=(Atom("a", ("?x",)), Atom("b", ("?x",)))
                )
            ],
        )

    def test_inequality_body_atom(self):
        rules = parse_clipper_rules([" :- Y !=Z, r(X,Z), r(X,Y)"])

        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(),
                    body=(
                        NegatedAtom("=", ("?y", "?z")),
                        Atom("r", ("?x", "?z")),
                        Atom("r", ("?x", "?y")),
                    ),
                )
            ],
        )

    def test_equality_head(self):
        rules = parse_clipper_rules(["X=Y :- r(X,Y)"])

        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("=", ("?x", "?y")),), body=(Atom("r", ("?x", "?y")),)
                )
            ],
        )

    def test_negated_body_atom(self):
        rules = parse_clipper_rules(["a(X) :- b(X), -c(X)"])

        self.assertEqual(
            rules,
            [
                DisjunctiveExistentialRule(
                    effect=(Atom("a", ("?x",)),),
                    body=(Atom("b", ("?x",)), NegatedAtom("c", ("?x",))),
                )
            ],
        )

    def test_quoted_individual_stays_a_bare_constant(self):
        rules = parse_clipper_rules(["nominal(X) :- eq(X,'alice')"])

        self.assertEqual(rules[0].body, (Atom("eq", ("?x", "alice")),))

    def test_no_body_is_a_fact(self):
        rules = parse_clipper_rules(["a(X) :- "])

        self.assertEqual(
            rules, [DisjunctiveExistentialRule(effect=(Atom("a", ("?x",)),), body=())]
        )

    def test_skips_blank_entries(self):
        rules = parse_clipper_rules(["b(Y) :- a(X), r(X,Y)", "  ", ""])

        self.assertEqual(len(rules), 1)


if __name__ == "__main__":
    unittest.main()
