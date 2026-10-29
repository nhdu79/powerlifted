# Negated Preconditions

Small tasks with negated atoms in action preconditions. Only the `join`
successor generator (`GenericNegationJoinSuccessorGenerator`, based on the
`Query` class in `src/search/database/query.{h,cc}`) supports them. The other
generators abort with "Actions with negated preconditions not supported yet".

Every task has a small reachable state space, so a bug makes the search
terminate early (wrong cost, or no plan) instead of running forever.

## Files

| Files | Expected result | Checks |
|---|---|---|
| `domain-pos.pddl`, `pos.pddl` | solvable, optimal cost 21 (87 reachable states) | every test action produces a specific tuple that satisfies its precondition |
| `domain-neg.pddl`, `neg.pddl` | unsolvable (64 reachable states) | no test action produces a tuple that violates its negated precondition |
| `cases/domain-aK.pddl`, `cases/aK.pddl` | solvable, cost 1 (`a7`: 2) | one test action each, so a failure points to a single case |

`run-tests.py` runs `pos` with `bfs/blind/join` and `alt-bfws1/ff/join`, and
`neg` and the cases with `bfs/blind/join`. Each problem file is found by the
driver through the `domain-<instance>` naming rule.

## Test Actions

| Action | Precondition pattern | Tuple required in `pos` |
|---|---|---|
| `a1` | no positive atom except the type atom, negated unary atom, parameter of a subtype | `s2` |
| `a2` | negated atom over constants only (`(not (m n3))`) | `n1` |
| `a3` | negated binary atom with swapped arguments (`(edge ?x ?y)`, `(not (r ?y ?x))`) | `n2 n3` |
| `a4` | repeated variable in a negated atom (`(not (r ?x ?x))`) | `n1` |
| `a5` | negated static predicate | `n1 n2` |
| `a5b` | negated static predicate with an empty extension | `n1` |
| `a6` | the same predicate positive and negated (`(r ?x ?y)`, `(not (r ?y ?x))`) | `n2 n1` |
| `a7` | negated atom that becomes true through a delete effect (`unlk n1` first) | `n1` |
| `a10` | negated atom together with an inequality | `n1 n2` |
| `a12` | negated atom that can only be checked after the last join | `n1 n2 n3` |

Only in `neg`:

| Action | Precondition pattern |
|---|---|
| `a2b` | negated ground atom that is always true, so the action is never applicable |
| `a8` | negated atom that is always added together with a positive atom of the same precondition |

The numbering comes from an earlier combined domain. There is no `a9` or `a11`.

### How `pos` works

The test actions run in a fixed sequence of stages, guarded by nullary atoms
(`st1`, ..., `st11`), so the guards add no tables to the join. In stage K, the
action `aK` records the tuple it was applied with (`dK`). The check action
`chkK` advances to the next stage only if that tuple is the one listed in
`wantK`. Any other instantiation is a dead end. If the generator misses a
required tuple, the goal `(st11)` becomes unreachable. If it wrongly allows
`(a7 n1)` before `(unlk n1)`, the plan is shorter than 21.

### How `neg` works

Each test action additionally requires a `badK` atom, which lists tuples that
satisfy the positive part of the precondition but violate the negated part.
Every test action has the effect `(violation)`, which is the goal. If the
generator wrongly accepts such a tuple, the task becomes solvable.

## Still to Add

1. A filter that removes several rows at the same join step (e.g. a negated
   atom that holds for 2 of 3 candidates).
2. A filter that removes no rows.
3. A positive (joined) atom with a constant in a non-final position, e.g.
   `(r ?x n2 ?y)`.
4. A repeated variable in a joined positive atom, with no other positive atom
   on that variable except its type atom.
5. A positive fluent atom whose variables are already covered, so it is used as
   a filter.
