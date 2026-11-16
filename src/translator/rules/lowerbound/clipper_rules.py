"""
Parse the raw Datalog rule strings owl.clipper.Clipper.rewrite_ontology()
returns (Clipper's own Prolog-style syntax, e.g. "b(Y) :- a(X), r(X,Y)."
or the empty-head denial " :- Y !=Z, r(X,Y), r(X,Z)."; Clipper.
_read_datalog_file already strips comments and the trailing "." per rule)
into DisjunctiveExistentialRule objects.

Clipper's own uppercase variables (X, Y, Z, ...) become our "?"-prefixed,
lowercased convention (X -> ?x); quoted individuals become bare constants;
"!=" / "=" become NegatedAtom("=", ...) / Atom("=", ...), reusing
atoms.EQUALITY_PREDICATE. A negated body atom's "-" prefix (Clipper's own
negation syntax) becomes a NegatedAtom. Clipper renders bottom two
different ways depending on where it comes from — a literal empty head
(e.g. a functionality denial) and a head atom over owl:Nothing's own
predicate (e.g. an O1-style disjointness denial, "nothing(X)") are both
normalised here to the same empty effect, rather than one becoming a
"nothing" atom left in place as if it were an ordinary predicate.
"""

from __future__ import annotations

from owl import OWL_NOTHING
from pddl.conditions import Atom, Literal, NegatedAtom

from ..atoms import EQUALITY_PREDICATE
from ..disjunctive_existential_rule import DisjunctiveExistentialRule

BOTTOM_PREDICATE = OWL_NOTHING.id


def _term(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        return text[1:-1]
    if text[:1].isupper():
        return f"?{text.lower()}"
    return text


def _split_body(text: str) -> list[str]:
    """Split on top-level commas only — a comma inside an atom's
    parentheses separates arguments, not atoms."""
    parts = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def _parse_atom(text: str) -> Literal:
    text = text.strip()
    if "!=" in text:
        left, right = text.split("!=", 1)
        return NegatedAtom(EQUALITY_PREDICATE, (_term(left), _term(right)))
    if "(" not in text and "=" in text:
        left, right = text.split("=", 1)
        return Atom(EQUALITY_PREDICATE, (_term(left), _term(right)))

    negated = text.startswith("-")
    if negated:
        text = text[1:]
    name, _, rest = text.partition("(")
    args_text = rest.rstrip(")").strip()
    args = tuple(_term(a) for a in args_text.split(",")) if args_text else ()
    return NegatedAtom(name.strip(), args) if negated else Atom(name.strip(), args)


def _parse_rule(text: str) -> DisjunctiveExistentialRule:
    head_text, _, body_text = text.partition(":-")
    head_text = head_text.strip()
    body = tuple(_parse_atom(a) for a in _split_body(body_text))

    effect: tuple[Literal, ...] = ()
    if head_text:
        head = _parse_atom(head_text)
        if head.predicate != BOTTOM_PREDICATE:
            effect = (head,)

    return DisjunctiveExistentialRule(effect=effect, body=body)


def parse_clipper_rules(raw_rules) -> list[DisjunctiveExistentialRule]:
    """raw_rules: Clipper.rewrite_ontology()'s return value (or
    rewrite_cq's/rewrite_all's) — one Datalog rule string per element,
    "." already stripped."""
    return [_parse_rule(r) for r in raw_rules if r.strip()]
