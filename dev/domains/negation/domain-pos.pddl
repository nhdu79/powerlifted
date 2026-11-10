;; Negated preconditions, SOLVABLE check, with a small state space.
;; The test actions run in a fixed sequence of stages (nullary atoms, so they
;; add no tables to the join). Stage k: aK must be applied with the tuple listed
;; in wantK (checked by chkK); any other instantiation leads to a dead end.
;; Reachable state space: 87 states.
(define (domain negtest-pos)
  (:requirements :typing :negative-preconditions :equality)
  (:types node - object special - node)
  (:constants n3 - node)
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

  ;; only keeps m, r fluent; never applicable ((never ?x) is empty)
  (:action churn :parameters (?x ?y - node) :precondition (never ?x)
    :effect (and (r ?x ?y) (m ?x)))
  (:action unlk :parameters (?x - node) :precondition (lk ?x) :effect (not (lk ?x)))

  ;; 1: single positive table (type only) + negated unary, subtype parameter
  (:action a1 :parameters (?x - special) :precondition (and (st1) (not (m ?x)))
    :effect (and (not (st1)) (c1) (d1 ?x)))
  ;; 2: negated atom over constants only (n3 not in m)
  (:action a2 :parameters (?x - node) :precondition (and (st2) (not (m n3)))
    :effect (and (not (st2)) (c2) (d2 ?x)))
  ;; 3: negated binary, swapped argument order
  (:action a3 :parameters (?x ?y - node)
    :precondition (and (st3) (edge ?x ?y) (not (r ?y ?x)))
    :effect (and (not (st3)) (c3) (d3 ?x ?y)))
  ;; 4: repeated variable in negated atom, single positive table
  (:action a4 :parameters (?x - node) :precondition (and (st4) (not (r ?x ?x)))
    :effect (and (not (st4)) (c4) (d4 ?x)))
  ;; 5: negated static predicate
  (:action a5 :parameters (?x ?y - node)
    :precondition (and (st5) (edge ?x ?y) (not (forbid ?x ?y)))
    :effect (and (not (st5)) (c5) (d5 ?x ?y)))
  ;; 5b: negated static predicate with empty extension
  (:action a5b :parameters (?x - node) :precondition (and (st6) (not (never ?x)))
    :effect (and (not (st6)) (c6) (d5b ?x)))
  ;; 6: same predicate positive and negated
  (:action a6 :parameters (?x ?y - node)
    :precondition (and (st7) (r ?x ?y) (not (r ?y ?x)))
    :effect (and (not (st7)) (c7) (d6 ?x ?y)))
  ;; 7: negated atom becomes true after a delete effect (needs unlk n1 first)
  (:action a7 :parameters (?x - node) :precondition (and (st8) (not (lk ?x)))
    :effect (and (not (st8)) (c8) (d7 ?x)))
  ;; 10: with inequality
  (:action a10 :parameters (?x ?y - node)
    :precondition (and (st9) (edge ?x ?y) (not (= ?x ?y)) (not (r ?x ?y)))
    :effect (and (not (st9)) (c9) (d10 ?x ?y)))
  ;; 12: negated atom only ready after the last join
  (:action a12 :parameters (?x ?y ?z - node)
    :precondition (and (st10) (edge ?x ?y) (edge ?y ?z) (not (r ?z ?x)))
    :effect (and (not (st10)) (c10) (d12 ?x ?y ?z)))

  ;; checks: advance to the next stage only if the expected tuple was used
  (:action chk1 :parameters (?x - node) :precondition (and (c1) (d1 ?x) (want1 ?x))
    :effect (and (not (c1)) (not (d1 ?x)) (st2)))
  (:action chk2 :parameters (?x - node) :precondition (and (c2) (d2 ?x) (want2 ?x))
    :effect (and (not (c2)) (not (d2 ?x)) (st3)))
  (:action chk3 :parameters (?x ?y - node) :precondition (and (c3) (d3 ?x ?y) (want3 ?x ?y))
    :effect (and (not (c3)) (not (d3 ?x ?y)) (st4)))
  (:action chk4 :parameters (?x - node) :precondition (and (c4) (d4 ?x) (want4 ?x))
    :effect (and (not (c4)) (not (d4 ?x)) (st5)))
  (:action chk5 :parameters (?x ?y - node) :precondition (and (c5) (d5 ?x ?y) (want5 ?x ?y))
    :effect (and (not (c5)) (not (d5 ?x ?y)) (st6)))
  (:action chk6 :parameters (?x - node) :precondition (and (c6) (d5b ?x) (want5b ?x))
    :effect (and (not (c6)) (not (d5b ?x)) (st7)))
  (:action chk7 :parameters (?x ?y - node) :precondition (and (c7) (d6 ?x ?y) (want6 ?x ?y))
    :effect (and (not (c7)) (not (d6 ?x ?y)) (st8)))
  (:action chk8 :parameters (?x - node) :precondition (and (c8) (d7 ?x) (want7 ?x))
    :effect (and (not (c8)) (not (d7 ?x)) (st9)))
  (:action chk9 :parameters (?x ?y - node) :precondition (and (c9) (d10 ?x ?y) (want10 ?x ?y))
    :effect (and (not (c9)) (not (d10 ?x ?y)) (st10)))
  (:action chk10 :parameters (?x ?y ?z - node)
    :precondition (and (c10) (d12 ?x ?y ?z) (want12 ?x ?y ?z))
    :effect (and (not (c10)) (not (d12 ?x ?y ?z)) (st11))))
