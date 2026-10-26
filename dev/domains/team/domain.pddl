; Teams recruiting players, with the team ontology dev/ontologies/team.owl.
;
; Nothing in the problem says which objects are teams or players: that
; follows from the ontology only (hasCaptain/hasMember have domain Team and
; range Player). A team recruits a player, or a player transfers between
; teams; a team that has the star player celebrates. (Recruiting only players
; not known to be members already would need (not (mko ...)), which the
; search doesn't support yet.)
;
; The mkos, for the translator's mko queries (see
; src/translator/queries/sparql.py):
; - (and (Team ?t) (Player ?p)) is shared by Recruit and Transfer (one
;   QUERY<i>: the same formula, same variable names), and is disconnected;
; - (exists (?c) (and (hasCaptain ?t ?c) (Captain ?c))), a team whose captain
;   is known to be a captain, is shared by Recruit and Celebrate. Its ?c is
;   existential: by the ontology every team has one, possibly anonymous;
; - (hasMember ?t star) and (hasMember ?from ?p) are atomic;
; - star is a constant of the domain, read by Celebrate's atomic mko and by
;   the goal's (exists (?t) ...), which has no free variables.
(define (domain team)

  (:constants star)

  (:predicates
    (Team ?x)
    (Player ?x)
    (Captain ?x)
    (Substitute ?x)
    (hasCaptain ?x ?y)
    (hasMember ?x ?y)
    (celebrated ?x)
  )

  (:action Recruit
    :parameters (?t ?p)
    :precondition (and
      (mko (and (Team ?t) (Player ?p)))
      (mko (exists (?c) (and (hasCaptain ?t ?c) (Captain ?c))))
    )
    :effect (and
      (hasMember ?t ?p)
    )
  )

  (:action Transfer
    :parameters (?from ?t ?p)
    :precondition (and
      (mko (hasMember ?from ?p))
      (mko (and (Team ?t) (Player ?p)))
    )
    :effect (and
      (not (hasMember ?from ?p))
      (hasMember ?t ?p)
    )
  )

  (:action Celebrate
    :parameters (?t)
    :precondition (and
      (mko (hasMember ?t star))
      (mko (exists (?c) (and (hasCaptain ?t ?c) (Captain ?c))))
    )
    :effect (and
      (celebrated ?t)
    )
  )
)
