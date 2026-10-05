# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Powerlifted is a domain-independent classical planner for **lifted planning**: it
solves PDDL tasks by reasoning over relations, action schemas, and objects
directly, without grounding the full state space. It combines lifted successor
generation, delete-relaxation heuristics, and width-based search.

The codebase is split into two components that run as separate processes per
task:
- **Translator** (`src/translator/`, pure Python): parses PDDL, normalizes it,
  and produces an intermediate representation file (default `output.lifted`).
- **Search** (`src/search/`, C++17): reads that intermediate file and runs the
  actual lifted search.

The **driver** (`driver/`, invoked via `powerlifted.py`) orchestrates both:
it builds (optionally), runs the translator as a subprocess, then runs the
search binary, and handles portfolios/iterations and plan validation.

Currently on branch `wiring_konclude_to_powerlfited` / `ontology`: integrating
a Konclude-based OWL/description-logic reasoner into the planner via an
embedded shared library. See `EMBEDDED_LINKING_POWERLIFTED.md` for the
step-by-step linking guide (this is developer documentation for the current
in-progress work, not general project docs) and `src/search/konclude_reasoner.h`
for the RAII wrapper around the embedded C API. Konclude is optional and off
by default: `python build.py --konclude` (CMake `USE_KONCLUDE`, defining
`POWERLIFTED_USE_KONCLUDE`) links it, and the search only uses it with
`--use-konclude` (see `TODO.md`). `src/search/CMakeLists.txt` then
hardcodes `KONCLUDE_REPO_ROOT` to a sibling checkout path (`../Konclude`) —
override with `-DKONCLUDE_REPO_ROOT=...` if building on a machine with a
different layout. `src/translator/ontology.py` is the Python
entry point for ontology-related processing during translation.

## Build

```bash
python build.py            # release build -> builds/release/search/search
python build.py -d         # debug build   -> builds/debug/search/search
python build.py --cxx-compiler <path>   # use a specific compiler
python build.py --konclude # also link the embedded Konclude reasoner (off by default)
```

`build.py` creates `builds/<debug|release>/search`, copies `src/translator`
into `builds/<debug|release>/translator`, then runs CMake + `make -j5` in the
search build dir. ccache is auto-detected and used if installed. You can also
pass `--build` to `powerlifted.py` to build before running.

Two CMake targets are produced: `search` (the planner) and `datalog_test` (a
standalone test binary for the Datalog engine, source at
`src/search/datalog/datalog_test.cc`).

Release builds compile with `-Werror`, so warnings fail the build. Debug
builds compile with `-fsanitize=undefined -pg`.

## Running the planner

```bash
./powerlifted.py [-d DOMAIN] -i INSTANCE -s SEARCH -e EVALUATOR -g GENERATOR [OPTIONS]
```

Defaults (best known satisficing configuration): `-s alt-bfws1 -e ff -g yannakakis`.
See `README.md` for the full table of search algorithms (`-s`), evaluators
(`-e`), successor generators (`-g`), and additional flags
(`--unit-cost`, `--validate`, `--preprocess-task`, `--seed`, etc.). Multiple
search configurations can be chained with repeated `--iteration S,E,G` flags.

## Tests

There is no unit-testing framework; correctness is checked via a local
regression suite that runs the built planner end-to-end against small PDDL
instances under `dev/domains/`.

```bash
python build.py                       # build first
python dev/run-tests.py --minimal     # small/fast subset
python dev/run-tests.py               # full local suite
python dev/run-tests.py --store-results dev/results.json     # save timing baseline
python dev/run-tests.py --compare-results dev/results.json   # compare against baseline
python dev/test-rule-parser.py        # search's parsing of LB/UB rules (needs Clipper)
```

`dev/test-rule-parser.py` translates the ontology tasks, decodes the
`.lifted` file's rule sections in Python, and compares them with what the
search parsed (printed via the search's `--print-rules`). It also checks that
malformed rule atoms are rejected.

Run the suite serially — the planner writes a shared intermediate file
(`output.lifted`) in the working directory by default, so concurrent runs can
clobber each other. `--validate` in planner options requires the `validate`
binary (from VAL) on `PATH`; the local suite doesn't require it unless a
specific test invokes it.

`dev/run-tests.py` covers, in this order: core plan-cost regressions (`bfs`/
`gbfs` + `blind` on small instances), special-case CLI paths
(`CLI_OPTION_TESTS`, e.g. `clique_bk`, `clique_kckp`, object creation,
disjunctive-precondition/Datalog-split cases), heuristic smoke tests
(`goalcount`, `add`, `hmax`, `ff`, `rff` via `gbfs`), and novelty/width-based
smoke tests (`bfws1`, `bfws1-rx`, `alt-bfws1`, `dq-bfws1-rx`). When a change
touches CLI behavior, search/heuristic/generator behavior, or object creation,
add or update a case here — prefer a tiny instance with a stable, easily
interpreted expected result. `join` on the `organic-synthesis` local instance
is known to be much slower/memory-hungrier than the other cases; that's
expected, not a regression.

## Architecture

### Data flow for a single search

1. `powerlifted.py` → `driver/main.py: main()`.
2. `driver/arguments.py` parses CLI options.
3. `driver/main.py: run_translator()` invokes
   `builds/<mode>/translator/translate.py` as a subprocess on the PDDL
   domain/instance (+ optional ontology file), writing the intermediate
   representation to `options.translator_file` (default `output.lifted`).
4. `driver/single_search_runner.py` (or `driver/portfolio_runner.py` for
   `--iteration` chains) invokes the compiled `search` binary against that
   file with the chosen search/evaluator/generator and any extra C++-side
   flags.
5. If a plan is produced and `--validate` was passed, `driver/main.py:
   validate()` shells out to VAL's `validate`.

### Translator (`src/translator/`)

Classic Fast-Downward-lineage pipeline: `pddl_parser/` (lisp tokenizer →
`pddl_parser/parsing_functions.py`) builds an AST of `src/translator/pddl/`
types (`tasks.py`, `actions.py`, `conditions.py`, `effects.py`, `axioms.py`,
`predicates.py`, `functions.py`, `f_expression.py`, `pddl_types.py`). Then
`normalize.py`, `compile_types.py`, `remove_predicates.py`,
`static_predicates.py`, `simplify.py`, `split_rules.py`, `reachability.py`,
`greedy_join.py`, and `pddl_to_prolog.py`/`graph.py` progressively transform
and analyze it (unlike grounded Fast-Downward, Powerlifted does **not**
ground the state space — this pipeline prepares the lifted representation and
predicate-join structure consumed by the C++ side). `ontology.py` is the
ongoing integration point for description-logic/ontology processing.
`build_model.py` and `complete_state.py` finalize the model written out for
the search component.

### Search (`src/search/`)

- `parser.cc`/`parser.h`, `task.h`/`task.cc`: read the translator's
  intermediate file into the in-memory task model (`action.h`,
  `action_schema.h`, `predicate.h`, `object.h`, `atom.h`,
  `goal_condition.h`, `structures.h`).
- `successor_generators/`: the lifted successor-generation strategies
  selectable via `-g` (`join`, `random_join`, `ordered_join`,
  `full_reducer`, `yannakakis`/clique-based), built on the relational
  `database/` layer (hash join, hash semi-join, project, table) — this is the
  "query optimization" successor generation from the ICAPS 2020 paper.
  `successor_generator_factory.cc` wires `-g` to an implementation.
- `datalog/`: the Datalog engine backing the delete-relaxation heuristics —
  `rules/` (rule representations, including disjunctive existential rules),
  `transformations/` (normal-form conversion, action-predicate removal,
  static stratification, variable renaming/projection), `grounder/`
  (weighted grounder), plus `datalog.cc`/`datalog_atom.cc`/`datalog_fact.cc`/
  `rule_matcher.cc`. Has its own standalone test binary,
  `datalog/datalog_test.cc` (target `datalog_test`).
- `heuristics/` + `delete_relaxation_heuristics/`: `-e` implementations
  (`add`, `blind`, `ff`, `goalcount`, `hmax`, `rff`), built on top of the
  Datalog engine; `heuristic_factory.cc` wires `-e` to an implementation.
- `search_engines/`: `-s` implementations (BFS, A*, greedy/lazy best-first,
  BFWS/alternated-BFWS/dual-queue-BFWS variants, IW); `search_factory.cc`
  wires `-s` to an implementation. `nodes.h`/`search_space.h` hold the
  generic search-node/space machinery shared across engines.
- `novelty/`: width-based search support (novelty tables/checks) used by the
  `iw*`/`bfws*`/`alt-bfws*`/`dq-bfws*` search engines.
- `open_lists/`: open-list implementations (greedy, tie-breaking) used by the
  search engines.
- `states/`: state representation (`state.h`, `sparse_states.h`).
- `algorithms/`: generic reusable data structures/algorithms (bitsets, hash
  sets, cartesian iterators, `kpkc.cc` — Bron-Kerbosch-based k-clique
  enumeration used by the clique successor generator).
- `parallel_hashmap/`: vendored third-party dependency (phmap) — the pattern
  to follow for other vendored deps (see the "Vendoring decision" note in
  `EMBEDDED_LINKING_POWERLIFTED.md` for how the in-progress Konclude
  integration is expected to eventually follow this same pattern).
- `main.cc`: search-binary entry point, ties parsing → heuristic/generator/
  search-engine factories → search execution → `plan_manager.cc` output.

To add a new search algorithm, heuristic, or successor generator: implement
it under the corresponding directory, add its source file(s) to the matching
`set(..._SOURCES ...)` list and, if new, the `add_executable` list in
`src/search/CMakeLists.txt`, then register it in the corresponding
`*_factory.cc` (`search_factory.cc`, `heuristic_factory.cc`,
`successor_generator_factory.cc`) so it's reachable from `-s`/`-e`/`-g`.

### Driver (`driver/`)

- `arguments.py`: CLI option definitions/parsing.
- `main.py`: top-level orchestration (see Data flow above).
- `single_search_runner.py`: runs one search configuration.
- `portfolio_runner.py`: runs chained `--iteration` configurations, numbering
  output plans `plan.1`, `plan.2`, ...
- `preprocessor.py`: optional CPDDL preprocessing (`--preprocess-task`,
  requires `CPDDL_BIN` env var; noted upstream as not fully functional).
- `limits.py`, `utils.py`: resource limits and shared helpers.

## Known limitations (upstream, not bugs to "fix" incidentally)

Axioms, conditional effects, and quantifiers are not supported; negated
preconditions are only supported as inequalities (`(not (= ?x ?y))`). Object
creation (`:new`) is supported in a STRIPS-like fragment but not by every
feature of the planner.
