; Drones moving on a grid of cells, with the drone-safety ontology
; dev/ontologies/drones.owl (after pddl-horndl's drones benchmark, without its
; conditional effects, which Powerlifted doesn't support).
;
; Objects are grid cells: (Drone ?c) means that a drone is at cell ?c.
; A drone moves to a very close cell that is not known to hold an object.
; Since veryClose is symmetric in the ontology (and the problem lists each
; pair only once), moving "back" along a listed pair is only possible
; through the mko.
(define (domain drone)

  (:predicates
    (environment ?x ?y)
    (Rain ?x)
    (Drone ?x)
    (WetDrone ?x)
    (LowVisibility ?x)
    (near ?x ?y)
    (veryClose ?x ?y)
    (Human ?x)
    (MovingObject ?x)
    (Objectx ?x)
    (RiskOfPhysicalDamage ?x)
    (Tree ?x)
  )

  (:action Move
    :parameters (?x ?y)
    :precondition (and
      (mko (and (Drone ?x) (veryClose ?x ?y)))
      (not (mko (= ?x ?y)))
      (not (mko (Objectx ?y)))
    )
    :effect (and
      (not (Drone ?x))
      (Drone ?y)
    )
  )
)
