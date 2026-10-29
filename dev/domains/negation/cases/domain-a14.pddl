;; One-case test for a14: (d14 ?x ?y) must be reachable for all five (edge ?x ?y).
(define (domain case-a14)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:predicates
    (edge ?a ?b - node) (forbid ?a ?b - node) (never ?a - node)   ; static
    (m ?x - node) (r ?a ?b - node) (lk ?x - node) (tri ?a ?b ?c - node)
    (d14 ?a ?b - node))

  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x) (tri ?x ?y ?y)))
  ;; negated static atom that removes no rows
  (:action a14 :parameters (?x ?y - node)
    :precondition (and (edge ?x ?y) (not (forbid ?y ?x)))
    :effect (and (d14 ?x ?y))))
