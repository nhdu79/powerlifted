;; Must be UNSOLVABLE (use with domain-neg.pddl): (violation) is reachable only if
;; a negated precondition wrongly admits a tuple listed in a badK predicate.
(define (problem negtest-neg) (:domain negtest-neg)
  (:objects n2 n3 - node s1 s2 - special)
  (:init
    (edge n1 n2) (edge n2 n3) (edge n3 n1) (edge n1 n1) (edge n2 n1)
    (forbid n2 n3)
    (m n1) (m s1)
    (r n2 n1) (r n3 n3)
    (lk n1)
    (bad1 s1) (bad2b n1) (bad3 n1 n2) (bad4 n3) (bad5 n2 n3) (bad6 n3 n3)
    (bad8 n1) (bad10 n1 n1) (bad10 n2 n1) (bad12 n1 n1 n2))
  (:goal (violation)))
