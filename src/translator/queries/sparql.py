"""
Translates the task's mkos into SPARQL for the search's Konclude reasoner
(src/search/konclude/state_reasoner.h, KoncludeQuery), each once (MkoQueries
keeps the known ones), so every precondition and the goal reuse them.

After UCQCollector.replacement, an mko is an atom flagged mko, in a
precondition or the goal, negated or not (the search applies the negation):
* a QUERY<i> atom, standing for the i-th collected query (syntactically equal
  mkos already share it). Its query is that UCQ, its answer variables x0,
  x1, ... its free variables in sorted order, i.e. QUERY<i>'s arguments, so
  every QUERY<i> atom shares it, whatever its arguments.
* any other atom, an atomic mko. Atoms that differ only in their variables'
  names are the same mko: its pattern (mko_pattern) renames the variables
  ?x0, ?x1, ... by first occurrence, which are its answer variables x0, x1,
  ..., in that order.

A conjunctive query becomes one SPARQL SELECT (one basic graph pattern) per
connected component, as Konclude answers only the first component of a
disconnected pattern; the search takes the product of the components'
answers, and the union over the conjunctive queries. (For a Horn ontology,
which the lowerbound's Clipper requires anyway, the certain answers of a UCQ
are the union of those of its CQs.)

The answer variables keep their names; the other variables, which are
existential, are the blank nodes _:y0, _:y1, ...: Konclude binds every
?variable to a named individual, selected or not, and only treats a blank
node as an existential (possibly anonymous) individual. A component selects
its answer variables; one without any, e.g. a ground atom, is an ASK, which
keeps (if entailed) or empties the product.

A query is not translated if it reads a predicate that is no class or object
property of the ontology (Konclude doesn't know it).
"""

from pddl import Atom, Conjunction, Disjunction, ExistentialCondition
from rules.atoms import is_variable

from .naming import get_query_id

RDF_TYPE = "a"


class UntranslatableQuery(Exception):
    pass


def _conjunctive_queries(ucq):
    for cq in ucq.parts if isinstance(ucq, Disjunction) else (ucq,):
        if isinstance(cq, ExistentialCondition):
            (cq,) = cq.parts
        yield list(cq.parts) if isinstance(cq, Conjunction) else [cq]


def mko_pattern(atom):
    """(predicate, arguments) of the mko atom, with its variables renamed
    ?x0, ?x1, ... by first occurrence: the key of its query."""
    names = {}
    for x in atom.args:
        if is_variable(x) and x not in names:
            names[x] = f"?x{len(names)}"
    return atom.predicate, tuple(names.get(x, x) for x in atom.args)


def _components(atoms):
    """atoms split into connected components (atoms sharing a variable are
    connected), in order of their first atom."""
    components = []  # [(variables, atom indices)]
    for i, atom in enumerate(atoms):
        variables = {x for x in atom.args if is_variable(x)}
        indices = [i]
        rest = []
        for component in components:
            if variables & component[0]:
                variables |= component[0]
                indices += component[1]
            else:
                rest.append(component)
        components = rest + [(variables, indices)]
    components.sort(key=lambda c: min(c[1]))
    return [(variables, [atoms[i] for i in sorted(indices)]) for variables, indices in components]


def _triple(atom, predicate_iris, terms):
    iri = predicate_iris.get(atom.predicate)
    if iri is None:
        raise UntranslatableQuery(
            f"{atom} is not a class or object property assertion of the ontology"
        )
    args = [terms[x] for x in atom.args]
    if len(args) == 1:
        return f"{args[0]} {RDF_TYPE} <{iri}> ."
    if len(args) == 2:
        return f"{args[0]} <{iri}> {args[1]} ."
    raise UntranslatableQuery(f"{atom} is neither unary nor binary")


def translate_cq(atoms, answer_names, predicate_iris, object_iri_prefix):
    """The SPARQL SELECT (ASK, if it has no answer variable) of each
    connected component of the conjunctive query atoms — answer_names names
    the answer variables ({PDDL variable: name}, in answer order)."""
    terms = {}  # PDDL term -> SPARQL term
    existentials = []
    for atom in atoms:
        for x in atom.args:
            if x not in terms:
                if not is_variable(x):
                    terms[x] = f"<{object_iri_prefix}{x}>"
                elif x in answer_names:
                    terms[x] = "?" + answer_names[x]
                else:
                    terms[x] = f"_:y{len(existentials)}"
                    existentials.append(x)
    queries = []
    for variables, component in _components(atoms):
        selected = [terms[x] for x in answer_names if x in variables]
        pattern = " ".join(_triple(a, predicate_iris, terms) for a in component)
        if selected:
            queries.append(f"SELECT {' '.join(selected)} WHERE {{ {pattern} }}")
        else:
            queries.append(f"ASK {{ {pattern} }}")
    return queries


def translate_mko(pattern, predicate_iris, object_iri_prefix):
    """(answer variables, [components]) for the mko pattern (see
    mko_pattern): its answer variables x0, x1, ... and its one conjunctive
    query, as translate_cq gives it. Raises UntranslatableQuery."""
    predicate, args = pattern
    answer_names = {}
    for x in args:
        if is_variable(x):
            answer_names[x] = x[1:]
    query = translate_cq(
        [Atom(predicate, args)], answer_names, predicate_iris, object_iri_prefix
    )
    return list(answer_names.values()), [query]


def translate_ucq(ucq, predicate_iris, object_iri_prefix):
    """(answer variables, [components per conjunctive query]) for
    the query ucq of a QUERY<i>: its answer variables x0, x1, ... are its free
    variables in sorted order. Raises UntranslatableQuery."""
    answer_names = {x: f"x{i}" for i, x in enumerate(sorted(ucq.free_variables()))}
    cqs = [
        translate_cq(
            [Atom(a.predicate, a.args) for a in atoms],
            answer_names,
            predicate_iris,
            object_iri_prefix,
        )
        for atoms in _conjunctive_queries(ucq)
    ]
    return list(answer_names.values()), cqs


class MkoQueries:
    """The known mkos and their queries, each translated once: a hash from
    an mko's key (its QUERY<i> name, or the pattern of an atomic mko) to its
    query (answer variables, [components per conjunctive query]),
    None if it has no translation."""

    def __init__(self, ucqs, predicate_iris, object_iri_prefix):
        self.ucqs = ucqs
        self.predicate_iris = predicate_iris
        self.object_iri_prefix = object_iri_prefix
        self.queries = {}
        self.untranslatable = {}  # key -> reason

    def add(self, literal):
        """The key of the mko literal (None if it isn't one), translating its
        query unless it is already known."""
        if not literal.mko:
            return None
        query_id = get_query_id(literal.predicate)
        key = literal.predicate if query_id is not None else mko_pattern(literal)
        if key not in self.queries:
            try:
                if query_id is not None:
                    query = translate_ucq(
                        self.ucqs[query_id], self.predicate_iris, self.object_iri_prefix
                    )
                else:
                    query = translate_mko(key, self.predicate_iris, self.object_iri_prefix)
            except UntranslatableQuery as e:
                query = None
                self.untranslatable[key] = str(e)
            self.queries[key] = query
        return key

    def query_entries(self):
        """[(QUERY<i>, query)] for the known QUERY<i> with a translation, by
        i."""
        return sorted(
            ((key, q) for key, q in self.queries.items() if isinstance(key, str) and q),
            key=lambda entry: get_query_id(entry[0]),
        )

    def mko_entries(self):
        """[(pattern, query)] for the known atomic mkos with a translation, by
        pattern."""
        return sorted(
            (key, q) for key, q in self.queries.items() if not isinstance(key, str) and q
        )
