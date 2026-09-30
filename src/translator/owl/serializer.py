"""
Serialize normalized DL axioms back into an OWL Turtle file, for handing
off to an external OWL reasoner (e.g. Clipper, via owl.clipper.Clipper) —
the inverse direction of owl.parser.parse_owl, restricted to the axiom
shapes rules.lowerbound.lowerbound_rules's shifted ontology actually produces (O1,
O3, O6, O7, O10, O11, O13, O14, plus the plain "conjunction of atomic
concepts ⊑ a single atomic concept" shape owl.ontology_shifter's S2/S3
rules use).

Entity IRIs are minted from each concept/role's .id, not its original
IRI, so a fresh symbol from owl.ontology_normalizer (whose .iri is just a
short local name, not an absolute IRI) still serializes to a valid IRI.
A user id ([a-z0-9]) is a fixed point of Clipper's own normalization
(owl.clipper.Clipper.adapt_predicate_name) and round-trips unchanged;
a generated id contains "_", which Clipper would drop, so it's written
under an alias instead (see clipper_aliases).
"""

from __future__ import annotations

import re

from rdflib import BNode, Graph, URIRef
from rdflib import Literal as RDFLiteral
from rdflib.namespace import OWL, RDF, RDFS, XSD

from owl.axioms import ConceptInclusion, FunctionalRole, RoleInclusion
from owl.expressions import (
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    AtomicRole,
    IntersectionConcept,
    InverseRole,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    MinCardinalityConcept,
    QualifiedExistentialConcept,
    UniversalConcept,
)

_CLIPPER_STABLE = re.compile(r"[a-z0-9]+")
ALIAS_PREFIX = "fresh"


def clipper_aliases(names) -> dict[str, str]:
    """{id: alias} for every id in names Clipper would rename (i.e. every
    generated id, see owl.expressions' naming constants): fresh<i>, skipping
    any alias that is itself one of names. Injective by construction, so
    Clipper's output can be mapped back exactly."""
    names = set(names)
    aliases = {}
    counter = 0
    for name in sorted(names):
        if _CLIPPER_STABLE.fullmatch(name):
            continue
        while f"{ALIAS_PREFIX}{counter}" in names:
            counter += 1
        aliases[name] = f"{ALIAS_PREFIX}{counter}"
        counter += 1
    return aliases


class _Writer:
    def __init__(self, base: str, aliases: dict[str, str] | None = None):
        self.graph = Graph()
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self._base = base
        self._aliases = aliases or {}
        # Every AtomicConcept/AtomicRole .id referenced so far — also
        # doubles as referenced_predicate_names' return value.
        self.entity_names: set[str] = set()

    def _entity_iri(self, expr_id: str) -> URIRef:
        return URIRef(f"{self._base}#{self._aliases.get(expr_id, expr_id)}")

    def _concept(self, concept) -> URIRef:
        if concept is OWL_THING:
            return OWL.Thing
        if concept is OWL_NOTHING:
            return OWL.Nothing
        assert isinstance(concept, AtomicConcept)
        iri = self._entity_iri(concept.id)
        if concept.id not in self.entity_names:
            self.entity_names.add(concept.id)
            self.graph.add((iri, RDF.type, OWL.Class))
        return iri

    def _role(self, role: AtomicRole) -> URIRef:
        iri = self._entity_iri(role.id)
        if role.id not in self.entity_names:
            self.entity_names.add(role.id)
            self.graph.add((iri, RDF.type, OWL.ObjectProperty))
        return iri

    def _restriction(self, role: AtomicRole, extra) -> BNode:
        node = BNode()
        self.graph.add((node, RDF.type, OWL.Restriction))
        self.graph.add((node, OWL.onProperty, self._role(role)))
        for pred, obj in extra:
            self.graph.add((node, pred, obj))
        return node

    def _cardinality_restriction(self, restriction, pred) -> BNode:
        n = RDFLiteral(restriction.n, datatype=XSD.nonNegativeInteger)
        filler = self._concept(restriction.concept)
        return self._restriction(restriction.role, [(pred, n), (OWL.onClass, filler)])

    def _lhs_subject(self, sub) -> URIRef | BNode:
        """A single concept, or an owl:intersectionOf blank node for a
        multi-conjunct LHS (IntersectionConcept)."""
        conjuncts = sub.operands if isinstance(sub, IntersectionConcept) else (sub,)
        if len(conjuncts) == 1:
            return self._concept(conjuncts[0])
        subject = BNode()
        self.graph.add((subject, OWL.intersectionOf, self._rdf_list(conjuncts)))
        return subject

    def add(self, ax) -> None:
        if isinstance(ax, FunctionalRole):
            self.graph.add((self._role(ax.role), RDF.type, OWL.FunctionalProperty))
            return

        if isinstance(ax, RoleInclusion):  # O6, O7
            sub = self._role(ax.sub)
            if isinstance(ax.sup, InverseRole):
                inv = BNode()
                self.graph.add((inv, OWL.inverseOf, self._role(ax.sup.role)))
                self.graph.add((sub, RDFS.subPropertyOf, inv))
            else:
                self.graph.add((sub, RDFS.subPropertyOf, self._role(ax.sup)))
            return

        assert isinstance(ax, ConceptInclusion)
        sub, sup = ax.sub, ax.sup

        if isinstance(sub, QualifiedExistentialConcept):  # O3
            node = self._restriction(
                sub.role, [(OWL.someValuesFrom, self._concept(sub.concept))]
            )
            self.graph.add((node, RDFS.subClassOf, self._concept(sup)))
            return

        if isinstance(sup, QualifiedExistentialConcept):  # O10
            node = self._restriction(
                sup.role, [(OWL.someValuesFrom, self._concept(sup.concept))]
            )
            self.graph.add((self._concept(sub), RDFS.subClassOf, node))
            return

        if isinstance(sup, MaxCardinalityConcept):  # O11
            node = self._cardinality_restriction(sup, OWL.maxQualifiedCardinality)
            self.graph.add((self._concept(sub), RDFS.subClassOf, node))
            return

        if isinstance(sup, MinCardinalityConcept):  # O14
            node = self._cardinality_restriction(sup, OWL.minQualifiedCardinality)
            self.graph.add((self._concept(sub), RDFS.subClassOf, node))
            return

        if isinstance(sup, (UniversalConcept, InverseUniversalConcept)):  # O13
            if isinstance(sup, InverseUniversalConcept):
                on_property = BNode()
                self.graph.add((on_property, OWL.inverseOf, self._role(sup.role)))
            else:
                on_property = self._role(sup.role)
            node = BNode()
            self.graph.add((node, RDF.type, OWL.Restriction))
            self.graph.add((node, OWL.onProperty, on_property))
            self.graph.add((node, OWL.allValuesFrom, self._concept(sup.concept)))
            self.graph.add((self._concept(sub), RDFS.subClassOf, node))
            return

        if sup is OWL_NOTHING:  # O1
            self.graph.add((self._lhs_subject(sub), RDFS.subClassOf, OWL.Nothing))
            return

        if isinstance(sup, AtomicConcept):
            # Plain subsumption: a conjunction of atomic concepts implies
            # a single atomic concept — owl.ontology_shifter's S2/S3
            # rules are exactly this shape.
            subject = self._lhs_subject(sub)
            self.graph.add((subject, RDFS.subClassOf, self._concept(sup)))
            return

        raise ValueError(f"serializer doesn't support this axiom shape: {ax}")

    def _rdf_list(self, items):
        head = RDF.nil
        for item in reversed(items):
            node = BNode()
            self.graph.add((node, RDF.first, self._concept(item)))
            self.graph.add((node, RDF.rest, head))
            head = node
        return head


def serialize_axioms(
    axioms,
    iri: str,
    declared: dict[str, int] | None = None,
    aliases: dict[str, str] | None = None,
) -> str:
    """Turtle text for axioms (the shapes this module's docstring lists),
    as a standalone owl:Ontology with IRI iri and one entity declaration
    per referenced concept/role.

    declared ({name: arity}) additionally declares entities no axiom
    mentions — arity 1 as an owl:Class, arity 2 as an owl:ObjectProperty —
    e.g. PDDL predicates used in mko queries: Clipper silently drops query
    atoms over undeclared names, which would make the query trivially
    true.

    aliases ({id: alias}, see clipper_aliases) gives the local name to
    write for an id instead of the id itself."""
    writer = _Writer(iri, aliases)
    writer.graph.add((URIRef(iri), RDF.type, OWL.Ontology))
    for ax in axioms:
        writer.add(ax)
    for name, arity in sorted((declared or {}).items()):
        if arity == 1:
            writer._concept(AtomicConcept(name))
        elif arity == 2:
            writer._role(AtomicRole(name))
        else:
            raise ValueError(
                f"cannot declare '{name}' of arity {arity}: OWL only has "
                f"concepts (arity 1) and roles (arity 2)"
            )
    return writer.graph.serialize(format="turtle")


def referenced_predicate_names(axioms) -> set[str]:
    """Every AtomicConcept/AtomicRole .id referenced by axioms — the
    predicate vocabulary serialize_axioms(axioms, ...) will declare,
    plus "thing"/"nothing" (OWL_THING/OWL_NOTHING's own .id) since either
    can appear regardless of whether an axiom mentions them by name (e.g.
    as owl:Nothing in an O1 axiom's rdfs:subClassOf). Used to guard
    Clipper's rewritten output against this same vocabulary — see
    rules.lowerbound.lowerbound_rules."""
    writer = _Writer(base="")
    for ax in axioms:
        writer.add(ax)
    return writer.entity_names | {OWL_THING.id, OWL_NOTHING.id}
