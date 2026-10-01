"""
Compiles the ontology and the task's mkos into lowerbound rules (the
counterpart of pddl-horndl's compilation/pipeline.py Compiler, without the
coherence update), and the ontology into upperbound rules:

1. collect the query of every mko (queries.ucq_collector);
2. check that the task's and the ontology's names can be translated into
   Clipper's spelling and back (queries.names);
3. compute the upperbound rules (rules.upperbound), in the task's spelling,
   with a rule per conjunctive query deriving its QUERY<i>;
4. format the queries for Clipper and rewrite them together with the shifted
   ontology (queries.rewriter, rules.lowerbound);
5. clean up Clipper's rules and declare the predicates the lowerbound and
   upperbound rules use that the task doesn't (queries.datalog);
6. replace every mko by the literal reading its answer, flagged mko (see
   pddl.conditions.Literal), which the search evaluates w.r.t. the rules.

Rules are kept as DisjunctiveExistentialRule objects on task.lowerbound_rules
and task.upperbound_rules.
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
from rules import (
    compute_lowerbound_rules,
    compute_upperbound_rules,
    group_by_normal_form,
    print_rules,
    shifted_ontology_axioms,
)
from rules.atoms import EQUALITY_PREDICATE

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


def _uses_equality(condition):
    """Whether condition has an "=" literal, inside an mko or not."""
    if isinstance(condition, Literal):
        return condition.predicate == EQUALITY_PREDICATE
    return any(_uses_equality(part) for part in condition.parts)


def _task_uses_equality(task):
    """Whether the task's conditions use "=" (inside an mko or not)."""
    return any(_uses_equality(proxy.condition) for proxy in all_conditions(task))


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
    """Compile the ontology and the task's mkos into lowerbound rules, and
    the ontology into upperbound rules.

    Stores the rules on task.lowerbound_rules and task.upperbound_rules,
    declares the predicates they introduce in task.predicates, and replaces
    every mko in the task's conditions. Raises owl.UnsupportedConstructError
    if the ontology isn't fully supported, and queries.names.NameClashError if
    its names and the task's can't be translated into Clipper's spelling
    safely.
    """
    clipper_path = _resolve_clipper(clipper_path)
    collector = _collect_ucqs(task)

    ontology = parse_owl(ontology_filepath)
    ontology_names = OntologyNames(ontology)
    normalize_ontology(ontology)
    # Before the mkos are replaced, so an "=" inside one counts too. Tells the
    # upperbound to add the equality axioms and UNA rules (which it also does
    # if the ontology has number restrictions or nominals). The lowerbound
    # needs neither: Clipper derives no "=", it rewrites number restrictions
    # into denials over distinct fillers.
    task_uses_equality = _task_uses_equality(task)
    shifted_axioms = shifted_ontology_axioms(ontology)
    ontology_names.add_generated(shifted_axioms)
    check_names(task, ontology_names)
    clipper_spelling = ClipperSpelling(pddl_predicate_names(task))
    # Before Clipper runs: compute_lowerbound_rules adds a warning to
    # ontology.warnings, which ensure_fully_supported would reject.
    upperbound_rules = compute_upperbound_rules(
        ontology,
        # objects are merged with domain's constants, so below is enough (see parsing_function.py:422)
        constants=[obj.name for obj in task.objects],
        arities={p.name: len(p.arguments) for p in task.predicates},
        uses_equality=task_uses_equality,
        rename=clipper_spelling.to_pddl,
        extra_rules=collector.query_rules(),
    )

    clipper_queries, unparameterized_query_ids = prepare_queries(
        collector.ucqs, clipper_spelling.to_clipper
    )
    clipper_query_predicates = {
        clipper_spelling.to_clipper(name): arity
        for name, arity in query_atoms(collector.ucqs).items()
    }
    clipper_rules, clipper_introduced_rules = compute_lowerbound_rules(
        ontology,
        clipper_path,
        debug=debug,
        queries=[q for group in clipper_queries for q in group],
        query_predicates=clipper_query_predicates,
        axioms=shifted_axioms,
    )

    lowerbound_rules = datalog.rename_rules(clipper_rules, clipper_spelling)
    lowerbound_rules, duplicate_rules = datalog.deduplicate_rules(
        lowerbound_rules, unparameterized_query_ids
    )
    unreachable_rules, irrelevant_rules = [], []
    if filter_unreachable:
        lowerbound_rules, unreachable_rules = datalog.filter_unreachable_rules(
            lowerbound_rules, _reachable_predicates(task)
        )
    if filter_irrelevant:
        lowerbound_rules, irrelevant_rules = datalog.filter_irrelevant_rules(
            lowerbound_rules, collector.queried_predicates, len(collector.ucqs)
        )

    new_predicate_declarations = datalog.predicate_declarations(
        lowerbound_rules + upperbound_rules, task.predicates
    )

    # A query Clipper derives nothing for still needs its (then never true)
    # predicate declared, as some condition reads it.
    declared_names = {p.name for p in new_predicate_declarations}
    for i, ucq in enumerate(collector.ucqs):
        name = query_predicate_name(i)
        if name not in declared_names:
            arity = len(ucq.free_variables())
            new_predicate_declarations.append(datalog.untyped_predicate(name, arity))
    task.predicates.extend(new_predicate_declarations)
    _apply_to_all_mkos(task, collector.replacement)
    task.lowerbound_rules = lowerbound_rules
    task.upperbound_rules = upperbound_rules

    if verbose:
        _print_compilation_information(
            clipper_queries,
            lowerbound_rules,
            duplicate_rules,
            unreachable_rules,
            irrelevant_rules,
            clipper_introduced_rules,
        )
        upperbound_rules_by_form = group_by_normal_form(upperbound_rules)
        print(
            f"%% UPPERBOUND RULES (not listed): {len(upperbound_rules)}, "
            "by normal form: "
            + ", ".join(
                f"{form} {len(form_rules)}"
                for form, form_rules in upperbound_rules_by_form.items()
            )
        )
    for warning in ontology.warnings:
        print(f"Ontology warning: {warning}")

    return ontology


def _print_compilation_information(
    clipper_queries,
    lowerbound_rules,
    duplicate_rules,
    unreachable_rules,
    irrelevant_rules,
    clipper_introduced_rules,
):
    for i, group in enumerate(clipper_queries):
        for q in group:
            print(f"%% {query_predicate_name(i)}: {q}")
    for title, section in (
        ("LOWERBOUND RULES", lowerbound_rules),
        ("DUPLICATE RULES", duplicate_rules),
        ("UNREACHABLE RULES", unreachable_rules),
        ("IRRELEVANT RULES", irrelevant_rules),
        ("RULES USING PREDICATES CLIPPER INTRODUCED", clipper_introduced_rules),
    ):
        if section:
            print(f"%% {title}:")
            print_rules(section)
