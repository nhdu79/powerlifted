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
    filter_unreachable_rules,
    lowerbound_una_rules,
    move_inequalities_to_effect,
)
from rules import DisjunctiveExistentialRule, una_rules  # noqa: E402


def rule(effect, body):
    return DisjunctiveExistentialRule(
        effect=tuple(Atom(p, ("?x",)) for p in effect),
        body=tuple(Atom(p, ("?x",)) for p in body),
    )

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


# team.owl's Player ⊑ Captain ⊔ Substitute, shifted, and its disjointness.
COMPLEMENTS = {"comp_captain": "captain", "comp_substitute": "substitute"}
S1 = rule((), ("player", "comp_substitute", "comp_captain"))
S2_CAPTAIN = rule(("captain",), ("player", "comp_substitute"))
S2_SUBSTITUTE = rule(("substitute",), ("player", "comp_captain"))
S3 = rule(("comp_player",), ("comp_substitute", "comp_captain"))
DISJOINT = rule((), ("substitute", "captain"))
SHIFTED = [S1, S2_CAPTAIN, S2_SUBSTITUTE, S3, DISJOINT]


class ComplementLinkTest(unittest.TestCase):
    def test_complements_are_reachable_from_the_start(self):
        reachable, unreachable = filter_unreachable_rules(
            SHIFTED, {"player"}, COMPLEMENTS
        )
        self.assertEqual(reachable, SHIFTED)
        self.assertEqual(unreachable, [])

    def test_shifted_rules_unreachable_without_complements(self):
        reachable, _ = filter_unreachable_rules(SHIFTED, {"player"})
        self.assertEqual(reachable, [])

    def test_needed_complement_makes_its_concept_needed(self):
        # S1 is a denial (relevant), and reads comp_captain and
        # comp_substitute, i.e. ¬captain and ¬substitute: so the rules
        # deriving captain and substitute are relevant too.
        derive_captain = rule(("captain",), ("leader",))
        relevant, irrelevant = filter_irrelevant_rules(
            [S1, S3, derive_captain], set(), 0, COMPLEMENTS
        )
        self.assertEqual(relevant, [S1, derive_captain])
        self.assertEqual(irrelevant, [S3])

    def test_concept_not_needed_without_complements(self):
        derive_captain = rule(("captain",), ("leader",))
        relevant, _ = filter_irrelevant_rules([S1, derive_captain], set(), 0)
        self.assertEqual(relevant, [S1])


if __name__ == "__main__":
    unittest.main()
