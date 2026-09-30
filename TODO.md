# Duy

- [ ] Rewrite rule O10 and O14 into having 1 predicate in the head with all variables (normal form)
- [ ] Atom flags in conditions/preconditions of actions to distinguish between MKO and non-MKO atoms
    - This is to be parsed back in the search component
    - No need to `DATALOG_` anymore
- [ ] EQ1--EQ4 in translator (only if there is number restriction or nomial)
    - Upperbound = `(EQ1--EQ4) U (ontology_rules)` U `una_rules`
    - Construct `una_rules` for each pair of constants AND objects (a,b):
        - a = b -> ⊥

- [ ] Understand what's written for c-chase

## Caveats

- [ ] UPPERBOUND: Requires normalization of `RULES` in page 6.
- [ ] translate the ontology into disjunctive existential rules (also using the same query predicates that the Clipper output uses) and put it into output.lifted
- [ ] Translator might create negated atoms! Mapping between shifting and translator

* O14 is rewritten as A(X) -> \exists Y_1,...Y_n r(X,Y_1) ∧ B(Y_1), ..., r(X,Y_n) ∧ B(Y_n), neq_(Y_i,Y_j) (pairwise), plus neq_(Y,Z) ∧ Y=Z -> ⊥ in both orders: no inequality needed in rules

### Later
- [x] Konnect Konclude
- [ ] Real conjunctive query answering instead of stub for Konclude (waiting for Andreas Steigmiller)
