# Negated Preconditions

Small tasks with negated atoms in action preconditions. Only the `join_neg`
successor generator (`GenericNegationJoinSuccessorGenerator`, based on the
`Query` class in `src/search/database/query.{h,cc}`) supports them. The other
generators abort with "Actions with negated preconditions not supported yet".

Every task has a small reachable state space, so a bug makes the search
terminate early (wrong cost, or no plan) instead of running forever.

## Files

| Files | Expected result | Checks |
|---|---|---|
| `domain-pos.pddl`, `pos.pddl` | solvable, optimal cost 21 (87 reachable states) | every test action produces a specific tuple that satisfies its precondition |
| `domain-neg.pddl`, `neg.pddl` | unsolvable (64 reachable states) | no test action produces a tuple that violates its precondition |
| `cases/domain-aK.pddl`, `cases/aK.pddl` | solvable, cost 1 (`a7`: 2, `a13`: 3, `a14`: 5) | one test action each, so a failure points to a single case |

`run-tests.py` runs `pos` with `bfs/blind/join_neg` and `alt-bfws1/ff/join_neg`, and
`neg` and the cases with `bfs/blind/join_neg`. Each problem file is found by the
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

Only in `cases/` and `neg` (data: `edge` = {12, 23, 31, 11, 21}, `forbid` = {23},
`m` = {n1, s1}, `r` = {21, 33}, `tri` = {123, 132, 221, 323}):

| Action | Precondition pattern | Required in `cases/` | Excluded in `neg` |
|---|---|---|---|
| `a13` | negated filter that removes several rows (2 of 5) at the same join step (`(edge ?x ?y)`, `(not (m ?x))`) | all 3 remaining tuples | `n1 n2`, `n1 n1` |
| `a14` | negated static filter that removes no rows (`(edge ?x ?y)`, `(not (forbid ?y ?x))`) | all 5 edges | (not in `neg`) |
| `a15` | joined fluent atom with a constant in a non-final position (`(m ?x)`, `(tri ?x n2 ?y)`) | `n1 n3` | `n1 n2` |
| `a16` | repeated variable in the only positive atom except the type atom (`(r ?x ?x)`) | `n3` | `n2` |
| `a17` | positive fluent atom whose variables are already covered, used as a filter (`(edge ?x ?y)`, `(r ?y ?x)`) | `n1 n2` | `n2 n1` |

The numbering of `a1` to `a12` comes from an earlier combined domain. There is
no `a9` or `a11`.

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
violate the rest of the precondition. In `a1` to `a12`, these tuples satisfy the
positive part but violate a negated atom.
Every test action has the effect `(violation)`, which is the goal. If the
generator wrongly accepts such a tuple, the task becomes solvable.

The translator sorts precondition atoms by predicate name, and this order
determines the join order. In `a1` to `a12`, `badK` therefore comes first and
is the only join atom, and all other atoms act as filters. For `a13` to `a17`,
the predicates are named `zbadK`, so they come last and act only as a final
filter. Their join structure is then the same as in `cases/`.
