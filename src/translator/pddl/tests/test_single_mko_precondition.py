"""
Regression tests for an action whose whole precondition is a single mko,
e.g. the team domain's Recruit:

    :precondition (and (mko (and (Team ?t) (Player ?p))))

Normalization turns the one-part (and ...) into the mko itself. Both
pddl.Action.get_action_preconditions and
pddl.Action.transform_precondition_into_list used to treat that mko as a
conjunction:

* get_action_preconditions returned the mko's parts, i.e. its query, so
  compile_types failed its "precondition is a literal" assertion;
* transform_precondition_into_list didn't wrap it, so compile_types added
  the parameters' type atoms to the mko's query, and the UCQ collector,
  which expects an mko to have one part, failed.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/pddl/tests/test_single_mko_precondition.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

import compile_types  # noqa: E402

from pddl import (  # noqa: E402
    Action,
    Atom,
    Conjunction,
    Effect,
    MinimalKnowledgeOperator,
    Truth,
    Type,
    TypedObject,
)

QUERY = Conjunction([Atom("team", ["?t"]), Atom("player", ["?p"])])


def recruit():
    """The team domain's Recruit, with its precondition as normalization
    leaves it: the mko itself, not a conjunction."""
    return Action(
        "recruit",
        [TypedObject("?t", "object"), TypedObject("?p", "object")],
        2,
        MinimalKnowledgeOperator([QUERY], False),
        [Effect([], Truth(), Atom("hasmember", ["?t", "?p"]))],
        None,
    )


class SingleMkoPreconditionTest(unittest.TestCase):
    def test_preconditions_are_the_mko(self):
        action = recruit()
        self.assertEqual(action.get_action_preconditions, [action.precondition])

    def test_transform_wraps_the_mko(self):
        action = recruit()
        mko = action.precondition
        action.transform_precondition_into_list()
        self.assertIsInstance(action.precondition, Conjunction)
        self.assertEqual(action.precondition.parts, (mko,))

    def test_type_atoms_go_next_to_the_mko(self):
        action = recruit()
        task = SimpleNamespace(actions=[action], objects=[])
        graph = compile_types.TypesGraph([Type("object", None)])
        compile_types.add_conditions_to_actions(task, graph)

        precondition = action.precondition
        self.assertIsInstance(precondition, Conjunction)
        mkos = [
            part
            for part in precondition.parts
            if isinstance(part, MinimalKnowledgeOperator)
        ]
        self.assertEqual(len(mkos), 1)
        # The query is untouched: one part (what queries.ucq_collector
        # unpacks), the original conjunction.
        self.assertEqual(mkos[0].parts, (QUERY,))
        type_atoms = {part for part in precondition.parts if isinstance(part, Atom)}
        self.assertEqual(
            type_atoms,
            {Atom("type@object", ["?t"]), Atom("type@object", ["?p"])},
        )


if __name__ == "__main__":
    unittest.main()
