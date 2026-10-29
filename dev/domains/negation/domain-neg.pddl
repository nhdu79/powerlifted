;; Negated preconditions, UNSOLVABLE check. No persistent d-facts, so
;; the reachable state space is tiny (only lk, lk2, sent change) and a planner
;; can exhaust it. Each aK is restricted by its badK atom (tuples that must
;; NOT satisfy the precondition) and has effect (violation).
(define (domain negtest-neg)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:constants n1 - node)
  (:predicates
    (edge ?a ?b - node) (forbid ?a ?b - node) (never ?a - node)   ; static
    (m ?x - node) (r ?a ?b - node) (lk ?x - node) (lk2 ?x - node) (sent ?x - node)
    (bad1 ?x - node) (bad2b ?x - node) (bad3 ?a ?b - node) (bad4 ?x - node)
    (bad5 ?a ?b - node) (bad6 ?a ?b - node) (bad8 ?x - node) (bad10 ?a ?b - node)
    (bad12 ?a ?b ?c - node)
    (violation))

  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x)))
  (:action unlk :parameters (?x - node) :precondition (lk ?x) :effect (not (lk ?x)))
  (:action lock2 :parameters (?x - node) :precondition (and) :effect (and (lk2 ?x) (sent ?x)))

  (:action a1 :parameters (?x - special)
    :precondition (and (bad1 ?x) (not (m ?x))) :effect (violation))
  (:action a2b :parameters (?x - node)
    :precondition (and (bad2b ?x) (not (m n1))) :effect (violation))
  (:action a3 :parameters (?x ?y - node)
    :precondition (and (bad3 ?x ?y) (edge ?x ?y) (not (r ?y ?x))) :effect (violation))
  (:action a4 :parameters (?x - node)
    :precondition (and (bad4 ?x) (not (r ?x ?x))) :effect (violation))
  (:action a5 :parameters (?x ?y - node)
    :precondition (and (bad5 ?x ?y) (edge ?x ?y) (not (forbid ?x ?y))) :effect (violation))
  (:action a6 :parameters (?x ?y - node)
    :precondition (and (bad6 ?x ?y) (r ?x ?y) (not (r ?y ?x))) :effect (violation))
  (:action a8 :parameters (?x - node)
    :precondition (and (bad8 ?x) (sent ?x) (not (lk2 ?x))) :effect (violation))
  (:action a10 :parameters (?x ?y - node)
    :precondition (and (bad10 ?x ?y) (edge ?x ?y) (not (= ?x ?y)) (not (r ?x ?y)))
    :effect (violation))
  (:action a12 :parameters (?x ?y ?z - node)
    :precondition (and (bad12 ?x ?y ?z) (edge ?x ?y) (edge ?y ?z) (not (r ?z ?x)))
    :effect (violation)))
