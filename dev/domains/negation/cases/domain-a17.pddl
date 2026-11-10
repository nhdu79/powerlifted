;; One-case test for a17: goal (d17 n1 n2) must be reachable.
(define (domain case-a17)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:predicates
    (edge ?a ?b - node) (forbid ?a ?b - node) (never ?a - node)   ; static
    (m ?x - node) (r ?a ?b - node) (lk ?x - node) (tri ?a ?b ?c - node)
    (d17 ?a ?b - node))

  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x) (tri ?x ?y ?y)))
  ;; positive fluent atom whose variables are already covered (used as a filter)
  (:action a17 :parameters (?x ?y - node)
    :precondition (and (edge ?x ?y) (r ?y ?x))
    :effect (and (d17 ?x ?y))))
