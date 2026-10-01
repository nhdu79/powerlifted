; Teams recruiting players, with the team ontology dev/ontologies/team.owl.
;
; Nothing in the problem says which objects are teams or players: that
; follows from the ontology only (hasCaptain/hasMember have domain Team and
; range Player). A team recruits a player that is not known to be one of
; its members already.
(define (domain team)

  (:predicates
    (Team ?x)
    (Player ?x)
    (Captain ?x)
    (Substitute ?x)
    (hasCaptain ?x ?y)
    (hasMember ?x ?y)
  )

  (:action Recruit
    :parameters (?t ?p)
    :precondition (and
      (mko (and (Team ?t) (Player ?p)))
      (not (mko (hasMember ?t ?p)))
    )
    :effect (and
      (hasMember ?t ?p)
    )
  )
)
