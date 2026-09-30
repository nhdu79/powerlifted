#! /usr/bin/env python3
"""
Load and normalize every ontology under dev/ontologies/, compute
TODO.md's "Computing Lowerbound rules pipeline" (now entirely given by
Clipper rewriting the shifted ontology — see
rules.lowerbound.lowerbound_rules.compute_lowerbound_rules), and print the
resulting rules — for manual inspection. Not a test — makes no
assertions.

Requires a Clipper binary, resolved the same way TODO.md's own snippet
does (a fixed list of per-machine paths).

Run with:

    python3 dev/print_lowerbound_rules.py

from anywhere (paths are resolved relative to this file).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRANSLATOR_DIR = _REPO_ROOT / "src" / "translator"
sys.path.insert(0, str(_TRANSLATOR_DIR))

from owl import normalize_ontology, parse_owl
from owl.parser import UnsupportedConstructError
from rules import compute_lowerbound_rules, format_rule

ONTOLOGY_DIR = _REPO_ROOT / "dev" / "ontologies"

_CLIPPER_CANDIDATES = [
    "/home/zinzin2312/repos/clipper/clipper-distribution/target/clipper/clipper.sh",
    "/Users/duynhu/repos/clipper/clipper-distribution/target/clipper/clipper.sh",
]


def _resolve(name: str, candidates: list[str]) -> str:
    for path in candidates:
        if Path(path).exists():
            return path
    raise FileNotFoundError(
        f"{name} not found. Searched:\n" + "\n".join(f"  {p}" for p in candidates)
    )


def main() -> None:
    clipper_path = _resolve("Clipper", _CLIPPER_CANDIDATES)

    for path in sorted(ONTOLOGY_DIR.glob("*.owl")):
        if "team" not in path.name:
            continue
        print(f"=== {path.name} ===")
        ontology = parse_owl(str(path))
        normalize_ontology(ontology)

        try:
            rules, new_rules = compute_lowerbound_rules(ontology, clipper_path)
        except UnsupportedConstructError as error:
            print(f"skipped — {error}")
            print()
            continue

        print(f"lowerbound rules ({len(rules)}):")
        for rule in rules:
            print(f"  {format_rule(rule)}")

        if new_rules:
            print(f"rules using a predicate Clipper introduced ({len(new_rules)}):")
            for rule in new_rules:
                print(f"  {format_rule(rule)}")

        if ontology.warnings:
            print("warnings:")
            for warning in ontology.warnings:
                print(f"  {warning}")

        print()


if __name__ == "__main__":
    main()
