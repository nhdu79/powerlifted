;; Must be SOLVABLE (use with domain-pos.pddl). Optimal plan length 21:
;; 10 test actions + 10 checks + (unlk n1) before (a7 n1).
(define (problem negtest-pos) (:domain negtest-pos)
  (:objects n1 n2 - node s1 s2 - special)
  (:init
    (edge n1 n2) (edge n2 n3) (edge n3 n1) (edge n1 n1) (edge n2 n1)
    (forbid n2 n3)
    (m n1) (m s1)
    (r n2 n1) (r n3 n3)
    (lk n1)
    (want1 s2) (want2 n1) (want3 n2 n3) (want4 n1) (want5 n1 n2) (want5b n1)
    (want6 n2 n1) (want7 n1) (want10 n1 n2) (want12 n1 n2 n3)
    (st1))
  (:goal (st11)))
