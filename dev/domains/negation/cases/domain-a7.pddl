;; One-case test for a7: goal (d7 n1) must be reachable.
(define (domain case-a7)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:predicates
    (edge ?a ?b - node) (forbid ?a ?b - node) (never ?a - node)   ; static
    (m ?x - node) (r ?a ?b - node) (lk ?x - node)
    (d1 ?x - node) (d2 ?x - node) (d3 ?a ?b - node) (d4 ?x - node) (d5 ?a ?b - node)
    (d5b ?x - node) (d6 ?a ?b - node) (d7 ?x - node) (d10 ?a ?b - node)
    (d12 ?a ?b ?c - node)
    (want1 ?x - node) (want2 ?x - node) (want3 ?a ?b - node) (want4 ?x - node)
    (want5 ?a ?b - node) (want5b ?x - node) (want6 ?a ?b - node) (want7 ?x - node)
    (want10 ?a ?b - node) (want12 ?a ?b ?c - node)
    (st1) (st2) (st3) (st4) (st5) (st6) (st7) (st8) (st9) (st10) (st11)
    (c1) (c2) (c3) (c4) (c5) (c6) (c7) (c8) (c9) (c10))


  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x)))
  (:action unlk :parameters (?x - node) :precondition (lk ?x) :effect (not (lk ?x)))
  (:action a7 :parameters (?x - node) :precondition (and (not (lk ?x)))
    :effect (and (d7 ?x))))
