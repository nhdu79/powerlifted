### Aktl.

- [ ] Remove negation in `DatalogAtom` (not supported!)
- [ ] Remove inequality in LB rules!

### Later
- [x] Konnect Konclude
- [ ] Real conjunctive query answering instead of stub for Konclude (waiting for Andreas Steigmiller)

### Konclude disabled by default
The embedded reasoner is only stubbed, so it is neither linked nor used by
default. Linking needs `python build.py --konclude` (CMake `USE_KONCLUDE`);
using it, also `--use-konclude` (to `powerlifted.py` or the `search` binary;
with `powerlifted.py --build` it links it too). Peak memory on blocks:
7.5 MB unlinked, 75 MB linked, ~1 GB with its startup smoke test.
- [ ] Once Konclude is supported, make it the default: `USE_KONCLUDE` ON in
  `src/search/CMakeLists.txt` and `build.py`, `konclude(false)` → `true` in
  `src/search/options.h`, and replace the smoke test in `src/search/main.cc`
  with the real ontology wiring.
