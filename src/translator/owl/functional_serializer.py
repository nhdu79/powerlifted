"""
Serialize an ontology's (normalized) TBox into OWL 2 functional syntax, for
the search's Konclude reasoner (src/search/konclude/state_reasoner.h), which
reads no Turtle.

Unlike owl.serializer (Clipper's input), it writes every axiom and
expression shape owl.parser produces, not only the Table 1 ones, so it also
serializes an ontology with unclassified axioms.

IRIs:
* a user entity keeps the IRI it has in the source ontology, so the
  vocabulary (task predicate -> IRI, see vocabulary) and hand-written SPARQL
  queries can use it;
* a fresh symbol of owl.ontology_normalizer (whose .iri is a bare name) gets
  FRESH_IRI_PREFIX + its id;
* a task object is OBJECT_IRI_PREFIX + its name, the IRI the search tells
  Konclude its facts with. A nominal's individual is the task object of the
  same normalized name, if there is one.

The planner assumes unique names (see the UNA rules of the lowerbound and
upperbound), OWL doesn't: the ontology states it for the task's objects with
DifferentIndividuals.
"""

from __future__ import annotations

from owl.axioms import (
    ConceptInclusion,
    FunctionalRole,
    InverseFunctionalRole,
    RoleInclusion,
)
from owl.expressions import (
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    AtomicRole,
    IntersectionConcept,
    InverseMaxCardinalityConcept,
    InverseMinCardinalityConcept,
    InverseQualifiedExistentialConcept,
    InverseRole,
    InverseUniversalConcept,
    MaxCardinalityConcept,
    MinCardinalityConcept,
    NegatedConcept,
    NegatedRole,
    Nominal,
    QualifiedExistentialConcept,
    RoleChain,
    SelfConcept,
    UnionConcept,
    UniversalConcept,
    parse_name,
)

FRESH_IRI_PREFIX = "http://powerlifted/fresh#"
OBJECT_IRI_PREFIX = "http://powerlifted/object#"


def _is_absolute(iri):
    return ":" in iri


def entity_iri(entity):
    """The IRI an AtomicConcept/AtomicRole is written with."""
    if _is_absolute(entity.iri):
        return entity.iri
    return FRESH_IRI_PREFIX + entity.id


def vocabulary(task, ontology):
    """{task predicate name: IRI} for every unary/binary task predicate that
    is a class/object property of ontology (straight out of owl.parse_owl),
    i.e. has the same normalized name and arity — the same correspondence
    the compiled rules use (queries.names)."""
    entities = {}
    for expr, arity in [(c, 1) for c in ontology.atomic_concepts.values()] + [
        (r, 2) for r in ontology.atomic_roles.values()
    ]:
        if expr in (OWL_THING, OWL_NOTHING) or not _is_absolute(expr.iri):
            continue
        entities[expr.id] = (entity_iri(expr), arity)
    result = {}
    for predicate in task.predicates:
        entry = entities.get(parse_name(predicate.name))
        if entry is not None and entry[1] == len(predicate.arguments):
            result[predicate.name] = entry[0]
    return result


class _Writer:
    def __init__(self, object_names):
        self._objects = {parse_name(name): name for name in object_names}
        self.classes = set()
        self.properties = set()
        self.individuals = set()

    def iri(self, iri):
        return f"<{iri}>"

    def concept(self, c):
        if c == OWL_THING:
            return "owl:Thing"
        if c == OWL_NOTHING:
            return "owl:Nothing"
        if isinstance(c, AtomicConcept):
            iri = entity_iri(c)
            self.classes.add(iri)
            return self.iri(iri)
        if isinstance(c, QualifiedExistentialConcept):
            return f"ObjectSomeValuesFrom({self.role(c.role)} {self.concept(c.concept)})"
        if isinstance(c, InverseQualifiedExistentialConcept):
            return (
                f"ObjectSomeValuesFrom({self.role(InverseRole(c.role))} "
                f"{self.concept(c.concept)})"
            )
        if isinstance(c, UniversalConcept):
            return f"ObjectAllValuesFrom({self.role(c.role)} {self.concept(c.concept)})"
        if isinstance(c, InverseUniversalConcept):
            return (
                f"ObjectAllValuesFrom({self.role(InverseRole(c.role))} "
                f"{self.concept(c.concept)})"
            )
        for kind, inverse, name in (
            (MaxCardinalityConcept, False, "ObjectMaxCardinality"),
            (InverseMaxCardinalityConcept, True, "ObjectMaxCardinality"),
            (MinCardinalityConcept, False, "ObjectMinCardinality"),
            (InverseMinCardinalityConcept, True, "ObjectMinCardinality"),
        ):
            if isinstance(c, kind):
                role = InverseRole(c.role) if inverse else c.role
                return f"{name}({c.n} {self.role(role)} {self.concept(c.concept)})"
        if isinstance(c, SelfConcept):
            return f"ObjectHasSelf({self.role(c.role)})"
        if isinstance(c, Nominal):
            return f"ObjectOneOf({self.individual(c.individual)})"
        if isinstance(c, NegatedConcept):
            return f"ObjectComplementOf({self.concept(c.concept)})"
        if isinstance(c, (IntersectionConcept, UnionConcept)):
            name = (
                "ObjectIntersectionOf"
                if isinstance(c, IntersectionConcept)
                else "ObjectUnionOf"
            )
            if len(c.operands) == 1:
                return self.concept(c.operands[0])
            return f"{name}({' '.join(self.concept(o) for o in c.operands)})"
        raise ValueError(f"cannot write concept {c!r} in functional syntax")

    def role(self, r):
        if isinstance(r, AtomicRole):
            iri = entity_iri(r)
            self.properties.add(iri)
            return self.iri(iri)
        if isinstance(r, InverseRole):
            return f"ObjectInverseOf({self.role(r.role)})"
        raise ValueError(f"cannot write role {r!r} in functional syntax")

    def individual(self, individual):
        name = self._objects.get(individual.id)
        if name is not None:
            iri = OBJECT_IRI_PREFIX + name
        elif _is_absolute(individual.iri):
            iri = individual.iri
        else:
            iri = OBJECT_IRI_PREFIX + individual.id
        self.individuals.add(iri)
        return self.iri(iri)

    def axiom(self, ax):
        if isinstance(ax, ConceptInclusion):
            return f"SubClassOf({self.concept(ax.sub)} {self.concept(ax.sup)})"
        if isinstance(ax, FunctionalRole):
            return f"FunctionalObjectProperty({self.role(ax.role)})"
        if isinstance(ax, InverseFunctionalRole):
            return f"InverseFunctionalObjectProperty({self.role(ax.role)})"
        if isinstance(ax, RoleInclusion):
            if isinstance(ax.sup, NegatedRole):  # R ⊑ ¬S
                return (
                    f"DisjointObjectProperties({self.role(ax.sub)} "
                    f"{self.role(ax.sup.role)})"
                )
            if isinstance(ax.sub, RoleChain):
                chain = " ".join(self.role(r) for r in ax.sub.roles)
                sub = f"ObjectPropertyChain({chain})"
            else:
                sub = self.role(ax.sub)
            return f"SubObjectPropertyOf({sub} {self.role(ax.sup)})"
        raise ValueError(f"cannot write axiom {ax!r} in functional syntax")


def serialize_functional(axioms, iri, object_names, declared_iris=()):
    """The text of an OWL 2 functional-syntax ontology with IRI iri (none if
    empty) holding axioms, a declaration per entity they use, and the unique
    names of the task's objects (object_names).

    declared_iris ({IRI: arity}) also declares entities no axiom mentions,
    e.g. the vocabulary's: Konclude can't answer a query over an undeclared
    name."""
    writer = _Writer(object_names)
    lines = [writer.axiom(ax) for ax in axioms]
    for entity, arity in dict(declared_iris).items():
        (writer.classes if arity == 1 else writer.properties).add(entity)
    objects = sorted(OBJECT_IRI_PREFIX + name for name in object_names)
    if len(objects) > 1:
        lines.append(f"DifferentIndividuals({' '.join(f'<{o}>' for o in objects)})")
    declarations = (
        [f"Declaration(Class(<{c}>))" for c in sorted(writer.classes)]
        + [f"Declaration(ObjectProperty(<{p}>))" for p in sorted(writer.properties)]
        + [
            f"Declaration(NamedIndividual(<{i}>))"
            for i in sorted(writer.individuals | set(objects))
        ]
    )
    header = f"Ontology(<{iri}>" if iri else "Ontology("
    return "\n".join(
        ["Prefix(owl:=<http://www.w3.org/2002/07/owl#>)", "", header]
        + declarations
        + [""]
        + lines
        + [")", ""]
    )
