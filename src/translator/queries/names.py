"""
User names at the Clipper boundary: checks and the Clipper spelling map
(mirrors pddl-horndl's compilation/names.py).

Clipper lowercases names and drops "_" and "-" (keeping e.g. "."). User
OWL names are normalized with owl.expressions.parse_name (keeping only
[a-z0-9]), which Clipper leaves unchanged; generated names contain "_" and
reach Clipper under an alias (owl.serializer.clipper_aliases). Either way,
ontology names round-trip through Clipper unchanged. PDDL names are
only lowercased by the parser, though, and the rest of the translator keeps
them exactly as written. Unlike pddl-horndl, which renames every PDDL
predicate up front, the names are therefore translated only where they cross
the Clipper boundary (ClipperSpelling):

* PDDL -> Clipper: parse_name, the same normalization user ontology ids use,
  so a PDDL predicate and an OWL entity with the same normalized name are
  the same predicate for Clipper;
* Clipper -> PDDL: back to the PDDL spelling, so the compiled rules speak
  the task's own vocabulary. Names the task doesn't know (ontology-only and
  generated ones) keep their normalized spelling.

check_names verifies up front that this translation is safe, i.e. it neither
merges distinct names nor produces a name that is generated elsewhere.

pddl-horndl's second check is kept for OWL names (letters, digits, "_" and
"-" only), even though Clipper never sees a raw OWL name: parse_name deletes
every other character, which silently turns e.g. "Café" into "caf" and a
non-Latin name into the empty string. PDDL names get the part of it that
matters for them: they must be ASCII and must not normalize to "".
"""

import re
from collections import defaultdict
from dataclasses import fields, is_dataclass

from owl import OWL_NOTHING, OWL_THING, AtomicConcept, AtomicRole
from owl.expressions import parse_name
from rdflib.namespace import OWL
from rules.atoms import NEQ_PREDICATE

_OWL_NS = str(OWL)
_QUERY_LIKE = re.compile(r"query\d+")
# Characters parse_name keeps, plus the separators it drops by design.
_NORMALIZATION_SAFE = re.compile(r"[A-Za-z0-9_-]+")


class NameClashError(ValueError):
    pass


def _raw_local_name(iri):
    """The local name of iri as written, i.e. owl.expressions._local_name
    without the normalization."""
    for sep in ("#", "/"):
        if sep in iri:
            return iri.rsplit(sep, 1)[-1]
    return iri


def _is_translator_generated(name):
    """Predicates the translator introduces itself (type@<type>, @-prefixed
    helpers, equality), which never reach Clipper."""
    return "@" in name or name == "="


def pddl_predicate_names(task):
    """The task's predicate names as written (lowercased by the parser)."""
    return [p.name for p in task.predicates if not _is_translator_generated(p.name)]


class OntologyNames:
    """The named concepts and roles of an ontology, split into the ones the
    user declared and the ones owl.ontology_normalizer generated.

    Construct from the ontology straight out of owl.parse_owl, then call
    add_generated with the axioms computed from it for Clipper.
    """

    def __init__(self, ontology):
        raw = defaultdict(set)  # normalized name -> raw local names
        self.arity = {}  # normalized name -> 1 (concept) or 2 (role)
        for expr, arity in [(c, 1) for c in ontology.atomic_concepts.values()] + [
            (r, 2) for r in ontology.atomic_roles.values()
        ]:
            if expr in (OWL_THING, OWL_NOTHING) or expr.iri.startswith(_OWL_NS):
                continue
            raw[expr.id].add(_raw_local_name(expr.iri))
            self.arity[expr.id] = arity
        self.raw = dict(raw)
        self.generated = set()

    def add_generated(self, axioms):
        """Record the fresh symbols normalization and shifting introduced
        (def_*, comp_*, defr_* — see owl.ontology_normalizer.fresh_symbols)
        that occur in axioms, recognised by their IRI, which is a bare name
        rather than an absolute IRI.

        Pass the axioms sent to Clipper (rules.lowerbound.shifted_ontology_
        axioms): their fresh symbols are exactly the ones that can end up as
        predicates in the compiled rules, next to the task's PDDL
        predicates. Their ids contain "_" and so never equal a (normalized)
        OWL name, but PDDL names aren't normalized and may contain "_" too.
        """
        for expr in _atomic_expressions(axioms):
            if ":" not in expr.iri:
                self.generated.add(expr.id)

def _atomic_expressions(node):
    """Every AtomicConcept/AtomicRole occurring in node (an axiom, an
    expression, or a list/tuple of them)."""
    if isinstance(node, (AtomicConcept, AtomicRole)):
        yield node
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from _atomic_expressions(child)
    elif is_dataclass(node):
        for field in fields(node):
            yield from _atomic_expressions(getattr(node, field.name))


class ClipperSpelling:
    """Translates predicate names between the task's and Clipper's spelling.

    Only unambiguous once check_names passed.
    """

    def __init__(self, pddl_names):
        self._to_pddl = {parse_name(name): name for name in pddl_names}

    def to_clipper(self, name):
        return parse_name(name)

    def to_pddl(self, name):
        return self._to_pddl.get(name, name)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_names(task, ontology_names):
    """Raise NameClashError if translating the task's names into Clipper's
    spelling (and back) is unsafe."""
    problems = []
    pddl_raw = defaultdict(set)
    pddl_arity = {}
    for predicate in task.predicates:
        if _is_translator_generated(predicate.name):
            continue
        name = parse_name(predicate.name)
        pddl_raw[name].add(predicate.name)
        pddl_arity[name] = len(predicate.arguments)
    pddl_raw = dict(pddl_raw)  # reads below must not insert empty entries
    owl_raw = ontology_names.raw
    no_names = frozenset()

    # 1. Distinct names merged by normalization. PDDL is case-insensitive
    #    (and already lowercased by the parser); OWL names are case-sensitive.
    for name in sorted(set(pddl_raw) | set(owl_raw)):
        spellings = pddl_raw.get(name, no_names) | owl_raw.get(name, no_names)
        if len({s.lower() for s in spellings}) > 1:
            # one representative per case-insensitive spelling
            shown = sorted({s.lower(): s for s in sorted(spellings)}.values())
            problems.append(
                f"{' / '.join(shown)} differ by more than letter case but all "
                f"normalize to '{name}'; use one spelling"
            )
        elif len(owl_raw.get(name, no_names)) > 1:
            shown = sorted(owl_raw[name])
            problems.append(
                f"OWL names {' / '.join(shown)} differ only in letter case, which "
                f"PDDL cannot distinguish; rename one of them"
            )

    # 2. Names normalization would mangle rather than merely normalize.
    for raws in owl_raw.values():
        for raw in sorted(raws):
            if not _NORMALIZATION_SAFE.fullmatch(raw):
                problems.append(
                    f"OWL name '{raw}' may only contain letters, digits, '_' and '-'"
                )
    for raws in pddl_raw.values():
        for raw in sorted(raws):
            if not raw.isascii() or not parse_name(raw):
                problems.append(
                    f"PDDL predicate '{raw}' must be ASCII and contain a letter "
                    f"or digit"
                )

    # 3. A PDDL predicate standing for an OWL entity of a different arity.
    for name in sorted(set(pddl_arity) & set(ontology_names.arity)):
        if pddl_arity[name] != ontology_names.arity[name]:
            kind = "concept" if ontology_names.arity[name] == 1 else "role"
            spelled = sorted(pddl_raw[name])[0]
            problems.append(
                f"PDDL predicate '{spelled}' has arity {pddl_arity[name]} but "
                f"names an OWL {kind}"
            )

    # 4. User names equal to names generated elsewhere. Generated ids are
    #    compared with PDDL names as written: both occur unnormalized in the
    #    compiled rules.
    for raws in pddl_raw.values():
        for raw in sorted(raws & ontology_names.generated):
            problems.append(
                f"'{raw}' is reserved for a fresh symbol introduced by "
                f"ontology normalization or shifting"
            )
        if NEQ_PREDICATE in raws:
            problems.append(
                f"'{NEQ_PREDICATE}' is reserved for the distinctness of "
                f"min-cardinality fillers"
            )
    reserved = {OWL_NOTHING.id: "owl:Nothing", OWL_THING.id: "owl:Thing"}
    for name in sorted(set(pddl_raw) | set(owl_raw)):
        spelled = sorted(pddl_raw.get(name, no_names) | owl_raw.get(name, no_names))[0]
        if name in reserved:
            problems.append(f"'{spelled}' is reserved for {reserved[name]}")
        elif _QUERY_LIKE.fullmatch(name):
            problems.append(f"'{spelled}' is reserved for generated query predicates")

    if problems:
        raise NameClashError(
            "Predicate names cannot be compiled safely:\n  - " + "\n  - ".join(problems)
        )
