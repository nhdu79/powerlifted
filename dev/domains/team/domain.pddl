; Teams recruiting players, with the team ontology dev/ontologies/team.owl.
;
; Nothing in the problem says which objects are teams or players: that
; follows from the ontology only (hasCaptain/hasMember have domain Team and
; range Player). A team recruits a player. (Recruiting only players not
; known to be members already would need (not (mko ...)), which the search
; doesn't support yet.)
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
    )
    :effect (and
      (hasMember ?t ?p)
    )
  )
)
