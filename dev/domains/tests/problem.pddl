; 3x3 grid (veryClose: orthogonal neighbours, near: diagonal ones; each pair
; listed once, the ontology makes both symmetric and veryClose ⊑ near):
;
;   aa ab ac        drones at aa and ab, a tree at bb, a human at cc,
;   ba bb bc        low visibility around ca
;   ca cb cc
;
; Initially both drones are at risk and near each other (each is very close
; to the other drone, a moving object). The drone at aa must reach cb, where
; it is at risk again (very close to the human), but no longer near the
; other drone, which stays at ab (at risk, as it is very close to the tree).
;
; The pairs on the drone's way are listed "backwards" ((veryClose ba aa) &c.),
; so each move needs the ontology's symmetry of veryClose. Expected optimal
; plan, 3 steps:
;   (move aa ba) (move ba ca) (move ca cb)
(define (problem drone_problem)
  (:domain drone)
  (:objects aa ab ac ba bb bc ca cb cc env)
  (:init
    (Drone aa)
    (Drone ab)
    (Tree bb)
    (Human cc)
    (LowVisibility env)
    (environment ca env)
    (veryClose aa ab)
    (veryClose ab ac)
    (veryClose ba bb)
    (veryClose bb bc)
    (veryClose cb ca)
    (veryClose cb cc)
    (veryClose ba aa)
    (veryClose ca ba)
    (veryClose ab bb)
    (veryClose bb cb)
    (veryClose ac bc)
    (veryClose bc cc)
    (near aa bb)
    (near ab ba)
    (near ab bc)
    (near ac bb)
    (near ba cb)
    (near bb ca)
    (near bb cc)
    (near bc cb)
  )
  (:goal
    (and
      (mko (Drone cb))
      (not (mko (exists (?x ?y)
        (and
          (RiskOfPhysicalDamage ?x)
          (RiskOfPhysicalDamage ?y)
          (near ?x ?y)
        ))))
    )
  )
)
