;; One-case test for a16: goal (d16 n3) must be reachable.
(define (domain case-a16)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:predicates
    (edge ?a ?b - node) (forbid ?a ?b - node) (never ?a - node)   ; static
    (m ?x - node) (r ?a ?b - node) (lk ?x - node) (tri ?a ?b ?c - node)
    (d16 ?x - node))

  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x) (tri ?x ?y ?y)))
  ;; repeated variable in a joined positive atom, no other positive atom on it
  ;; except its type atom
  (:action a16 :parameters (?x - node)
    :precondition (and (r ?x ?x))
    :effect (and (d16 ?x))))
