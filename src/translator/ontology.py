"""
Compiles the ontology and the task's mkos into lowerbound rules (the
counterpart of pddl-horndl's compilation/pipeline.py Compiler, without the
coherence update):

1. collect the query of every mko (queries.ucq_collector);
2. check that the task's and the ontology's names can be translated into
   Clipper's spelling and back (queries.names);
3. format the queries for Clipper and rewrite them together with the shifted
   ontology (queries.rewriter, rules.lowerbound);
4. clean up Clipper's rules and separate what the ontology entails from what
   the state holds by priming derived predicates (queries.datalog);
5. replace every mko by the literal reading its answer.

Rules are kept as DisjunctiveExistentialRule objects on task.ontology_rules.
"""

import os
import shutil
from pathlib import Path

from normalize import all_conditions
from owl import normalize_ontology, parse_owl
from pddl import Literal, MinimalKnowledgeOperator
from queries import datalog
from queries.names import (
    ClipperSpelling,
    OntologyNames,
    check_names,
    pddl_predicate_names,
)
from queries.naming import query_predicate_name
from queries.rewriter import prepare_queries, query_atoms
from queries.ucq_collector import UCQCollector
from rules import compute_lowerbound_rules, print_rules, shifted_ontology_axioms

CLIPPER_PATH_ENVIRONMENT_VARIABLE = "CLIPPER_PATH"
DEFAULT_CLIPPER_PATH = "clipper.sh"
# Clipper as a sibling checkout of this repository, like the Konclude
# checkout src/search/CMakeLists.txt expects (KONCLUDE_REPO_ROOT).
SIBLING_CLIPPER_PATH = Path(
    "..", "clipper", "clipper-distribution", "target", "clipper", "clipper.sh"
)


def _visit_mkos(condition, fn):
    """condition with every mko replaced by fn(mko), in document order."""
    if isinstance(condition, MinimalKnowledgeOperator):
        return fn(condition)
    if isinstance(condition, Literal) or not condition.parts:
        return condition
    return condition.change_parts([_visit_mkos(part, fn) for part in condition.parts])


def _apply_to_all_mkos(task, fn):
    for proxy in all_conditions(task):
        proxy.set(_visit_mkos(proxy.condition, fn))


def _collect_ucqs(task):
    collector = UCQCollector()

    def collect(mko):
        collector(mko)
        return mko

    _apply_to_all_mkos(task, collect)
    collector.number_queries()
    return collector


def _reachable_predicates(task):
    """Predicates the state can hold: those of the initial state and of
    action effects."""
    names = {atom.predicate for atom in task.init}
    for action in task.actions:
        names |= {effect.literal.predicate for effect in action.effects}
    return names


def _repository_root():
    """The directory holding powerlifted.py, found upwards from this file —
    which runs from src/translator/ or from its copy in
    builds/<mode>/translator/."""
    for directory in Path(__file__).resolve().parents:
        if (directory / "powerlifted.py").is_file():
            return directory
    return None


def _resolve_clipper(clipper_path):
    """clipper_path, else $CLIPPER_PATH, else clipper.sh on PATH, else a
    sibling Clipper checkout of this repository."""
    if clipper_path or os.environ.get(CLIPPER_PATH_ENVIRONMENT_VARIABLE):
        candidates = [clipper_path or os.environ[CLIPPER_PATH_ENVIRONMENT_VARIABLE]]
    else:
        candidates = [DEFAULT_CLIPPER_PATH]
        root = _repository_root()
        if root is not None:
            candidates.append(str((root / SIBLING_CLIPPER_PATH).resolve()))
    for candidate in candidates:
        if shutil.which(candidate) is not None:
            return candidate
    raise FileNotFoundError(
        "Clipper not found; tried: "
        + ", ".join(repr(c) for c in candidates)
        + f" (pass --clipper or set {CLIPPER_PATH_ENVIRONMENT_VARIABLE})"
    )


def process_ontology(
    task,
    ontology_filepath,
    clipper_path=None,
    filter_unreachable=True,
    filter_irrelevant=True,
    verbose=False,
    debug=False,
):
    """Compile the ontology and the task's mkos into lowerbound rules.

    Stores the rules on task.ontology_rules, declares the predicates they
    introduce in task.predicates, and replaces every mko in the task's
    conditions. Raises owl.UnsupportedConstructError if the ontology isn't
    fully supported, and queries.names.NameClashError if its names and the
    task's can't be translated into Clipper's spelling safely.
    """
    clipper_path = _resolve_clipper(clipper_path)
    collector = _collect_ucqs(task)

    ontology = parse_owl(ontology_filepath)
    ontology_names = OntologyNames(ontology)
    normalize_ontology(ontology)
    axioms = shifted_ontology_axioms(ontology)
    ontology_names.add_generated(axioms)
    check_names(task, ontology_names)
    spelling = ClipperSpelling(pddl_predicate_names(task))

    queries, unparameterized = prepare_queries(collector.ucqs, spelling.to_clipper)
    query_predicates = {
        spelling.to_clipper(name): arity
        for name, arity in query_atoms(collector.ucqs).items()
    }
    raw_rules, new_rules = compute_lowerbound_rules(
        ontology,
        clipper_path,
        debug=debug,
        queries=[q for group in queries for q in group],
        query_predicates=query_predicates,
        axioms=axioms,
    )

    rules = datalog.rename_rules(raw_rules, spelling)
    rules, duplicates = datalog.deduplicate_rules(rules, unparameterized)
    unreachable, irrelevant = [], []
    if filter_unreachable:
        rules, unreachable = datalog.filter_unreachable_rules(
            rules, _reachable_predicates(task)
        )
    if filter_irrelevant:
        rules, irrelevant = datalog.filter_irrelevant_rules(
            rules, collector.queried_predicates, len(collector.ucqs)
        )
    derived = datalog.derived_predicates(rules)
    rules, new_predicates = datalog.compile_rules(rules, task.predicates)

    # A query Clipper derives nothing for still needs its (then never true)
    # predicate declared, as some condition reads it.
    for i, ucq in enumerate(collector.ucqs):
        name = query_predicate_name(i)
        if name not in derived:
            arity = len(ucq.free_variables())
            new_predicates.append(datalog.primed_predicate(name, arity))
    task.predicates.extend(new_predicates)
    _apply_to_all_mkos(task, lambda mko: collector.replacement(mko, derived))
    task.ontology_rules = rules

    if verbose:
        _print_compilation_information(
            queries, rules, duplicates, unreachable, irrelevant, new_rules
        )
    for warning in ontology.warnings:
        print(f"Ontology warning: {warning}")

    return ontology


def _print_compilation_information(
    queries, rules, duplicates, unreachable, irrelevant, new_rules
):
    for i, group in enumerate(queries):
        for q in group:
            print(f"%% {query_predicate_name(i)}: {q}")
    for title, section in (
        ("RULES", rules),
        ("DUPLICATE RULES", duplicates),
        ("UNREACHABLE RULES", unreachable),
        ("IRRELEVANT RULES", irrelevant),
        ("RULES USING PREDICATES CLIPPER INTRODUCED", new_rules),
    ):
        if section:
            print(f"%% {title}:")
            print_rules(section)
