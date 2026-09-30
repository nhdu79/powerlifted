# Duy

- [ ] Understand what's written for c-chase

## Caveats

- [ ] UPPERBOUND: Requires normalization of `RULES` in page 6.
- [ ] translate the ontology into disjunctive existential rules (also using the same query predicates that the Clipper output uses) and put it into output.lifted
- [ ] Translator might create negated atoms! Mapping between shifting and translator

* O14 is rewritten as A(X) -> \exists Y_1,...Y_n r(X,Y_1) ∧ B(Y_1), ..., r(X,Y_n) ∧ B(Y_n), neq_(Y_i,Y_j) (pairwise), plus neq_(Y,Z) ∧ Y=Z -> ⊥ in both orders: no inequality needed in rules

### Later
- [x] Konnect Konclude
- [ ] Real conjunctive query answering instead of stub for Konclude (waiting for Andreas Steigmiller)
