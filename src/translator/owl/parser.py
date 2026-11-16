"""
OWL ontology parser backed by rdflib.

Parses an OWL Turtle file and normalises its TBox axioms into the uniform
`sub`-predicate form used by owl.axioms (ConceptInclusion/RoleInclusion),
using the expression types defined in owl.expressions.

Supported OWL constructors:
  owl:ObjectProperty, owl:FunctionalProperty, owl:InverseFunctionalProperty
  owl:SymmetricProperty                                                    → P ⊑ P⁻
  owl:propertyDisjointWith                                                 → P ⊑ ¬Q
  owl:inverseOf (direct axiom on a named property)                        (P ≡ Q⁻ →
                                                                             P ⊑ Q⁻, Q ⊑ P⁻)
  rdfs:subPropertyOf, rdfs:domain, rdfs:range
  owl:Class with rdfs:subClassOf, owl:disjointWith, owl:equivalentClass
                                                                             (A ≡ B → A ⊑ B, B ⊑ A)
  owl:Nothing                                                              → ⊥  (OWL_NOTHING)
  owl:propertyChainAxiom (P1 P2 …)                                        → RoleChain(P1,…,Pn) ⊑ Q
  Blank-node restriction  owl:onProperty P + owl:someValuesFrom A/⊤      → ∃P.A | ∃P⁻.A
                                                                             (∃P / ∃P⁻ when A is ⊤)
  Blank-node restriction  owl:onProperty P + owl:allValuesFrom A/⊤       → ∀P.A | ∀P⁻.A
  Blank-node restriction  owl:onProperty P + owl:hasSelf "true"^^xsd:boolean → Self(P)
                                                                             (P atomic only)
  Blank-node restriction  owl:onProperty P + owl:maxQualifiedCardinality n
                           + owl:onClass A                                → ≤nP.A | ≤nP⁻.A
  Blank-node restriction  owl:onProperty P + owl:minQualifiedCardinality n
                           + owl:onClass A                                → ≥nP.A | ≥nP⁻.A
  Blank-node intersection owl:intersectionOf (A B …)                      → A ⊓ B
  Blank-node union        owl:unionOf (A B …)                             → A ⊔ B
  Blank-node enumeration  owl:oneOf (a …)                                  → {a} | {a} ⊔ …
  General (blank-node subject) subClassOf / disjointWith axioms

Unsupported constructs (unqualified owl:cardinality/owl:maxCardinality/
owl:minCardinality, owl:hasValue, owl:complementOf, and everything else
outside the list above) are recorded in Ontology.warnings rather than
raising; call Ontology.is_supported to check. Parsing itself never aborts;
owl.ontology_normalizer.ensure_fully_supported is the place to raise
(UnsupportedConstructError) once an ontology is actually about to be used,
e.g. for planning — see its docstring.
"""

from __future__ import annotations

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS


class UnsupportedConstructError(Exception):
    """Raised when an ontology that's about to be used isn't fully
    supported — see owl.ontology_normalizer.ensure_fully_supported."""


from owl.axioms import (
    ConceptInclusion,
    FunctionalRole,
    InverseFunctionalRole,
    Ontology,
    RoleInclusion,
)
from owl.expressions import (
    OWL_NOTHING,
    OWL_THING,
    AtomicConcept,
    AtomicRole,
    ConceptExpression,
    Individual,
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
    RoleExpression,
    SelfConcept,
    UnionConcept,
    UniversalConcept,
    _local_name,
)

# ---------------------------------------------------------------------------
# OWL vocabulary coverage  (post-parse coverage scan)
#
# For each structural role a term can play, _ALL_* names every OWL2 term
# with real TBox/RBox semantics that can appear there; _SUPPORTED_* is the
# (small, explicit) subset this parser actually implements. A term added to
# _ALL_* and never marked supported is caught automatically by any code that
# checks _SUPPORTED_* membership directly, instead of silently slipping
# through because nobody remembered to also add it to a separate
# hand-maintained "unsupported" list.
#
# Deliberately excluded from every _ALL_* below (not "unsupported", simply
# out of scope): ABox assertions/individuals, ontology annotation and
# versioning vocabulary (owl:versionInfo, owl:imports, axiom reification via
# owl:Axiom/owl:annotatedSource, …), and datatype/facet vocabulary — none of
# these carry TBox/RBox logical content this parser models.
# ---------------------------------------------------------------------------


# rdf:type values on a property, characterising it
_ALL_PROPERTY_TYPES: dict = {
    OWL.ObjectProperty: "owl:ObjectProperty",
    OWL.FunctionalProperty: "owl:FunctionalProperty",
    OWL.InverseFunctionalProperty: "owl:InverseFunctionalProperty",
    OWL.SymmetricProperty: "owl:SymmetricProperty",
    OWL.DatatypeProperty: "owl:DatatypeProperty",
    OWL.TransitiveProperty: "owl:TransitiveProperty",
    OWL.AsymmetricProperty: "owl:AsymmetricProperty",
    OWL.ReflexiveProperty: "owl:ReflexiveProperty",
    OWL.IrreflexiveProperty: "owl:IrreflexiveProperty",
}
_SUPPORTED_PROPERTY_TYPES = {
    OWL.ObjectProperty,
    OWL.FunctionalProperty,
    OWL.InverseFunctionalProperty,
    OWL.SymmetricProperty,
}

# Predicates that form a standalone axiom (checked on any subject)
_ALL_AXIOM_PREDS: dict = {
    OWL.disjointWith: "owl:disjointWith",
    OWL.propertyChainAxiom: "owl:propertyChainAxiom",
    OWL.equivalentClass: "owl:equivalentClass",
    OWL.equivalentProperty: "owl:equivalentProperty",
    OWL.hasKey: "owl:hasKey",
    OWL.disjointUnionOf: "owl:disjointUnionOf",
    OWL.propertyDisjointWith: "owl:propertyDisjointWith",
    OWL.inverseOf: "owl:inverseOf",
}
_SUPPORTED_AXIOM_PREDS = {
    OWL.disjointWith,
    OWL.propertyChainAxiom,
    OWL.propertyDisjointWith,
    OWL.equivalentClass,
    OWL.inverseOf,
}
# owl:inverseOf also has a second, unrelated usage as the filler of a
# blank-node role expression (e.g. [owl:inverseOf :P] inside rdfs:subPropertyOf
# or an owl:onProperty) — that's handled separately by _resolve_role, not by
# the standalone-axiom collection this dict drives.

# rdf:type values marking a blank node as bundling its own axiom
_ALL_META_TYPES: dict = {
    OWL.AllDisjointClasses: "owl:AllDisjointClasses",
    OWL.AllDisjointProperties: "owl:AllDisjointProperties",
    OWL.NegativePropertyAssertion: "owl:NegativePropertyAssertion",
    OWL.AllDifferent: "owl:AllDifferent",
}
_SUPPORTED_META_TYPES: set = set()

# Predicates recognised as the filler of a blank-node class expression
_ALL_CLASS_EXPRS: dict = {
    OWL.intersectionOf: "owl:intersectionOf",
    OWL.unionOf: "owl:unionOf",
    OWL.oneOf: "owl:oneOf",
    OWL.complementOf: "owl:complementOf",
}
_SUPPORTED_CLASS_EXPRS = {OWL.intersectionOf, OWL.unionOf, OWL.oneOf}

# Predicates recognised as the filler of an owl:Restriction
_ALL_RESTRICTIONS: dict = {
    OWL.someValuesFrom: "owl:someValuesFrom",
    OWL.allValuesFrom: "owl:allValuesFrom",
    OWL.hasSelf: "owl:hasSelf",
    OWL.maxQualifiedCardinality: "owl:maxQualifiedCardinality",
    OWL.minQualifiedCardinality: "owl:minQualifiedCardinality",
    OWL.hasValue: "owl:hasValue",
    OWL.maxCardinality: "owl:maxCardinality",
    OWL.minCardinality: "owl:minCardinality",
    OWL.cardinality: "owl:cardinality",
    OWL.qualifiedCardinality: "owl:qualifiedCardinality",
}
_SUPPORTED_RESTRICTIONS = {
    OWL.someValuesFrom,
    OWL.allValuesFrom,
    OWL.hasSelf,
    OWL.maxQualifiedCardinality,
    OWL.minQualifiedCardinality,
}
# owl:hasValue, owl:maxCardinality, owl:minCardinality, owl:cardinality, and
# owl:qualifiedCardinality (unqualified/plain cardinality forms — no
# owl:onClass filler) stay out of _SUPPORTED_RESTRICTIONS and fall through to
# the generic unsupported-restriction warning loop below like any other
# unhandled restriction predicate.


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------


class _OWLBuilder:
    """Walks an rdflib Graph and populates an Ontology."""

    def __init__(self, graph: Graph) -> None:
        self._g = graph
        self._onto = Ontology(iri="")
        # IRI-keyed lookups for resolving named nodes during axiom collection
        self._concepts_by_iri: dict[str, AtomicConcept] = {}
        self._roles_by_iri: dict[str, AtomicRole] = {}

    def _warn(self, msg: str) -> None:
        self._onto.warnings.append(msg)

    # ------------------------------------------------------------------
    # Top-level entry point
    # ------------------------------------------------------------------

    def build(self) -> Ontology:
        self._collect_ontology_iri()
        self._collect_atomic_concepts()  # named classes + their negations
        self._collect_atomic_roles()  # named roles + negation/inverse/unqualified ∃
        self._collect_role_axioms()  # funct, invFunct, symmetric, subPropertyOf, domain, range
        self._collect_property_chains()  # propertyChainAxiom → RoleInclusion(RoleChain, Q)
        self._collect_concept_axioms()  # subClassOf, disjointWith on named subjects
        self._collect_general_axioms()  # subClassOf, disjointWith on blank-node subjects
        self._scan_unsupported()  # warn about constructs outside the supported fragment
        self._deduplicate_axioms()
        return self._onto

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def _add_concept(self, expr: ConceptExpression) -> ConceptExpression:
        self._onto.concepts[expr.id] = expr
        return expr

    def _add_role(self, expr: RoleExpression) -> RoleExpression:
        self._onto.roles[expr.id] = expr
        return expr

    def _add_axiom(self, ax) -> None:
        self._onto.axioms.append(ax)

    # ------------------------------------------------------------------
    # Entity collection — named classes and properties, and the expressions
    # derived from them (negation, inverse, unqualified domain/range)
    # ------------------------------------------------------------------

    def _collect_ontology_iri(self) -> None:
        for s in self._g.subjects(RDF.type, OWL.Ontology):
            self._onto.iri = str(s)
            return

    def _collect_atomic_concepts(self) -> None:
        """Register every named owl:Class as an AtomicConcept, plus its negation."""
        for s in self._g.subjects(RDF.type, OWL.Class):
            if isinstance(s, BNode):
                continue
            c = AtomicConcept(str(s))
            self._concepts_by_iri[c.iri] = c
            self._add_concept(c)
            self._add_concept(NegatedConcept(c))

    def _collect_atomic_roles(self) -> None:
        """Register every named owl:ObjectProperty P as an AtomicRole, plus its
        negation, its inverse P⁻ (and that inverse's negation), and the
        unqualified domain/range existentials ∃P / ∃P⁻ (plus their negations)."""
        for s in self._g.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, BNode):
                continue
            r = AtomicRole(str(s))
            self._roles_by_iri[r.iri] = r
            self._add_role(r)
            self._add_role(NegatedRole(r))
            inv_r = InverseRole(r)
            self._add_role(inv_r)
            self._add_role(NegatedRole(inv_r))

            ex = QualifiedExistentialConcept(r, OWL_THING)
            self._add_concept(ex)
            self._add_concept(NegatedConcept(ex))

            inv_ex = InverseQualifiedExistentialConcept(r, OWL_THING)
            self._add_concept(inv_ex)
            self._add_concept(NegatedConcept(inv_ex))

    # ------------------------------------------------------------------
    # Axiom collection
    # ------------------------------------------------------------------

    def _collect_role_axioms(self) -> None:
        """Collect axioms attached directly to each named role: functional and
        inverse-functional characteristics, symmetric (P ⊑ P⁻),
        propertyDisjointWith (P ⊑ ¬Q), inverseOf (P ≡ Q⁻, as P ⊑ Q⁻ and
        Q ⊑ P⁻), subPropertyOf, and domain/range (as ∃P ⊑ X / ∃P⁻ ⊑ X)."""
        for r_iri, role in self._roles_by_iri.items():
            node = URIRef(r_iri)

            if (node, RDF.type, OWL.FunctionalProperty) in self._g:
                self._add_axiom(FunctionalRole(role))

            if (node, RDF.type, OWL.InverseFunctionalProperty) in self._g:
                self._add_axiom(InverseFunctionalRole(role))

            if (node, RDF.type, OWL.SymmetricProperty) in self._g:
                self._add_axiom(RoleInclusion(role, InverseRole(role)))

            for disjoint_node in self._g.objects(node, OWL.propertyDisjointWith):
                sup = self._resolve_role(disjoint_node)
                if sup is not None:
                    self._add_axiom(RoleInclusion(role, NegatedRole(sup)))

            for inv_node in self._g.objects(node, OWL.inverseOf):
                inv = self._resolve_role(inv_node)
                if inv is not None:
                    self._add_axiom(RoleInclusion(role, InverseRole(inv)))
                    self._add_axiom(RoleInclusion(inv, InverseRole(role)))

            for sup_node in self._g.objects(node, RDFS.subPropertyOf):
                sup = self._resolve_role(sup_node)
                if sup is not None:
                    self._add_axiom(RoleInclusion(role, sup))

            for domain_node in self._g.objects(node, RDFS.domain):
                sup = self._resolve_concept(domain_node)
                if sup is not None:
                    self._add_axiom(
                        ConceptInclusion(
                            QualifiedExistentialConcept(role, OWL_THING), sup
                        )
                    )

            for range_node in self._g.objects(node, RDFS.range):
                sup = self._resolve_concept(range_node)
                if sup is not None:
                    self._add_axiom(
                        ConceptInclusion(
                            InverseQualifiedExistentialConcept(role, OWL_THING), sup
                        )
                    )

    def _collect_property_chains(self) -> None:
        """Collect owl:propertyChainAxiom (P1 … Pn) as RoleInclusion(RoleChain, Q).

        Order is preserved (composition is not commutative); if any chain
        member or the chain's own property fails to resolve, the whole axiom
        is dropped rather than silently built from a partial member list.
        """
        for subject, chain_head in self._g.subject_objects(OWL.propertyChainAxiom):
            sup = self._resolve_role(subject)
            if sup is None:
                self._warn(
                    "owl:propertyChainAxiom on an unresolvable role — axiom ignored"
                )
                continue

            chain_members = self._rdf_list(chain_head)
            if len(chain_members) < 2:
                self._warn(
                    "owl:propertyChainAxiom with fewer than 2 roles — axiom ignored"
                )
                continue

            resolved = [self._resolve_role(m) for m in chain_members]
            if any(r is None for r in resolved):
                self._warn(
                    "owl:propertyChainAxiom contains an unresolvable role — axiom ignored"
                )
                continue

            chain = RoleChain(tuple(resolved))
            self._add_role(chain)
            self._add_axiom(RoleInclusion(chain, sup))

    def _collect_concept_axioms(self) -> None:
        """Collect subClassOf/disjointWith/equivalentClass axioms whose
        subject is a named (non-blank-node) class."""
        for c_iri, concept in self._concepts_by_iri.items():
            node = URIRef(c_iri)

            for sup_node in self._g.objects(node, RDFS.subClassOf):
                sup = self._resolve_concept(sup_node)
                if sup is not None:
                    self._add_axiom(ConceptInclusion(concept, sup))

            for disjoint_node in self._g.objects(node, OWL.disjointWith):
                sup = self._resolve_concept(disjoint_node)
                if sup is not None:
                    self._add_axiom(ConceptInclusion(concept, NegatedConcept(sup)))

            for equiv_node in self._g.objects(node, OWL.equivalentClass):
                equiv = self._resolve_concept(equiv_node)
                if equiv is not None:
                    self._add_axiom(ConceptInclusion(concept, equiv))
                    self._add_axiom(ConceptInclusion(equiv, concept))

    def _collect_general_axioms(self) -> None:
        """Collect subClassOf/disjointWith/equivalentClass axioms whose
        subject is a blank-node class expression (general TBox axioms).
        rdf:List nodes are skipped."""
        visited: set = set()
        for predicate in (RDFS.subClassOf, OWL.disjointWith, OWL.equivalentClass):
            for subject in self._g.subjects(predicate, None):
                if not isinstance(subject, BNode) or subject in visited:
                    continue
                if (subject, RDF.first, None) in self._g:
                    continue  # rdf:List node — not an axiom subject
                visited.add(subject)

                sub_expr = self._resolve_concept(subject)
                if sub_expr is None:
                    continue
                # sub_expr itself is already registered by _resolve_concept; also
                # pre-register its negation for compound concepts that appear only
                # as the subject of a general axiom.
                if isinstance(
                    sub_expr,
                    (
                        IntersectionConcept,
                        UnionConcept,
                        QualifiedExistentialConcept,
                        InverseQualifiedExistentialConcept,
                        UniversalConcept,
                        InverseUniversalConcept,
                        MaxCardinalityConcept,
                        InverseMaxCardinalityConcept,
                        MinCardinalityConcept,
                        InverseMinCardinalityConcept,
                        SelfConcept,
                        Nominal,
                    ),
                ):
                    self._add_concept(NegatedConcept(sub_expr))

                for sup_node in self._g.objects(subject, RDFS.subClassOf):
                    sup = self._resolve_concept(sup_node)
                    if sup is not None:
                        self._add_axiom(ConceptInclusion(sub_expr, sup))
                for disjoint_node in self._g.objects(subject, OWL.disjointWith):
                    sup = self._resolve_concept(disjoint_node)
                    if sup is not None:
                        self._add_axiom(ConceptInclusion(sub_expr, NegatedConcept(sup)))
                for equiv_node in self._g.objects(subject, OWL.equivalentClass):
                    equiv = self._resolve_concept(equiv_node)
                    if equiv is not None:
                        self._add_axiom(ConceptInclusion(sub_expr, equiv))
                        self._add_axiom(ConceptInclusion(equiv, sub_expr))

    # ------------------------------------------------------------------
    # Node resolvers — turn rdflib nodes into expression objects
    # ------------------------------------------------------------------

    def _resolve_concept(self, node) -> ConceptExpression | None:
        """
        Named IRI            → AtomicConcept (looked up by IRI)
        owl:Thing            → OWL_THING singleton
        Restriction BNode    → QualifiedExistentialConcept(P, A) |
                                InverseQualifiedExistentialConcept(P, A) |
                                UniversalConcept(P, A) |
                                InverseUniversalConcept(P, A) |
                                MaxCardinalityConcept(P, n, A) |
                                InverseMaxCardinalityConcept(P, n, A) |
                                MinCardinalityConcept(P, n, A) |
                                InverseMinCardinalityConcept(P, n, A) |
                                SelfConcept(P)
                                (owl:someValuesFrom / owl:allValuesFrom /
                                owl:maxQualifiedCardinality+owl:onClass /
                                owl:minQualifiedCardinality+owl:onClass / owl:hasSelf;
                                A is OWL_THING for the unqualified ∃P / ∃P⁻ / ∀P / ∀P⁻ case)
        Intersection BNode   → IntersectionConcept(operands)   (owl:intersectionOf)
        Union BNode          → UnionConcept(operands)          (owl:unionOf)
        Enumeration BNode    → Nominal(a) | UnionConcept of Nominal(a_i)  (owl:oneOf)
        Unsupported node (e.g. owl:hasValue, unqualified owl:maxCardinality/
        owl:minCardinality/owl:cardinality, owl:complementOf)
                             → None  (warning recorded in ontology.warnings)

        Any compound expression built here (i.e. everything but a bare named
        AtomicConcept) is registered into ontology.concepts before being
        returned, regardless of whether it ends up as an axiom's sub or sup.
        """
        if isinstance(node, URIRef):
            if node == OWL.Thing:
                return OWL_THING
            if node == OWL.Nothing:
                return OWL_NOTHING
            iri = str(node)
            return self._concepts_by_iri.get(iri) or AtomicConcept(iri)

        if (node, RDF.type, OWL.Restriction) in self._g:
            return self._register(self._resolve_restriction(node))

        union_head = self._g.value(node, OWL.unionOf)
        if union_head is not None:
            return self._register(self._resolve_union(union_head))

        one_of_head = self._g.value(node, OWL.oneOf)
        if one_of_head is not None:
            return self._register(self._resolve_one_of(one_of_head))

        intersection_head = self._g.value(node, OWL.intersectionOf)
        if intersection_head is not None:
            return self._register(self._resolve_intersection(intersection_head))

        for pred_uri, label in _ALL_CLASS_EXPRS.items():
            if pred_uri in _SUPPORTED_CLASS_EXPRS:
                continue
            if (node, pred_uri, None) in self._g:
                self._warn(f"unsupported class expression {label} — axiom ignored")
                return None

        self._warn(f"unrecognized blank-node class expression {node!r} — axiom ignored")
        return None

    def _register(self, expr: ConceptExpression | None) -> ConceptExpression | None:
        """Register a freshly-built compound concept expression, if any, and return it."""
        if expr is not None:
            self._add_concept(expr)
        return expr

    def _resolve_restriction(self, node) -> ConceptExpression | None:
        """Handle an owl:Restriction blank node.

        owl:someValuesFrom A → QualifiedExistentialConcept(P, A)
                                | InverseQualifiedExistentialConcept(P, A)   (∃P.A / ∃P⁻.A;
                                A is OWL_THING for the unqualified ∃P / ∃P⁻ case)
        owl:allValuesFrom A  → UniversalConcept(P, A)
                                | InverseUniversalConcept(P, A)   (∀P.A / ∀P⁻.A;
                                A is OWL_THING for the unqualified ∀P / ∀P⁻ case)
        owl:hasSelf true     → SelfConcept(P)   (Self(P); P must be atomic)
        owl:maxQualifiedCardinality n + owl:onClass A
                             → MaxCardinalityConcept(P, n, A)
                               | InverseMaxCardinalityConcept(P, n, A)   (≤nP.A / ≤nP⁻.A)
        owl:minQualifiedCardinality n + owl:onClass A
                             → MinCardinalityConcept(P, n, A)
                               | InverseMinCardinalityConcept(P, n, A)   (≥nP.A / ≥nP⁻.A)
        Anything else (owl:hasValue, unqualified owl:maxCardinality/
        owl:minCardinality/owl:cardinality, …) falls through to the generic
        unsupported-restriction warning below.
        """
        prop_node = self._g.value(node, OWL.onProperty)

        some_filler = self._g.value(node, OWL.someValuesFrom)
        if some_filler is not None:
            role = self._resolve_role(prop_node)
            if role is None:
                return None
            filler = self._resolve_concept(some_filler)
            if filler is None:
                return None
            if isinstance(role, InverseRole):
                return InverseQualifiedExistentialConcept(role.role, filler)
            return QualifiedExistentialConcept(role, filler)

        all_filler = self._g.value(node, OWL.allValuesFrom)
        if all_filler is not None:
            role = self._resolve_role(prop_node)
            if role is None:
                return None
            filler = self._resolve_concept(all_filler)
            if filler is None:
                return None
            if isinstance(role, InverseRole):
                return InverseUniversalConcept(role.role, filler)
            return UniversalConcept(role, filler)

        has_self = self._g.value(node, OWL.hasSelf)
        if has_self is not None:
            role = self._resolve_role(prop_node)
            if role is None:
                return None
            if not isinstance(role, AtomicRole):
                self._warn("owl:hasSelf on a non-atomic role — restriction ignored")
                return None
            return SelfConcept(role)

        max_qualified = self._g.value(node, OWL.maxQualifiedCardinality)
        if max_qualified is not None:
            return self._resolve_qualified_cardinality(
                node,
                prop_node,
                max_qualified,
                "owl:maxQualifiedCardinality",
                MaxCardinalityConcept,
                InverseMaxCardinalityConcept,
            )

        min_qualified = self._g.value(node, OWL.minQualifiedCardinality)
        if min_qualified is not None:
            return self._resolve_qualified_cardinality(
                node,
                prop_node,
                min_qualified,
                "owl:minQualifiedCardinality",
                MinCardinalityConcept,
                InverseMinCardinalityConcept,
            )

        for pred_uri, label in _ALL_RESTRICTIONS.items():
            if pred_uri in _SUPPORTED_RESTRICTIONS:
                continue
            if (node, pred_uri, None) in self._g:
                self._warn(
                    f"unsupported OWL restriction {label} — axiom containing it ignored"
                )
                return None
        self._warn(
            "unsupported owl:Restriction (no recognized filler predicate) — axiom ignored"
        )
        return None

    def _resolve_qualified_cardinality(
        self, node, prop_node, literal, pred_label, positive_cls, inverse_cls
    ) -> ConceptExpression | None:
        """Shared owl:maxQualifiedCardinality / owl:minQualifiedCardinality handling:
        resolve P, require owl:onClass A, parse the integer bound n, and build
        positive_cls(P, n, A) or inverse_cls(P, n, A) depending on P's direction."""
        role = self._resolve_role(prop_node)
        if role is None:
            return None
        on_class = self._g.value(node, OWL.onClass)
        if on_class is None:
            self._warn(f"{pred_label} without owl:onClass — restriction ignored")
            return None
        filler = self._resolve_concept(on_class)
        if filler is None:
            return None
        try:
            n = int(literal)
        except (TypeError, ValueError):
            self._warn(
                f"{pred_label} value {literal!r} is not an integer — restriction ignored"
            )
            return None
        if isinstance(role, InverseRole):
            return inverse_cls(role.role, n, filler)
        return positive_cls(role, n, filler)

    def _resolve_intersection(self, list_head) -> ConceptExpression | None:
        """Handle an owl:intersectionOf list; requires at least 2 resolvable operands."""
        operands = tuple(
            op
            for op in (self._resolve_concept(m) for m in self._rdf_list(list_head))
            if op is not None
        )
        if len(operands) < 2:
            self._warn(
                "owl:intersectionOf with fewer than 2 resolvable operands — axiom ignored"
            )
            return None
        return IntersectionConcept(operands)

    def _resolve_union(self, list_head) -> ConceptExpression | None:
        """Handle an owl:unionOf list; requires at least 2 resolvable operands."""
        operands = tuple(
            op
            for op in (self._resolve_concept(m) for m in self._rdf_list(list_head))
            if op is not None
        )
        if len(operands) < 2:
            self._warn(
                "owl:unionOf with fewer than 2 resolvable operands — axiom ignored"
            )
            return None
        return UnionConcept(operands)

    def _resolve_one_of(self, list_head) -> ConceptExpression | None:
        """Handle an owl:oneOf list of individuals: {a} for one member, {a} ⊔ … for several."""
        members = self._rdf_list(list_head)
        if not members:
            self._warn("owl:oneOf with no members — axiom ignored")
            return None
        nominals = []
        for member in members:
            if not isinstance(member, URIRef):
                self._warn(
                    "owl:oneOf member is not a named individual — enumeration ignored"
                )
                return None
            nominals.append(Nominal(Individual(str(member))))
        if len(nominals) == 1:
            return nominals[0]
        return UnionConcept(tuple(nominals))

    def _resolve_role(self, node) -> AtomicRole | InverseRole | None:
        if isinstance(node, BNode):
            # Support [owl:inverseOf :P] as an inline inverse-role expression.
            inverse_of = self._g.value(node, OWL.inverseOf)
            if inverse_of is not None:
                inner = self._roles_by_iri.get(str(inverse_of)) or AtomicRole(
                    str(inverse_of)
                )
                return InverseRole(inner)
            self._warn("anonymous (blank-node) role expression — axiom ignored")
            return None
        iri = str(node)
        return self._roles_by_iri.get(iri) or AtomicRole(iri)

    def _rdf_list(self, head) -> list:
        """Walk an rdf:List and return its items."""
        items = []
        current = head
        while current and current != RDF.nil:
            first = self._g.value(current, RDF.first)
            if first is not None:
                items.append(first)
            current = self._g.value(current, RDF.rest)
        return items

    # ------------------------------------------------------------------
    # Post-parse helpers
    # ------------------------------------------------------------------

    def _deduplicate_axioms(self) -> None:
        seen: set[str] = set()
        deduped = []
        for ax in self._onto.axioms:
            if ax.id not in seen:
                seen.add(ax.id)
                deduped.append(ax)
        self._onto.axioms = deduped

    # ------------------------------------------------------------------
    # Post-parse coverage scan
    # ------------------------------------------------------------------

    def _scan_unsupported(self) -> None:
        """
        Warn about OWL/RDFS predicates and types that carry axiom semantics
        but are not handled by any collection method.  These were silently
        skipped; this scan makes the omission explicit.
        """
        for type_uri, label in _ALL_PROPERTY_TYPES.items():
            if type_uri in _SUPPORTED_PROPERTY_TYPES:
                continue
            for s in self._g.subjects(RDF.type, type_uri):
                if not isinstance(s, BNode):
                    self._warn(
                        f"unsupported property characteristic {label} on "
                        f"<{_local_name(str(s))}> — axioms involving this property may be incomplete"
                    )

        for pred_uri, label in _ALL_AXIOM_PREDS.items():
            if pred_uri in _SUPPORTED_AXIOM_PREDS:
                continue
            seen: set[str] = set()
            for s in self._g.subjects(pred_uri, None):
                key = str(s)
                if key not in seen:
                    seen.add(key)
                    subject_repr = (
                        _local_name(key) if isinstance(s, URIRef) else "anonymous"
                    )
                    self._warn(
                        f"unsupported axiom predicate {label} on "
                        f"<{subject_repr}> — axiom ignored"
                    )

        for type_uri, label in _ALL_META_TYPES.items():
            if type_uri in _SUPPORTED_META_TYPES:
                continue
            for _ in self._g.subjects(RDF.type, type_uri):
                self._warn(f"unsupported axiom type {label} — axiom ignored")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_owl(path: str) -> Ontology:
    """Parse an OWL Turtle file and return a normalised Ontology."""
    g = Graph()
    g.parse(path, format="turtle")
    return _OWLBuilder(g).build()
