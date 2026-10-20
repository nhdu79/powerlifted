#! /usr/bin/env python3
"""
Runs konclude_test (src/search/konclude/konclude_test.cc): the search's
KoncludeStateReasoner on the team task, i.e. state diffs sent to the Konclude
worker process and the task's mko queries answered over them.

It translates the team task with its ontology (so the test reads the same
.lifted file the search would), including the normalized ontology in OWL
functional syntax, which Konclude reads, and runs the test on it.

Build with Konclude first, then run from anywhere:

    python build.py --konclude
    python dev/test-konclude.py [--restart-every N] [--debug]

The translation needs Clipper (see src/translator/ontology.py).
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

BASEDIR = Path(__file__).resolve().parent.parent
DOMAINS = BASEDIR / "dev" / "domains"
ONTOLOGIES = BASEDIR / "dev" / "ontologies"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--restart-every",
        type=int,
        default=2,
        help="restart the Konclude worker every N state changes (default: 2)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="use the debug build"
    )
    args = parser.parse_args()

    build = BASEDIR / "builds" / ("debug" if args.debug else "release")
    test_binary = build / "search" / "konclude_test"
    if not test_binary.is_file():
        sys.exit(f"{test_binary} not found; build with: python build.py --konclude")

    with tempfile.TemporaryDirectory() as tmpdir:
        lifted_path = Path(tmpdir) / "team.lifted"
        ontology_path = Path(tmpdir) / "team.ofn"
        translation = subprocess.run(
            [
                sys.executable,
                str(build / "translator" / "translate.py"),
                str(DOMAINS / "team" / "domain.pddl"),
                str(DOMAINS / "team" / "problem.pddl"),
                "--ontology",
                str(ONTOLOGIES / "team.owl"),
                "--konclude-ontology-file",
                str(ontology_path),
                "--output-file",
                str(lifted_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if translation.returncode != 0:
            sys.exit(
                f"translator failed (exit {translation.returncode}):\n"
                + translation.stderr[-2000:]
            )
        test = subprocess.run(
            [
                str(test_binary),
                str(lifted_path),
                "",  # the worker the build was configured with
                str(args.restart_every),
            ],
            check=False,
        )
    sys.exit(test.returncode)


if __name__ == "__main__":
    main()
