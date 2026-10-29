;; One-case test for a13: (d13 ?x ?y) must be reachable for the three (edge ?x ?y) with
;; (not (m ?x)).
(define (domain case-a13)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:predicates
    (edge ?a ?b - node) (forbid ?a ?b - node) (never ?a - node)   ; static
    (m ?x - node) (r ?a ?b - node) (lk ?x - node) (tri ?a ?b ?c - node)
    (d13 ?a ?b - node))

  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x) (tri ?x ?y ?y)))
  ;; negated atom that removes several rows (2 of 5) at the same join step
  (:action a13 :parameters (?x ?y - node)
    :precondition (and (edge ?x ?y) (not (m ?x)))
    :effect (and (d13 ?x ?y))))
