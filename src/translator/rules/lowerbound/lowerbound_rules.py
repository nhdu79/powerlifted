"""
Compute the lowerbound rules with Clipper: serialize the shifted ontology
(shifted_ontology_axioms), rewrite it with Clipper, and parse Clipper's
Datalog program back into DisjunctiveExistentialRule objects.

Axioms sent to Clipper: O1, O3, O6, O7, O10, O13; O11 with n in {0, 1};
O14 with n >= 1; and every O2 axiom via owl.ontology_shifter.
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
    """The ontology's Horn-SHIQ axioms, unmodified: O1, O3, O6, O7, O10,
    O13; O11 with n in {0, 1}; O14 with n >= 1. Excludes O2 (see
    shifted_ontology_axioms)."""
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
    """horn_shiq_fragment_axioms(ontology) plus the shifted O2 axioms."""
    return horn_shiq_fragment_axioms(ontology) + shift_ontology(ontology)


def _assert_stable_predicate_names(names: set[str], clipper: Clipper) -> None:
    """Raise if Clipper would respell any of names (adapt_predicate_name)."""
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
    """The rules using a predicate outside known_names, i.e. one Clipper
    introduced."""
    return [
        rule
        for rule in rules
        if any(atom.predicate not in known_names for atom in rule.body + rule.effect)
    ]


def _warn_about_new_predicates(
    ontology: Ontology, flagged: list[DisjunctiveExistentialRule], known_names: set[str]
) -> None:
    """Add a warning to ontology.warnings naming the new predicates in
    flagged."""
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
    """(rules, new_rules): the lowerbound rules Clipper computes for
    shifted_ontology_axioms(ontology), and those of them using a predicate
    Clipper introduced (new_predicate_rules).

    queries (Clipper-formatted CQs) are rewritten in the same Clipper call.
    query_predicates ({name: arity}) not mentioned by any axiom are
    declared in the serialized ontology. axioms, if given, must be
    shifted_ontology_axioms(ontology)."""
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

    # Predicates Clipper may use without having introduced them.
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
    """rules with every alias replaced by the id it stands for."""
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
    """Raise if a query head has an empty body: Clipper dropped all its
    atoms."""
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
