"""
Names the query compilation generates itself (mirrors pddl-horndl's
compilation/naming.py).

Generated names are written in uppercase (QUERY<i>, DATALOG_<P>), while every
user name reaching this point is lowercase — PDDL names are lowercased by
pddl_parser.lisp_parser and OWL names by owl.expressions.parse_name — so a
generated name can never coincide with a user name. queries.names.check_names
additionally reserves the lowercase spellings (e.g. "query0"), exactly as
pddl-horndl does, since Clipper's own view of names is case-insensitive.
"""

import re

QUERY_PREDICATE_NAME = "QUERY"
_QUERY_NAME = re.compile(QUERY_PREDICATE_NAME + r"(\d+)")
PRIME_PREFIX = "DATALOG_"


def query_predicate_name(idx):
    return f"{QUERY_PREDICATE_NAME}{idx}"


def get_query_id(name):
    """Index i of a generated QUERY<i> name, or None for any other name.

    Clipper preserves the case of query heads, so the match is exact; a user
    concept such as "queryresult" is not a query.
    """
    match = _QUERY_NAME.fullmatch(name)
    return int(match.group(1)) if match else None


def is_primed_predicate_name(name):
    return name.startswith(PRIME_PREFIX)


def prime_predicate_name(original):
    return f"{PRIME_PREFIX}{original.upper()}"
