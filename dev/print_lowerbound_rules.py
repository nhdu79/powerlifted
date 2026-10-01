#! /usr/bin/env python3
"""
Parse dev/domains/team (domain.pddl + problem.pddl — the mko-using "team"
task written against dev/ontologies/team.owl), normalize it the same way
translate.py does, then run it through ontology.process_ontology and print
the resulting lowerbound rules on task.lowerbound_rules — for manual
inspection. Not a test — makes no assertions.

process_ontology itself resolves Clipper the same way translate.py's own
call does: $CLIPPER_PATH, else clipper.sh on PATH, else a sibling ../clipper
checkout of this repository (see ontology._resolve_clipper).

Run with:

    python3 dev/print_lowerbound_rules.py

from anywhere (paths are resolved relative to this file).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRANSLATOR_DIR = _REPO_ROOT / "src" / "translator"
sys.path.insert(0, str(_TRANSLATOR_DIR))

DOMAIN_FILE = _REPO_ROOT / "dev" / "domains" / "team" / "domain.pddl"
PROBLEM_FILE = _REPO_ROOT / "dev" / "domains" / "team" / "problem.pddl"
ONTOLOGY_FILE = _REPO_ROOT / "dev" / "ontologies" / "team.owl"

# pddl_parser eagerly imports options, whose module-level setup() parses
# sys.argv for required "domain"/"task" positionals (translate.py's own CLI)
# the instant it's imported — before we get a chance to call pddl_parser.open
# with our own explicit filenames. Feed it argv of our own so that import
# doesn't blow up; the values themselves are unused, since we always pass
# domain_filename/task_filename explicitly below.
sys.argv = [sys.argv[0], str(DOMAIN_FILE), str(PROBLEM_FILE)]

import normalize
import pddl_parser
from ontology import process_ontology
from owl.parser import UnsupportedConstructError
from queries.names import NameClashError


def main() -> None:
    print(f"=== {ONTOLOGY_FILE.name} ({DOMAIN_FILE.parent.name}) ===")

    task = pddl_parser.open(
        domain_filename=str(DOMAIN_FILE), task_filename=str(PROBLEM_FILE)
    )
    normalize.normalize(task)

    try:
        process_ontology(task, str(ONTOLOGY_FILE), verbose=True)
    except (UnsupportedConstructError, NameClashError) as error:
        print(f"skipped — {error}")
        return

    print(f"lowerbound rules on task.lowerbound_rules: {len(task.lowerbound_rules)}")


if __name__ == "__main__":
    main()
