import errno
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from build import PROJECT_ROOT, build

from . import arguments, portfolio_runner
from .preprocessor import preprocess_cpddl
from .single_search_runner import run_single_search
from .utils import remove_temporary_files, silent_remove


def validate(domain_name, instance_name, planfile):
    plan = Path(planfile)
    if not plan.is_file():
        logging.info(f'No plan file to validate could be found at "{planfile}"')
        return

    try:
        validate_inputs = ["validate", domain_name, instance_name, planfile]
        _ = subprocess.call(" ".join(validate_inputs), shell=True)
    except OSError as err:
        if err.errno == errno.ENOENT:
            logging.error("Error: 'validate' binary not found. Is it on the PATH?")
            return
        else:
            logging.error(f"Error executing 'validate': {err}")


def run_search(build_dir, options, extra):

    if options.iteration is None:
        code = run_single_search(
            build_dir,
            options.time_limit,
            options.translator_file,
            options.search,
            options.heuristic,
            options.generator,
            str(options.seed),
            options.plan_file,
            extra,
        )

        # If we found a plan, try to validate it
        if code == 0 and options.validate:
            validate(options.domain, options.instance, options.plan_file)
        remove_temporary_files(options)
        return code
    else:
        return portfolio_runner.run(build_dir, options, extra)


def run_translator(build_dir, options, extra):
    translator_args = [
        os.path.join(build_dir, "translator", "translate.py"),
        options.domain,
        options.instance,
    ]
    if options.ontology is not None:
        translator_args += ["--ontology", options.ontology]
    if options.clipper is not None:
        translator_args += ["--clipper", options.clipper]
    if options.konclude_ontology_file is not None:
        translator_args += ["--konclude-ontology-file", options.konclude_ontology_file]
    translator = subprocess.Popen(
        translator_args + ["--output-file", options.translator_file] + extra
    )
    translator.communicate()
    if translator.returncode != 0:
        raise RuntimeError("Error during preprocessing/translation.")


def set_extra_options(options):
    CPP_EXTRA_OPTIONS = []
    PYTHON_EXTRA_OPTIONS = []

    if options.keep_action_predicates:
        PYTHON_EXTRA_OPTIONS.append("--keep-action-predicates")
    if options.keep_duplicated_rules:
        PYTHON_EXTRA_OPTIONS.append("--keep-duplicated-rules")
    if options.add_inequalities:
        PYTHON_EXTRA_OPTIONS.append("--add-inequalities")

    # If it is a width-based search, we might need to pass more flags
    if options.full_novelty_check:
        CPP_EXTRA_OPTIONS.append("--full-novelty-check")
    if options.novelty_early_stop:
        CPP_EXTRA_OPTIONS += ["--novelty-early-stop", str(1)]
    if options.use_konclude:
        CPP_EXTRA_OPTIONS.append("--use-konclude")
    if options.konclude_restart_every is not None:
        CPP_EXTRA_OPTIONS += [
            "--konclude-restart-every",
            str(options.konclude_restart_every),
        ]

    # Checks if unit-cost flag is true
    if options.unit_cost:
        PYTHON_EXTRA_OPTIONS += ["--unit-cost"]

    return PYTHON_EXTRA_OPTIONS, CPP_EXTRA_OPTIONS


def main():

    options = arguments.parse_options()

    build_dir = os.path.join(
        PROJECT_ROOT, "builds", "debug" if options.debug else "release"
    )

    if options.build:
        build(options.debug, options.cxx_compiler, options.use_konclude)

    # Create build path
    if not os.path.exists(build_dir):
        raise OSError("Planner not built!")

    if options.preprocess_task:
        preprocess_cpddl(options)

    PYTHON_EXTRA_OPTIONS, CPP_EXTRA_OPTIONS = set_extra_options(options)

    # The normalized ontology for the search's Konclude reasoner, which the
    # translator writes: the Konclude worker reloads it whenever it restarts,
    # so it may only go once planning is over.
    options.konclude_ontology_file = None
    if options.use_konclude and options.ontology is not None:
        fd, options.konclude_ontology_file = tempfile.mkstemp(
            prefix="powerlifted-ontology-", suffix=".ofn"
        )
        os.close(fd)

    try:
        # Invoke the Python preprocessor
        run_translator(build_dir, options, PYTHON_EXTRA_OPTIONS)

        # Invoke the C++ search component
        search_exit_code = run_search(build_dir, options, CPP_EXTRA_OPTIONS)
    finally:
        if options.konclude_ontology_file is not None:
            silent_remove(options.konclude_ontology_file)

    return search_exit_code
