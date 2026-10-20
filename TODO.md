### Aktl.

- [x] Remove negation in `DatalogAtom` (not supported!)
- [x] Remove inequality in LB rules!
- [ ] Vocab for query0 (mkos)
- [x] Mapping between negated predicate and predicate (in LB) for UB

### Later
- [x] Konnect Konclude
- [ ] Real conjunctive query answering instead of stub for Konclude

### Konclude disabled by default
Konclude runs in a worker process (`konclude_worker` from the Konclude
checkout); the search only compiles its client. Building with it needs
`python build.py --konclude` (CMake `USE_KONCLUDE`); using it, also
`--use-konclude` (to `powerlifted.py` or the `search` binary; with
`powerlifted.py --build` it builds with it too), which so far only starts a
worker (smoke test). Search peak memory on blocks: 7.5 MB either way (the
worker is a separate process; the previous in-process library took 75 MB,
~1 GB with its smoke test).
- [x] Methods for state diffs and mko queries: `KoncludeStateReasoner`
  (`src/search/konclude/state_reasoner.h`), tested by `dev/test-konclude.py`
  on the team task.
- [x] Translator: write the vocabulary (predicate → ontology IRI) and the
  normalized ontology in OWL functional syntax (`--konclude-ontology-file`,
  `src/translator/owl/functional_serializer.py`; the `.lifted` file's
  `ONTOLOGY` section names both). The driver makes it a temporary file with
  `--use-konclude` and deletes it after planning (the worker reloads it on
  every restart). The search loads it and tells the initial state.
- [ ] Translator: each mko's query as one SPARQL SELECT per connected
  component.
- [ ] Search: call `set_state` and `entailed` for an mko whose lowerbound and
  upperbound answers differ; consider caching answers per state.
- [ ] Konclude misses `Captain(alice)` on the team ontology, and hangs on a
  smaller variant (max cardinality; Konclude's
  `docs/INCREMENTAL_REASONING.md` §4). The worker client has no timeout yet.
- [ ] Once Konclude is supported, make it the default: `USE_KONCLUDE` ON in
  `src/search/CMakeLists.txt` and `build.py`, `konclude(false)` → `true` in
  `src/search/options.h`.
