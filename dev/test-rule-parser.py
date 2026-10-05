#! /usr/bin/env python3
"""
Checks the search component's parser for the LOWERBOUND-RULES and
UPPERBOUND-RULES sections (parse_rules in src/search/parser.cc).

For each task below, it runs the translator, decodes the rule sections of the
resulting .lifted file independently (predicate and object names come from
its PREDICATES/OBJECTS sections, by index), and compares them rule by rule
with what the search binary parsed, as printed by --print-rules. It also
checks that the search rejects malformed rule atoms: a negated atom
(unsupported) and an argument that is neither 'c' nor 'p'.

Build first, then run from anywhere:

    python build.py
    python dev/test-rule-parser.py [--debug]

The ontology tasks need Clipper (see src/translator/ontology.py).
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASEDIR = Path(__file__).resolve().parent.parent
DOMAINS = BASEDIR / "dev" / "domains"
ONTOLOGIES = BASEDIR / "dev" / "ontologies"

# (label, domain, problem, ontology or None)
TASKS = [
    (
        "team",
        DOMAINS / "team" / "domain.pddl",
        DOMAINS / "team" / "problem.pddl",
        ONTOLOGIES / "team.owl",
    ),
    (
        "drones",
        DOMAINS / "drones" / "domain.pddl",
        DOMAINS / "drones" / "problem.pddl",
        ONTOLOGIES / "drones.owl",
    ),
    (
        "gripper (no ontology)",
        DOMAINS / "gripper" / "domain.pddl",
        DOMAINS / "gripper" / "prob01.pddl",
        None,
    ),
]

RULE_SECTIONS = ("LOWERBOUND-RULES", "UPPERBOUND-RULES")
# Exit codes of src/search/utils/system.h.
SEARCH_INPUT_ERROR = 33
SEARCH_UNSUPPORTED = 34


class LiftedFile:
    """The parts of a .lifted file the rule sections refer to."""

    def __init__(self, path):
        self.lines = path.read_text().splitlines()
        self.predicates = self._names("PREDICATES", lines_per_entry=2)
        self.objects = self._names("OBJECTS", lines_per_entry=1)

    def section_start(self, title):
        """Index of the line "<title> <n>", and n."""
        for i, line in enumerate(self.lines):
            parts = line.split()
            if len(parts) == 2 and parts[0] == title:
                return i, int(parts[1])
        raise ValueError(f"section {title} not found")

    def _names(self, title, lines_per_entry):
        start, n = self.section_start(title)
        names = {}
        for k in range(n):
            name, index = self.lines[start + 1 + k * lines_per_entry].split()[:2]
            names[int(index)] = name
        return names

    def rules(self, title):
        """The rules of a rule section, rendered as the search prints them
        (DisjunctiveExistentialProgram::output_rule, without its suffix)."""
        start, n = self.section_start(title)
        i = start + 1
        rules = []
        for _ in range(n):
            effect_size, body_size, _ = map(int, self.lines[i].split())
            i += 1
            atoms = [
                self._atom(self.lines[i + k]) for k in range(effect_size + body_size)
            ]
            i += effect_size + body_size
            effect, body = atoms[:effect_size], atoms[effect_size:]
            head = ", ".join(effect) if effect else "⊥"
            rules.append(f"{head} :- {', '.join(body)}" if body else head)
        return rules

    def _atom(self, line):
        tokens = line.split()
        name, predicate_index, _negated, number_args = tokens[:4]
        if self.predicates[int(predicate_index)] != name:
            raise ValueError(
                f"predicate index of {line!r} names "
                f"{self.predicates[int(predicate_index)]!r}"
            )
        args = []
        for k in range(int(number_args)):
            kind, index = tokens[4 + 2 * k], int(tokens[5 + 2 * k])
            args.append(self.objects[index] if kind == "c" else f"?v{index}")
        return f"{name}({', '.join(args)})"


def printed_rules(stdout):
    """{section: rules} from the search's --print-rules output, without the
    " [<body type>, index:<i>]." and variable-map suffix of each rule."""
    lines = stdout.splitlines()
    sections = {}
    current = None
    for line in lines:
        if line in RULE_SECTIONS:
            current = sections.setdefault(line, [])
        elif line == "END-RULES":
            current = None
        elif current is not None:
            rule = line[: line.rindex(". [")]
            current.append(re.sub(r" \[\w+, index:\d+\]$", "", rule))
    return sections


def run_search(lifted_path, *extra):
    return subprocess.run(
        [
            str(BASEDIR / "builds" / "release" / "search" / "search"),
            "-f",
            str(lifted_path),
            "-s",
            "gbfs",
            "-e",
            "blind",
            "-g",
            "yannakakis",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def translate(domain, problem, ontology, output_path):
    command = [
        sys.executable,
        str(BASEDIR / "builds" / "release" / "translator" / "translate.py"),
        str(domain),
        str(problem),
        "--output-file",
        str(output_path),
    ]
    if ontology is not None:
        command += ["--ontology", str(ontology)]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def check_task(label, domain, problem, ontology, tmpdir, debug):
    """Error messages for one task (empty if the parser read every rule)."""
    lifted_path = Path(tmpdir) / "task.lifted"
    translation = translate(domain, problem, ontology, lifted_path)
    if translation.returncode != 0:
        return [
            f"translator failed (exit {translation.returncode}):\n"
            + translation.stdout[-2000:]
            + translation.stderr[-2000:]
        ]

    lifted = LiftedFile(lifted_path)
    search = run_search(lifted_path, "--print-rules")
    if search.returncode != 0:
        return [
            f"search --print-rules failed (exit {search.returncode}):\n"
            + search.stderr[-2000:]
        ]
    parsed = printed_rules(search.stdout)

    errors = []
    for title in RULE_SECTIONS:
        expected = lifted.rules(title)
        actual = parsed.get(title)
        if actual is None:
            errors.append(f"{title}: not printed by the search")
            continue
        if debug:
            print(f"  {title}: {len(expected)} rules")
            for rule in actual:
                print(f"    {rule}")
        if len(actual) != len(expected):
            errors.append(
                f"{title}: {len(expected)} rules in the file, {len(actual)} parsed"
            )
        for i, (e, a) in enumerate(zip(expected, actual)):
            if e != a:
                errors.append(
                    f"{title} rule {i}:\n      file:   {e}\n      parsed: {a}"
                )
    if not errors:
        counts = [f"{len(parsed[t])} {t.split('-')[0].lower()}" for t in RULE_SECTIONS]
        print(f"  {', '.join(counts)} rules parsed correctly")
    return errors


def mutate_first_rule_atom(lifted_path, mutate):
    """Rewrite the first atom of the first lowerbound rule with mutate (a
    function on its token list). Returns False if there is no such rule."""
    lifted = LiftedFile(lifted_path)
    start, n = lifted.section_start("LOWERBOUND-RULES")
    if n == 0:
        return False
    atom_line = start + 2  # after the section line and the rule's sizes line
    tokens = lifted.lines[atom_line].split()
    lifted.lines[atom_line] = " ".join(mutate(tokens))
    lifted_path.write_text("\n".join(lifted.lines) + "\n")
    return True


def set_negated(tokens):
    return tokens[:2] + ["1"] + tokens[3:]


def set_bad_argument_kind(tokens):
    if int(tokens[3]) == 0:
        raise ValueError("first lowerbound rule atom has no arguments")
    return tokens[:4] + ["x"] + tokens[5:]


def check_rejections(tmpdir):
    """Error messages for the malformed-input cases (on the team task)."""
    label, domain, problem, ontology = TASKS[0]
    errors = []
    for description, mutate, exit_code, message in (
        ("negated rule atom", set_negated, SEARCH_UNSUPPORTED, "is not supported"),
        (
            "argument neither 'c' nor 'p'",
            set_bad_argument_kind,
            SEARCH_INPUT_ERROR,
            "neither constant nor variable",
        ),
    ):
        lifted_path = Path(tmpdir) / "malformed.lifted"
        translation = translate(domain, problem, ontology, lifted_path)
        if translation.returncode != 0:
            return [f"translator failed on {label} (exit {translation.returncode})"]
        if not mutate_first_rule_atom(lifted_path, mutate):
            return [f"{label} has no lowerbound rule to mutate"]
        search = run_search(lifted_path, "--print-rules")
        if search.returncode != exit_code or message not in search.stderr:
            errors.append(
                f"{description}: expected exit {exit_code} with "
                f"{message!r}, got exit {search.returncode}:\n" + search.stderr[-1000:]
            )
        else:
            print(f"  {description}: rejected (exit {exit_code})")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--debug", action="store_true", help="print the rules the search parsed"
    )
    args = parser.parse_args()

    failures = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        for label, domain, problem, ontology in TASKS:
            print(f"{label}:")
            errors = check_task(label, domain, problem, ontology, tmpdir, args.debug)
            for error in errors:
                print(f"  FAILED {error}")
            failures += bool(errors)
        print("malformed rule atoms (team):")
        errors = check_rejections(tmpdir)
        for error in errors:
            print(f"  FAILED {error}")
        failures += bool(errors)

    print(
        "All rule parser tests passed."
        if not failures
        else f"{failures} rule parser test(s) failed."
    )
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
