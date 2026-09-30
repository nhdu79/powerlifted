"""
Regression tests for owl.ontology_normalizer.role_normalization.

No test framework is used elsewhere in this repo (see CLAUDE.md); this uses
only the standard-library unittest module. Run with:

    python3 src/translator/owl/ontology_normalizer/tests/test_role_normalization.py

from anywhere (the `owl` package path is resolved relative to this file,
not the current working directory).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_TRANSLATOR_DIR = _THIS_DIR.parent.parent.parent
if str(_TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl.axioms import (  # noqa: E402
    FunctionalRole,
    InverseFunctionalRole,
    Ontology,
    RoleInclusion,
)
from owl.ontology_normalizer.axiom_classification import (  # noqa: E402
    O6,
    O7,
    O8,
    O9,
    O11,
    UNCLASSIFIED,
    classify_axiom,
)
from owl.expressions import (  # noqa: E402
    AtomicRole,
    InverseRole,
    NegatedRole,
    RoleChain,
)
from owl.ontology_normalizer import normalize_ontology  # noqa: E402
from owl.ontology_normalizer.role_normalization import (  # noqa: E402
    _normalize_inverse_disjoint_role,
    _normalize_inverse_functional_role,
    _normalize_inverse_role_LHS,
    _normalize_role_chain_length,
)


class NormalizeRoleChainLengthTest(unittest.TestCase):
    """Direct tests of _normalize_role_chain_length in isolation, on an
    already-atomic chain R1 ∘ R2 ∘ R3 ⊑ S (inverse-role elimination is
    _normalize_inverse_role_LHS's job, tested separately below)."""

    def setUp(self):
        self.r1, self.r2, self.r3, self.s = (
            AtomicRole("http://ex/R1"),
            AtomicRole("http://ex/R2"),
            AtomicRole("http://ex/R3"),
            AtomicRole("http://ex/S"),
        )
        self.chain = RoleChain((self.r1, self.r2, self.r3))
        self.axiom = RoleInclusion(self.chain, self.s)
        self.ontology = Ontology(iri="http://ex", axioms=[self.axiom])

    def test_binarized_into_two_o8_axioms(self):
        _normalize_role_chain_length(self.ontology)

        self.assertEqual(len(self.ontology.axioms), 2)
        for ax in self.ontology.axioms:
            self.assertIsInstance(ax, RoleInclusion)
            self.assertIsInstance(ax.sub, RoleChain)
            self.assertEqual(len(ax.sub.roles), 2)
            self.assertEqual(classify_axiom(ax), O8)

        # The final axiom's target is the original super-role S.
        final = [ax for ax in self.ontology.axioms if ax.sup == self.s]
        self.assertEqual(len(final), 1)
        # The fresh intermediate role is registered, alongside its negation.
        fresh = final[0].sub.roles[0]
        self.assertIsInstance(fresh, AtomicRole)
        self.assertIn(fresh.id, self.ontology.roles)
        self.assertIn(f"not_{fresh.id}", self.ontology.roles)

    def test_two_role_chains_are_untouched(self):
        plain = Ontology(
            iri="http://ex",
            axioms=[RoleInclusion(RoleChain((self.r1, self.r2)), self.s)],
        )
        before = list(plain.axioms)
        _normalize_role_chain_length(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        _normalize_role_chain_length(self.ontology)
        once = list(self.ontology.axioms)
        _normalize_role_chain_length(self.ontology)
        self.assertEqual(once, self.ontology.axioms)

    def test_normalize_ontology_fully_classifies(self):
        normalize_ontology(self.ontology)
        sizes = {label: len(axs) for label, axs in self.ontology.axiom_types.items()}
        self.assertEqual(sizes[O8], 2)
        self.assertEqual(sizes[UNCLASSIFIED], 0)


class NormalizeInverseRoleLHSTest(unittest.TestCase):
    """Direct tests of _normalize_inverse_role_LHS in isolation."""

    def test_bare_inverse_sub_rewritten_to_o7_defining_axiom(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        ontology = Ontology(
            iri="http://ex", axioms=[RoleInclusion(InverseRole(r), s)]
        )

        _normalize_inverse_role_LHS(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(r).id}")
        self.assertIn(RoleInclusion(r, InverseRole(fresh)), ontology.axioms)
        self.assertIn(RoleInclusion(fresh, InverseRole(r)), ontology.axioms)
        self.assertIn(RoleInclusion(fresh, s), ontology.axioms)
        self.assertCountEqual(
            [classify_axiom(ax) for ax in ontology.axioms], [O7, O7, O6]
        )
        self.assertIn(fresh.id, ontology.roles)
        self.assertIn(f"not_{fresh.id}", ontology.roles)

    def test_chain_member_inverse_rewritten(self):
        r1, r2, r3, s = (
            AtomicRole("http://ex/R1"),
            AtomicRole("http://ex/R2"),
            AtomicRole("http://ex/R3"),
            AtomicRole("http://ex/S"),
        )
        ontology = Ontology(
            iri="http://ex",
            axioms=[RoleInclusion(RoleChain((r1, InverseRole(r2), r3)), s)],
        )

        _normalize_inverse_role_LHS(ontology)

        rewritten = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, RoleInclusion) and isinstance(ax.sub, RoleChain)
        ]
        self.assertEqual(len(rewritten), 1)
        for member in rewritten[0].sub.roles:
            self.assertIsInstance(member, AtomicRole)

    def test_axioms_without_inverse_lhs_are_untouched(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        plain = Ontology(iri="http://ex", axioms=[RoleInclusion(r, InverseRole(s))])
        before = list(plain.axioms)
        _normalize_inverse_role_LHS(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        ontology = Ontology(
            iri="http://ex", axioms=[RoleInclusion(InverseRole(r), s)]
        )
        _normalize_inverse_role_LHS(ontology)
        once = list(ontology.axioms)
        _normalize_inverse_role_LHS(ontology)
        self.assertEqual(once, ontology.axioms)


class NormalizeInverseDisjointRoleTest(unittest.TestCase):
    """Direct tests of _normalize_inverse_disjoint_role in isolation."""

    def test_inverse_sub_rewritten_to_o7_plus_o9(self):
        # R^- sqcap S sqsubseteq bot  ->  R subseteq R'^- (O7) + R' sqcap S sqsubseteq bot (O9)
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        axiom = RoleInclusion(InverseRole(r), NegatedRole(s))
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_inverse_disjoint_role(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(r).id}")
        self.assertIn(RoleInclusion(r, InverseRole(fresh)), ontology.axioms)
        self.assertIn(RoleInclusion(fresh, NegatedRole(s)), ontology.axioms)
        for ax in ontology.axioms:
            self.assertNotEqual(classify_axiom(ax), UNCLASSIFIED)
        self.assertIn(fresh.id, ontology.roles)
        self.assertIn(f"not_{fresh.id}", ontology.roles)

    def test_inverse_negated_role_rewritten_to_o7_plus_o9(self):
        # R sqcap S^- sqsubseteq bot  ->  S subseteq S'^- (O7) + R sqcap S' sqsubseteq bot (O9)
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        axiom = RoleInclusion(r, NegatedRole(InverseRole(s)))
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_inverse_disjoint_role(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(s).id}")
        self.assertIn(RoleInclusion(s, InverseRole(fresh)), ontology.axioms)
        self.assertIn(RoleInclusion(r, NegatedRole(fresh)), ontology.axioms)
        for ax in ontology.axioms:
            self.assertNotEqual(classify_axiom(ax), UNCLASSIFIED)

    def test_both_sides_inverse_rewritten(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        axiom = RoleInclusion(InverseRole(r), NegatedRole(InverseRole(s)))
        ontology = Ontology(iri="http://ex", axioms=[axiom])

        _normalize_inverse_disjoint_role(ontology)

        for ax in ontology.axioms:
            self.assertNotEqual(classify_axiom(ax), UNCLASSIFIED)
        o9_axioms = [ax for ax in ontology.axioms if classify_axiom(ax) == O9]
        self.assertEqual(len(o9_axioms), 1)

    def test_same_role_shared_with_inverse_role_lhs(self):
        # R^- sqcap S sqsubseteq bot  and  R^- sqsubseteq T  in the same
        # ontology must reuse the same fresh role for R^-.
        r, s, t = (
            AtomicRole("http://ex/R"),
            AtomicRole("http://ex/S"),
            AtomicRole("http://ex/T"),
        )
        ontology = Ontology(
            iri="http://ex",
            axioms=[
                RoleInclusion(InverseRole(r), NegatedRole(s)),
                RoleInclusion(InverseRole(r), t),
            ],
        )

        _normalize_inverse_role_LHS(ontology)
        _normalize_inverse_disjoint_role(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(r).id}")
        defining_axioms = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, RoleInclusion) and ax.sub == r
        ]
        self.assertEqual(len(defining_axioms), 1)  # R subseteq fresh^- deduped
        self.assertIn(RoleInclusion(fresh, NegatedRole(s)), ontology.axioms)
        self.assertIn(RoleInclusion(fresh, t), ontology.axioms)

    def test_atomic_disjoint_role_is_untouched(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        plain = Ontology(
            iri="http://ex", axioms=[RoleInclusion(r, NegatedRole(s))]
        )
        before = list(plain.axioms)
        _normalize_inverse_disjoint_role(plain)
        self.assertEqual(before, plain.axioms)

    def test_axioms_without_negated_role_sup_are_untouched(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        plain = Ontology(iri="http://ex", axioms=[RoleInclusion(InverseRole(r), s)])
        before = list(plain.axioms)
        _normalize_inverse_disjoint_role(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        r, s = AtomicRole("http://ex/R"), AtomicRole("http://ex/S")
        ontology = Ontology(
            iri="http://ex",
            axioms=[RoleInclusion(InverseRole(r), NegatedRole(InverseRole(s)))],
        )
        _normalize_inverse_disjoint_role(ontology)
        once = list(ontology.axioms)
        _normalize_inverse_disjoint_role(ontology)
        self.assertEqual(once, ontology.axioms)


class NormalizeInverseFunctionalRoleTest(unittest.TestCase):
    """Direct tests of _normalize_inverse_functional_role in isolation."""

    def test_inverse_functional_rewritten_to_o7_plus_o11(self):
        # invFunct(P)  ->  P subseteq P'^- (O7)  +  funct(P') (O11)
        p = AtomicRole("http://ex/P")
        axiom = InverseFunctionalRole(p)
        ontology = Ontology(iri="http://ex", axioms=[axiom])
        self.assertEqual(classify_axiom(axiom), UNCLASSIFIED)

        _normalize_inverse_functional_role(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(p).id}")
        self.assertIn(RoleInclusion(p, InverseRole(fresh)), ontology.axioms)
        self.assertIn(FunctionalRole(fresh), ontology.axioms)
        self.assertNotIn(axiom, ontology.axioms)
        for ax in ontology.axioms:
            self.assertNotEqual(classify_axiom(ax), UNCLASSIFIED)
        self.assertIn(fresh.id, ontology.roles)
        self.assertIn(f"not_{fresh.id}", ontology.roles)

    def test_shares_fresh_role_with_inverse_role_lhs(self):
        # invFunct(P)  and  P^- subseteq S  in the same ontology must reuse
        # the same fresh role for P^-.
        p, s = AtomicRole("http://ex/P"), AtomicRole("http://ex/S")
        ontology = Ontology(
            iri="http://ex",
            axioms=[InverseFunctionalRole(p), RoleInclusion(InverseRole(p), s)],
        )

        _normalize_inverse_role_LHS(ontology)
        _normalize_inverse_functional_role(ontology)

        fresh = AtomicRole(f"defr_{InverseRole(p).id}")
        defining_axioms = [
            ax
            for ax in ontology.axioms
            if isinstance(ax, RoleInclusion) and ax.sub == p
        ]
        self.assertEqual(len(defining_axioms), 1)  # P subseteq fresh^- deduped
        self.assertIn(FunctionalRole(fresh), ontology.axioms)
        self.assertIn(RoleInclusion(fresh, s), ontology.axioms)

    def test_functional_role_is_untouched(self):
        p = AtomicRole("http://ex/P")
        plain = Ontology(iri="http://ex", axioms=[FunctionalRole(p)])
        before = list(plain.axioms)
        _normalize_inverse_functional_role(plain)
        self.assertEqual(before, plain.axioms)

    def test_idempotent(self):
        p = AtomicRole("http://ex/P")
        ontology = Ontology(iri="http://ex", axioms=[InverseFunctionalRole(p)])
        _normalize_inverse_functional_role(ontology)
        once = list(ontology.axioms)
        _normalize_inverse_functional_role(ontology)
        self.assertEqual(once, ontology.axioms)


class NormalizeRoleAxiomIntegrationTest(unittest.TestCase):
    """R1 ∘ R2⁻ ∘ R3 ⊑ S needs both new passes together: inverse-role
    elimination, then chain-length binarization."""

    def test_normalize_ontology_fully_classifies(self):
        r1, r2, r3, s = (
            AtomicRole("http://ex/R1"),
            AtomicRole("http://ex/R2"),
            AtomicRole("http://ex/R3"),
            AtomicRole("http://ex/S"),
        )
        chain = RoleChain((r1, InverseRole(r2), r3))
        ontology = Ontology(iri="http://ex", axioms=[RoleInclusion(chain, s)])

        self.assertEqual(classify_axiom(ontology.axioms[0]), UNCLASSIFIED)

        normalize_ontology(ontology)
        sizes = {label: len(axs) for label, axs in ontology.axiom_types.items()}
        # R2 ≡ A_x⁻  (O7 x2),  R1∘A_x ⊑ A_y  (O8),  A_y∘R3 ⊑ S  (O8)
        self.assertEqual(sizes[O7], 2)
        self.assertEqual(sizes[O8], 2)
        self.assertEqual(sizes[UNCLASSIFIED], 0)


if __name__ == "__main__":
    unittest.main()
