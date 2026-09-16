# Current Pipeline:

1. Load ontology $K$, normalize $K$ and output `Rules` (for Horn-SHIQ: Clipper; the rest stays the same)
2. Normalize `Rules`, apply shifting to `Rules` to get `shift(Rules)` (handling disjunct).
3. Construct subset of `ELHO` rules by copying `Rules` and eliminating rules of form (O4), (O5),
(O8), (O9), and (O11) (Page 7) to get `ExistsRules` (handling existential).
4. To compute $L^q$:
    - `ans_q(shift(Rules)) U ans_q(ExistsRules)`


## Caveats

- [ ] UPPERBOUND: Requires normalization of `RULES` in page 6.
- [ ] Duy: adapt translate.py to parse and normalize the ontology, apply shifting to the disjunctive rules (Pagoda paper Sec. 4.1), call Clipper and put its output into output.lifted
- [ ] Duy: translate the ontology into disjunctive existential rules (also using the same query predicates that the Clipper output uses) and put it into output.lifted


* New class for disjunctive rule! `DisjunctiveExistentialRule`? => Datatype for rules (1)
* Mimic `DisjunctiveExistentialRule` attributes!
* LOWERBOUND
- [ ] Normalization of `Ontology` for Clipper(?)
    * No existential concept on LHS
    * Assumed normalization
- [ ] Define shifting (sec 4.1) for "normalized" ONTOLOGY.
- Translator might create negated atoms! Mapping between shifting and translator


* O14 can be directly rewritten as A(X) -> \exists Y_1,...Y_n r(X,Y_1), ..., r(X,Y_n), Y_1 != Y_2, ... (pairwise)

### Later
- [x] Konnect Konclude
- [ ] Real conjunctive query answering instead of stub for Konclude (waiting for Andreas Steigmiller)
