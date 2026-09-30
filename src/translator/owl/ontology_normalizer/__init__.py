"""
Normalize an ontology towards the 14 axiom forms (O1)-(O14) of Table 1,
page 7, Zhou et al. 2015 ("Pay-as-you-go ABox Reasoning"), and classify
each axiom into its Table 1 bucket.

Table 1 (n, m > 0; A, B atomic concepts or ⊤; R, S, T atomic roles):

    O1    A1 ⊓ … ⊓ An        ⊑ ⊥
    O2    A1 ⊓ … ⊓ An        ⊑ B1 ⊔ … ⊔ Bm
    O3    ∃R.A                ⊑ B
    O4    A                   ⊑ Self(R)
    O5    Self(R)              ⊑ A
    O6    R                   ⊑ S
    O7    R                   ⊑ S⁻
    O8    R ∘ S                ⊑ T
    O9    R ⊓ S                ⊑ ⊥
    O10   A                   ⊑ ∃R.B
    O11   A                   ⊑ ≤m R.B
    O12   A                   ⊑ {a}
    O13   ⊤                   ⊑ ∀R.A
    O14   A                   ⊑ ≥m R.B

An axiom not shaped like one of O1-O14 after normalization is classified
UNCLASSIFIED.

This __init__.py is the package's orchestrator; the passes themselves
live in sibling modules:
    fresh_symbols.py         fresh atomic concept/role introduction,
                              always as a full equivalence (both ⊑
                              directions) to what it stands in for
    concept_normalization.py concept-side passes (see its own docstring)
    role_normalization.py    role-side passes (see its own docstring)
    axiom_classification.py  Table 1 classification (O1-O14, UNCLASSIFIED)
"""

from __future__ import annotations

from owl.axioms import Ontology

from .axiom_classification import (
    O1,
    O2,
    O3,
    O4,
    O5,
    O6,
    O7,
    O8,
    O9,
    O10,
    O11,
    O12,
    O13,
    O14,
    TABLE1_LABELS,
    UNCLASSIFIED,
    _classify_axioms,
    classify_axiom,
    ensure_fully_supported,
)
from .concept_normalization import (
    _normalize_intersection_sub,
    _normalize_intersection_sup,
    _normalize_inverse_role_concept,
    _normalize_max_cardinality_LHS,
    _normalize_min_cardinality_LHS,
    _normalize_negative_concept_inclusions,
    _normalize_restriction_concept_filler,
    _normalize_union_sub,
    _normalize_union_sup,
    _normalize_universal_concept,
)
from .role_normalization import (
    _normalize_inverse_disjoint_role,
    _normalize_inverse_functional_role,
    _normalize_inverse_role_LHS,
    _normalize_role_chain_length,
)

__all__ = [
    "O1",
    "O2",
    "O3",
    "O4",
    "O5",
    "O6",
    "O7",
    "O8",
    "O9",
    "O10",
    "O11",
    "O12",
    "O13",
    "O14",
    "TABLE1_LABELS",
    "UNCLASSIFIED",
    "classify_axiom",
    "ensure_fully_supported",
    "normalize_ontology",
]


def normalize_ontology(ontology: Ontology) -> None:
    """Normalize the ontology in-place towards Table 1 and classify every
    axiom into ontology.axiom_types: rewrite negative concept inclusions,
    eliminate inverse roles from role-axiom LHSs, disjoint-role axioms,
    and inverse-functional roles, binarize role chains longer than 2,
    eliminate complex conjuncts/disjuncts, split a conjunctive sup and a
    disjunctive sub, eliminate a non-atomic ∃/∀/≤n/≥n filler, and
    eliminate inverse/universal/cardinality concept shapes to a fixpoint,
    then classify. Never raises — see ensure_fully_supported to check the
    result."""
    _normalize_negative_concept_inclusions(ontology)
    _normalize_inverse_role_LHS(ontology)
    _normalize_inverse_disjoint_role(ontology)
    _normalize_inverse_functional_role(ontology)
    _normalize_role_chain_length(ontology)
    _normalize_complex_concepts_to_fixpoint(ontology)
    _classify_axioms(ontology)


def _deduplicate_axioms(ontology: Ontology) -> None:
    """Remove duplicate axioms (same .id), keeping the first occurrence."""
    seen_ids: set[str] = set()
    deduped = []
    for ax in ontology.axioms:
        if ax.id not in seen_ids:
            seen_ids.add(ax.id)
            deduped.append(ax)
    ontology.axioms = deduped


def _normalize_complex_concepts_to_fixpoint(ontology: Ontology) -> None:
    """Run the concept-normalization passes together, repeatedly, until
    none adds an axiom: intersection-sub/union-sup flattening,
    intersection-sup and union-sub splitting, non-atomic ∃/∀/≤n/≥n filler
    elimination, inverse existential/max/min cardinality elimination,
    min/max cardinality LHS, and universal concept rewriting. Deduplicates
    once at the end — intersection-sup/union-sub splitting can produce an
    axiom that already exists elsewhere in the ontology."""
    while True:
        axiom_count_before = len(ontology.axioms)
        # TODO(dnh): Rewrite this into recursive?
        _normalize_intersection_sub(ontology)
        _normalize_union_sup(ontology)
        _normalize_intersection_sup(ontology)
        _normalize_union_sub(ontology)
        _normalize_restriction_concept_filler(ontology)
        _normalize_inverse_role_concept(ontology)
        _normalize_min_cardinality_LHS(ontology)
        _normalize_max_cardinality_LHS(ontology)
        _normalize_universal_concept(ontology)
        if len(ontology.axioms) == axiom_count_before:
            break
    _deduplicate_axioms(ontology)
