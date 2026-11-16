"""
Regression tests for queries.names.check_names' reservation of the Table 1
rules' own predicates (rules.atoms.NEQ_PREDICATE, HEAD_PREDICATE_PREFIX).

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/queries/tests/test_names.py
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

from pddl import Predicate, TypedObject  # noqa: E402
from queries.names import NameClashError, check_names  # noqa: E402


def _task(*names_and_arities):
    return SimpleNamespace(
        predicates=[
            Predicate(name, [TypedObject(f"?x{i}", "object") for i in range(arity)])
            for name, arity in names_and_arities
        ]
    )


_NO_ONTOLOGY_NAMES = SimpleNamespace(raw={}, arity={}, generated=set())


class ReservedRulePredicatesTest(unittest.TestCase):
    def test_ordinary_and_translator_generated_names_pass(self):
        check_names(_task(("on", 2), ("type@block", 1), ("=", 2)), _NO_ONTOLOGY_NAMES)

    def test_neq_is_reserved(self):
        with self.assertRaisesRegex(NameClashError, "'neq@' is reserved"):
            check_names(_task(("neq@", 2)), _NO_ONTOLOGY_NAMES)

    def test_every_head_name_is_reserved(self):
        with self.assertRaisesRegex(
            NameClashError, "'head@exists_r_dot_b' is reserved"
        ):
            check_names(_task(("head@exists_r_dot_b", 2)), _NO_ONTOLOGY_NAMES)

    def test_the_old_underscore_spelling_is_a_user_name_again(self):
        check_names(_task(("neq_", 2)), _NO_ONTOLOGY_NAMES)


if __name__ == "__main__":
    unittest.main()
