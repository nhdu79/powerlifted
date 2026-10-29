;; One-case test for a15: goal (d15 n1 n3) must be reachable.
(define (domain case-a15)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:constants n2 - node)
  (:predicates
    (edge ?a ?b - node) (forbid ?a ?b - node) (never ?a - node)   ; static
    (m ?x - node) (r ?a ?b - node) (lk ?x - node) (tri ?a ?b ?c - node)
    (d15 ?a ?b - node))

  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x) (tri ?x ?y ?y)))
  ;; joined positive atom with a constant in a non-final position
  (:action a15 :parameters (?x ?y - node)
    :precondition (and (m ?x) (tri ?x n2 ?y))
    :effect (and (d15 ?x ?y))))
