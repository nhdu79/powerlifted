; Two teams: red, captained by alice, and blue, with members bob and carol.
; Red has no member yet and must recruit bob and carol; that they are players
; (and red and blue teams) is only entailed by the ontology's domain and range
; of hasCaptain/hasMember. Expected optimal plan, 2 steps (in either order):
;   (recruit red bob) (recruit red carol)
(define (problem team_problem)
  (:domain team)
  (:objects red blue alice bob carol)
  (:init
    (hasCaptain red alice)
    (hasMember blue bob)
    (hasMember blue carol)
  )
  (:goal
    (and
      (mko (hasMember red bob))
      (mko (hasMember red carol))
    )
  )
)
