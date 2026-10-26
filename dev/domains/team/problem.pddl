; Two teams: red, captained by alice, and blue, with members bob, carol and
; the domain's star. Red has no member yet and must recruit bob and carol, and
; get the star (recruit or transfer) to celebrate; that they are players (and
; red and blue teams) is only entailed by the ontology's domain and range of
; hasCaptain/hasMember. Expected optimal plan, 4 steps (the first three in any
; order, the star by recruit or transfer):
;   (recruit red bob) (recruit red carol) (recruit red star) (celebrate red)
(define (problem team_problem)
  (:domain team)
  (:objects red blue alice bob carol)
  (:init
    (hasCaptain red alice)
    (hasMember blue bob)
    (hasMember blue carol)
    (hasMember blue star)
  )
  (:goal
    (and
      (mko (hasMember red bob))
      (mko (hasMember red carol))
      (mko (exists (?t) (and (Team ?t) (hasMember ?t star))))
      (celebrated red)
    )
  )
)
