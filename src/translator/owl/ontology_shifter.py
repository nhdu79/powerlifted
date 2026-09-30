"""
"Shifting" (Zhou et al. 2015, Definition 4.3, page 13) defined directly
on normalized DL axioms — for O2 (A1⊓...⊓An ⊑ B1⊔...⊔Bm, m>=2)
specifically, reading the axiom itself as form (4): LHS conjuncts as
body atoms, RHS disjuncts as head atoms. Each Bj gets a fresh complement
concept B'j (owl.ontology_normalizer.fresh_symbols' existing comp_
convention); the LHS conjuncts are always safe to drop (every DL axiom
conjunct/disjunct is about the same single variable, so Definition
4.3's per-body-atom safety side condition holds trivially). The result
feeds directly into rules.lowerbound.lowerbound_rules.shifted_ontology_axioms,
serialized and handed to Clipper — the lowerbound is computed entirely
by Clipper now, with no separate rule-level shifting step.

For A1 ⊑ B1⊔B2 this produces:
  (S1)   A1 ⊓ B'1 ⊓ B'2 ⊑ ⊥
  (S2_1) A1 ⊓ B'2 ⊑ B1
  (S2_2) A1 ⊓ B'1 ⊑ B2
  (S3_1) B'1 ⊓ B'2 ⊑ A'1

An O2 axiom with only one disjunct (m=1, an ordinary A⊑B) is already
deterministic and Horn — shift_o2_axiom passes it through unchanged
rather than shifting it, so shift_ontology's output already covers
every O2 axiom in the ontology, not just the disjunctive ones.
"""

from __future__ import annotations

import copy

from owl.axioms import ConceptInclusion, Ontology
from owl.expressions import (
    OWL_NOTHING,
    AtomicConcept,
    ConceptExpression,
    IntersectionConcept,
    UnionConcept,
)
from owl.ontology_normalizer import O2
from owl.ontology_normalizer.fresh_symbols import fresh_complement_concept_for


def _conjuncts(concept: ConceptExpression) -> tuple[AtomicConcept, ...]:
    return concept.operands if isinstance(concept, IntersectionConcept) else (concept,)


def _disjuncts(concept: ConceptExpression) -> tuple[AtomicConcept, ...]:
    return concept.operands if isinstance(concept, UnionConcept) else (concept,)


def _conjunction(concepts: list[AtomicConcept]) -> ConceptExpression:
    return concepts[0] if len(concepts) == 1 else IntersectionConcept(tuple(concepts))


def shift_o2_axiom(ax: ConceptInclusion) -> list[ConceptInclusion]:
    """shift(ax) for an O2 axiom, or [ax] itself if it has fewer than 2
    disjuncts (m=1: already deterministic, nothing to shift)."""
    conjuncts = _conjuncts(ax.sub)
    disjuncts = _disjuncts(ax.sup)
    if len(disjuncts) < 2:
        return [ax]

    complements = [fresh_complement_concept_for(d) for d in disjuncts]

    s1_lhs = _conjunction(list(conjuncts) + complements)
    shifted = [ConceptInclusion(s1_lhs, OWL_NOTHING)]

    for j, disjunct in enumerate(disjuncts):
        others = complements[:j] + complements[j + 1 :]
        shifted.append(
            ConceptInclusion(_conjunction(list(conjuncts) + others), disjunct)
        )

    for i, conjunct in enumerate(conjuncts):
        others = conjuncts[:i] + conjuncts[i + 1 :]
        shifted.append(
            ConceptInclusion(
                _conjunction(list(others) + complements),
                fresh_complement_concept_for(conjunct),
            )
        )

    return shifted


def shift_ontology(ontology: Ontology) -> list[ConceptInclusion]:
    """shift(Σ) over every one of Σ's O2 axioms — m>=2 ones shifted,
    m=1 ones passed through unchanged (see shift_o2_axiom). Operates on
    a deep copy of ontology, never the original object: the same
    normalized Ontology is also needed unmodified elsewhere (e.g. for
    the Table 1 rules used to compute the upperbound), so shifting must
    never be able to affect it, now or after a future change here."""
    ontology_copy = copy.deepcopy(ontology)
    return [
        shifted
        for ax in ontology_copy.axiom_types.get(O2, ())
        for shifted in shift_o2_axiom(ax)
    ]
