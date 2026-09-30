"""
Lowerbound rules are computed entirely by Clipper: the shifted ontology
(the restricted, Horn-SHIQ-only axioms already in the normalized ontology,
plus owl.ontology_shifter's handling of every O2 axiom — shifted for m>=2,
passed through unchanged for m=1) is serialized and handed to the external
Clipper reasoner (owl.clipper.Clipper); Clipper's rewritten Datalog program,
parsed back into DisjunctiveExistentialRule objects, IS the lowerbound.
This module only selects which axioms go to Clipper and adapts its output — it
doesn't reimplement any of Clipper's reasoning.

The axioms sent to Clipper are exactly O1, O3, O6, O7, O10, O13
(unrestricted), O11 (only n in {0, 1} — Horn-SHIQ restricts number
restrictions to functionality; a general n>=2 qualified cardinality is
inherently disjunctive regardless of whether its role is simple, which
is exactly why O11's own rule needs the pairwise-equality disjunction
in the first place, and owl.ontology_shifter doesn't shift O11, only
O2 — verified empirically too: Clipper warns and drops n>=2 the same
way it does n=0, even for a plain atomic role), O14 (only n >= 1), and
O2 (every axiom, via owl.ontology_shifter — see
horn_shiq_fragment_axioms and shifted_ontology_axioms for the exact
split). O10 and O14 are genuinely existential, but that's not a reason
to exclude them here — it's Clipper's own rewriting, not this module,
that generally can't turn a standalone existential axiom into a finite
non-existential Datalog rule without a query driving it, so such an
axiom's semantic content typically still needs c-chase over the raw
Table 1 rules (rules.table1.ontology_rules.translate_ontology's full output,
including the top-population rules) elsewhere, for the upperbound.
"""

from __future__ import annotations

import os
import tempfile

from owl import (
    O1,
    O3,
    O6,
    O7,
    O10,
    O11,
    O13,
    O14,
    FunctionalRole,
    Ontology,
    ensure_fully_supported,
)
from owl.clipper import Clipper
from owl.ontology_shifter import shift_ontology
from owl.serializer import (
    clipper_aliases,
    referenced_predicate_names,
    serialize_axioms,
)

from ..atoms import EQUALITY_PREDICATE
from ..disjunctive_existential_rule import DisjunctiveExistentialRule
from .clipper_rules import parse_clipper_rules

HORN_SHIQ_LABELS = (O1, O3, O6, O7, O10, O13)


def _cardinality(ax) -> int:
    return 1 if isinstance(ax, FunctionalRole) else ax.sup.n


def horn_shiq_fragment_axioms(ontology: Ontology) -> list:
    """The ontology's own axioms that are already Horn-SHIQ, unmodified:
    O1, O3, O6, O7, O10, O13 unrestricted; O11 restricted to n in {0, 1}
    (a general n>=2 qualified cardinality is inherently disjunctive —
    not a "non-simple role" issue, since O8 is already excluded from
    this fragment and role simplicity alone doesn't make ≥2 Horn — see
    this module's docstring; owl.ontology_shifter doesn't shift O11,
    only O2, so n>=2 is simply dropped here; Clipper itself also warns
    and drops n=0); O14 restricted to n >= 1. Always excludes O2 — every
    O2 axiom (m=1 or m>=2) reaches Clipper only via shifted_ontology_
    axioms's shift_ontology call, which passes an m=1 axiom through
    unchanged and shifts an m>=2 one (see owl.ontology_shifter's
    docstring)."""
    ensure_fully_supported(ontology)
    axioms = [
        ax for label in HORN_SHIQ_LABELS for ax in ontology.axiom_types.get(label, ())
    ]
    axioms += [
        ax for ax in ontology.axiom_types.get(O11, ()) if _cardinality(ax) in (0, 1)
    ]
    axioms += [ax for ax in ontology.axiom_types.get(O14, ()) if _cardinality(ax) >= 1]
    return axioms


def shifted_ontology_axioms(ontology: Ontology) -> list:
    """The shifted ontology: horn_shiq_fragment_axioms(ontology) plus
    owl.ontology_shifter.shift_ontology(ontology), which covers every O2
    axiom in the ontology — shifted for m>=2, passed through unchanged
    for m=1 — so O2's own original form only ever appears here when
    m=1."""
    return horn_shiq_fragment_axioms(ontology) + shift_ontology(ontology)


def _assert_stable_predicate_names(names: set[str], clipper: Clipper) -> None:
    """Pre-flight guard: every predicate name about to be sent to Clipper
    must already be a fixed point of Clipper's own adapt_predicate_name
    (see owl.serializer's module docstring for why it should be) —
    otherwise Clipper would echo it back under a different spelling,
    silently splitting one predicate into two in the lowerbound. This is
    what keeps our existing names from getting overwritten by Clipper's
    own rewriting."""
    mismatches = {
        name: clipper.adapt_predicate_name(name)
        for name in names
        if clipper.adapt_predicate_name(name) != name
    }
    if mismatches:
        raise ValueError(
            f"predicate names not stable under Clipper's naming: {mismatches}"
        )


def new_predicate_rules(
    rules: list[DisjunctiveExistentialRule], known_names: set[str]
) -> list[DisjunctiveExistentialRule]:
    """The subset of rules using at least one predicate outside
    known_names — i.e. one Clipper introduced on its own (e.g. a fresh
    witness predicate for eliminating a cardinality restriction), not a
    name we sent it."""
    return [
        rule
        for rule in rules
        if any(atom.predicate not in known_names for atom in rule.body + rule.effect)
    ]


def _warn_about_new_predicates(
    ontology: Ontology, flagged: list[DisjunctiveExistentialRule], known_names: set[str]
) -> None:
    """Record (in ontology.warnings) the predicate names flagged uses
    outside known_names — not necessarily a problem, but worth knowing
    about rather than silently absorbing into the lowerbound. The rules
    themselves are flagged's caller's to keep; see new_predicate_rules."""
    new = sorted(
        {a.predicate for r in flagged for a in r.body + r.effect} - known_names
    )
    if new:
        ontology.warnings.append(f"Clipper introduced new predicate(s): {new}")


def compute_lowerbound_rules(
    ontology: Ontology,
    clipper_path: str,
    debug: bool = False,
    queries: list[str] | None = None,
    query_predicates: dict[str, int] | None = None,
    axioms: list | None = None,
) -> tuple[list[DisjunctiveExistentialRule], list[DisjunctiveExistentialRule]]:
    """(rules, new_rules): rules is the lowerbound, computed entirely by
    Clipper — serialize shifted_ontology_axioms(ontology) to an
    intermediate OWL file, rewrite it via Clipper (external process, at
    clipper_path), and parse the resulting Datalog program back into
    DisjunctiveExistentialRule objects, guarding our own vocabulary
    against Clipper's naming (_assert_stable_predicate_names). new_rules
    is the subset of rules that uses a predicate Clipper introduced on
    its own, not one we sent it (see new_predicate_rules) — kept, not
    just warned about, so a caller can inspect exactly which rules those
    are.

    queries (Clipper-formatted CQ strings, see queries.rewriter.prepare_
    queries) are rewritten together with the ontology in a single Clipper
    call; their QUERY<i> heads then occur in rules too. query_predicates
    ({name: arity}, in Clipper's spelling) are the predicates those
    queries mention: the ones no serialized axiom mentions get declared
    in the intermediate OWL file, since Clipper silently drops query
    atoms over undeclared names.

    axioms, if given, must be shifted_ontology_axioms(ontology), computed
    by a caller that needs them as well — shifting deep-copies the whole
    ontology, so it's worth doing only once."""
    if axioms is None:
        axioms = shifted_ontology_axioms(ontology)
    entity_names = referenced_predicate_names(axioms)
    declared = {
        name: arity
        for name, arity in (query_predicates or {}).items()
        if name not in entity_names
    }
    aliases = clipper_aliases(entity_names | set(declared))
    text = serialize_axioms(
        axioms, ontology.iri or "http://powerlifted/lowerbound", declared, aliases
    )

    fd, path = tempfile.mkstemp(suffix=".owl")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        clipper = Clipper(clipper_path, path, mqf=bool(queries), debug_mode=debug)
        # Only the entities we actually declared go through Clipper's
        # IRI-derived naming — equality isn't a declared entity, so it's
        # excluded here even though it's added below as always-expected.
        _assert_stable_predicate_names(
            {aliases.get(n, n) for n in entity_names | set(declared)}, clipper
        )
        if queries:
            raw_rules = clipper.rewrite_all("\n".join(queries))
        else:
            raw_rules = clipper.rewrite_ontology()
    finally:
        if not debug:
            os.remove(path)

    # Equality is always a legitimate predicate for Clipper to use (e.g.
    # its own functionality-denial rewriting, via !=), regardless of
    # whether these axioms happen to produce an O11/O14 equality atom —
    # not something to flag as "introduced on its own". Neither are the
    # query heads and the predicates declared for the queries.
    query_heads = {_query_head_name(q) for q in queries or ()}
    known_names = entity_names | set(declared) | {EQUALITY_PREDICATE} | query_heads
    rules = _unalias(parse_clipper_rules(raw_rules), aliases)
    _assert_no_dropped_queries(rules, query_heads)
    flagged = new_predicate_rules(rules, known_names)
    _warn_about_new_predicates(ontology, flagged, known_names)
    return rules, flagged


def _unalias(
    rules: list[DisjunctiveExistentialRule], aliases: dict[str, str]
) -> list[DisjunctiveExistentialRule]:
    """rules with every alias (see owl.serializer.clipper_aliases) replaced
    by the id it stands for."""
    ids = {alias: name for name, alias in aliases.items()}

    def unalias(atom):
        return atom.__class__(ids.get(atom.predicate, atom.predicate), atom.args)

    return [
        DisjunctiveExistentialRule(
            effect=tuple(unalias(a) for a in rule.effect),
            body=tuple(unalias(a) for a in rule.body),
        )
        for rule in rules
    ]


def _assert_no_dropped_queries(
    rules: list[DisjunctiveExistentialRule], query_heads: set[str]
) -> None:
    """Clipper silently drops query atoms whose predicate it doesn't know;
    once every atom of a query is dropped, it answers with an empty body
    ("QUERY0(X0) :- ."), which would read as a query that always holds.
    Every query sent has at least one atom, so an empty body can only mean
    that."""
    dropped = sorted(
        {
            atom.predicate
            for rule in rules
            if not rule.body
            for atom in rule.effect
            if atom.predicate in query_heads
        }
    )
    if dropped:
        raise ValueError(
            f"Clipper dropped every atom of query {', '.join(dropped)}: some "
            f"predicate in it is unknown to the ontology Clipper was given"
        )


def _query_head_name(query: str) -> str:
    return query.split("(", 1)[0].strip()
