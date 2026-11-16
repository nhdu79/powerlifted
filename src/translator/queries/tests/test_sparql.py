"""
Regression tests for queries.sparql: an atomic mko's query, shared by the
atoms that differ only in their variables' names, and a conjunctive query as
one SPARQL SELECT per connected component.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/queries/tests/test_sparql.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from pddl import (  # noqa: E402
    Atom,
    Conjunction,
    Disjunction,
    ExistentialCondition,
    NegatedAtom,
    TypedObject,
)

from queries import sparql  # noqa: E402
from queries.sparql import (  # noqa: E402
    MkoQueries,
    UntranslatableQuery,
    mko_pattern,
    translate_cq,
    translate_mko,
    translate_ucq,
)

T = "http://t#"
O = "http://o#"
IRIS = {"team": T + "Team", "player": T + "Player", "hasmember": T + "hasMember"}


def mko(predicate, *args):
    return Atom(predicate, args, mko=True)


class MkoPatternTest(unittest.TestCase):
    def test_atoms_differing_in_variable_names_share_a_pattern(self):
        self.assertEqual(
            mko_pattern(mko("hasmember", "?t", "?p")),
            mko_pattern(mko("hasmember", "?a", "?b")),
        )

    def test_negated_atom_has_the_pattern_of_its_atom(self):
        self.assertEqual(
            mko_pattern(NegatedAtom("team", ("?t",), mko=True)),
            mko_pattern(mko("team", "?x")),
        )

    def test_variables_by_first_occurrence_and_constants_kept(self):
        self.assertEqual(
            mko_pattern(mko("hasmember", "?p", "red")), ("hasmember", ("?x0", "red"))
        )
        self.assertNotEqual(
            mko_pattern(mko("hasmember", "?t", "?t")),
            mko_pattern(mko("hasmember", "?t", "?p")),
        )


class TranslateMkoTest(unittest.TestCase):
    def test_variables_are_the_answer_variables(self):
        result = translate_mko(("hasmember", ("?x0", "?x1")), IRIS, O)

        self.assertEqual(
            result,
            (["x0", "x1"], [[f"SELECT ?x0 ?x1 WHERE {{ ?x0 <{T}hasMember> ?x1 . }}"]]),
        )

    def test_constant_and_repeated_variable(self):
        result = translate_mko(("hasmember", ("?x0", "?x0")), IRIS, O)
        self.assertEqual(
            result,
            (["x0"], [[f"SELECT ?x0 WHERE {{ ?x0 <{T}hasMember> ?x0 . }}"]]),
        )

        result = translate_mko(("hasmember", ("red", "?x0")), IRIS, O)
        self.assertEqual(
            result,
            (["x0"], [[f"SELECT ?x0 WHERE {{ <{O}red> <{T}hasMember> ?x0 . }}"]]),
        )

    def test_ground_atom_is_an_ask(self):
        result = translate_mko(("hasmember", ("red", "bob")), IRIS, O)

        self.assertEqual(
            result, ([], [[f"ASK {{ <{O}red> <{T}hasMember> <{O}bob> . }}"]])
        )

    def test_predicate_outside_the_ontology_is_not_translated(self):
        with self.assertRaisesRegex(UntranslatableQuery, "free"):
            translate_mko(("free", ("?x0",)), IRIS, O)


class TranslateCQTest(unittest.TestCase):
    def test_disconnected_atoms_have_a_query_per_component(self):
        atoms = [Atom("team", ("?t",)), Atom("player", ("?p",))]

        result = translate_cq(atoms, {"?t": "t", "?p": "p"}, IRIS, O)

        self.assertEqual(
            result,
            [
                f"SELECT ?t WHERE {{ ?t a <{T}Team> . }}",
                f"SELECT ?p WHERE {{ ?p a <{T}Player> . }}",
            ],
        )

    def test_component_without_answer_variables_is_an_ask(self):
        # The constant stays an IRI, the existential variable a blank node.
        atoms = [Atom("team", ("?t",)), Atom("hasmember", ("red", "?p"))]

        result = translate_cq(atoms, {"?t": "t"}, IRIS, O)

        self.assertEqual(
            result,
            [
                f"SELECT ?t WHERE {{ ?t a <{T}Team> . }}",
                f"ASK {{ <{O}red> <{T}hasMember> _:y0 . }}",
            ],
        )

    def test_existential_only_component_is_an_ask(self):
        result = translate_cq([Atom("player", ("?p",))], {}, IRIS, O)

        self.assertEqual(result, [f"ASK {{ _:y0 a <{T}Player> . }}"])


class TranslateUCQTest(unittest.TestCase):
    def test_free_variables_in_sorted_order_are_the_answer_variables(self):
        ucq = ExistentialCondition(
            [TypedObject("?q", "object")],
            [
                Conjunction(
                    [
                        Atom("hasmember", ("?t", "?p")),
                        Atom("player", ("?p",)),
                        Atom("hasmember", ("?t", "?q")),
                    ]
                )
            ],
        )

        result = translate_ucq(ucq, IRIS, O)

        # ?p, ?t: x0, x1.
        self.assertEqual(
            result,
            (
                ["x0", "x1"],
                [
                    [
                        f"SELECT ?x0 ?x1 WHERE {{ ?x1 <{T}hasMember> ?x0 . "
                        f"?x0 a <{T}Player> . ?x1 <{T}hasMember> _:y0 . }}"
                    ]
                ],
            ),
        )

    def test_boolean_query_is_an_ask(self):
        ucq = ExistentialCondition(
            [TypedObject("?t", "object")],
            [Conjunction([Atom("team", ("?t",)), Atom("hasmember", ("?t", "star"))])],
        )

        result = translate_ucq(ucq, IRIS, O)

        self.assertEqual(
            result,
            (
                [],
                [[f"ASK {{ _:y0 a <{T}Team> . _:y0 <{T}hasMember> <{O}star> . }}"]],
            ),
        )

    def test_union_has_a_conjunctive_query_per_disjunct(self):
        ucq = Disjunction([Atom("team", ("?x",)), Atom("player", ("?x",))])

        _, cqs = translate_ucq(ucq, IRIS, O)

        self.assertEqual(
            cqs,
            [
                [f"SELECT ?x0 WHERE {{ ?x0 a <{T}Team> . }}"],
                [f"SELECT ?x0 WHERE {{ ?x0 a <{T}Player> . }}"],
            ],
        )


class MkoQueriesTest(unittest.TestCase):
    def setUp(self):
        self.translated = []
        self.translate_mko = sparql.translate_mko
        self.translate_ucq = sparql.translate_ucq

        def counting(translate):
            def wrapped(key, *args):
                self.translated.append(key)
                return translate(key, *args)

            return wrapped

        sparql.translate_mko = counting(self.translate_mko)
        sparql.translate_ucq = counting(self.translate_ucq)
        ucq = Conjunction([Atom("team", ("?t",)), Atom("player", ("?p",))])
        self.mkos = MkoQueries([ucq], IRIS, O)

    def tearDown(self):
        sparql.translate_mko = self.translate_mko
        sparql.translate_ucq = self.translate_ucq

    def test_known_mko_is_translated_once(self):
        # [P(x)] or Q(x) and [P(X)]: their mko P(x) is the same.
        first = self.mkos.add(mko("team", "?x"))
        self.mkos.add(Atom("player", ("?x",)))
        second = self.mkos.add(mko("team", "?y"))
        negated = self.mkos.add(NegatedAtom("team", ("?z",), mko=True))

        self.assertEqual(first, second)
        self.assertEqual(first, negated)
        self.assertEqual(self.translated, [("team", ("?x0",))])
        self.assertEqual(
            self.mkos.mko_entries(),
            [
                (
                    ("team", ("?x0",)),
                    (["x0"], [[f"SELECT ?x0 WHERE {{ ?x0 a <{T}Team> . }}"]]),
                )
            ],
        )

    def test_query_atoms_share_their_query_whatever_their_arguments(self):
        self.mkos.add(mko("QUERY0", "?p", "?t"))
        self.mkos.add(mko("QUERY0", "?a", "?a"))

        self.assertEqual(len(self.translated), 1)
        ((name, (variables, cqs)),) = self.mkos.query_entries()
        self.assertEqual((name, variables), ("QUERY0", ["x0", "x1"]))
        self.assertEqual(
            cqs,
            [
                [
                    f"SELECT ?x1 WHERE {{ ?x1 a <{T}Team> . }}",
                    f"SELECT ?x0 WHERE {{ ?x0 a <{T}Player> . }}",
                ]
            ],
        )
        self.assertEqual(self.mkos.mko_entries(), [])

    def test_untranslatable_mko_is_recorded_once_and_not_listed(self):
        self.mkos.add(mko("free", "?x"))
        self.mkos.add(mko("free", "?y"))

        self.assertEqual(len(self.translated), 1)
        self.assertEqual(list(self.mkos.untranslatable), [("free", ("?x0",))])
        self.assertEqual(self.mkos.mko_entries(), [])


if __name__ == "__main__":
    unittest.main()
