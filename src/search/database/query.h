#ifndef SEARCH_QUERY_H
#define SEARCH_QUERY_H

#include "../atom.h"
#include "table.h"

#include <vector>

using namespace std;

struct SelectionPattern {
    int predicate_idx;
    vector<pair<int, int>> const_checks;  // (position, object index)
    vector<pair<int, int>> eq_checks;     // (position, first occurrence of same var)
    vector<int> project;                  // first position of each var
    vector<int> vars;                     // final variable indices (-> tuple_index)
};

struct JoinAtom {
    bool is_static;
    Table precompiled;          // if static: precompiled table
    SelectionPattern pattern;   // if not static: pattern for select_tuples
};

struct FilterAtom {
    int predicate_idx;
    bool negated;
    bool is_static;
    int join_step = -1;   // step in the join program at which the filter becomes applicable
    vector<int> arg_map;  // per position:
                          //  for variables, specifies the source column (>= 0) in the joined table
                          //  for constants with index c, stores -c-1
};

class Query {
public:
    Query(const vector<Atom> &atoms, const vector<Atom> &equality_atoms,
        const vector<bool> &nullary_positive_atoms, const vector<bool> &nullary_negated_atoms,
        const vector<Relation> &static_relations);

    // TODO: for semi-naive evaluation, add a "Delta" argument
    Table evaluate(const vector<Relation> &relations, const vector<bool> &nullary_atoms) const;

private:
    // Whether the query is statically unsatisfiable
    bool statically_unsatisfiable = false;

    // all positive query atoms, static or not
    vector<JoinAtom> join_atoms;

    // all ground atoms (except nullary), only non-static
    // static ground atoms are removed by precompilation
    vector<FilterAtom> ground_atoms;

    // indicators for nullary atoms, of the form (predicate_idx, negated)
    vector<pair<int, bool>> nullary_atoms;

    // all filter atoms (except nullary or =), static or not, negation is assumed to be safe
    // this also includes positive atoms whose variables are already covered by the join_atoms
    vector<FilterAtom> filter_atoms;

    // =-atoms (non-ground), which are filtered separately
    // ground =-atoms are removed by precompilation
    vector<FilterAtom> eq_filters;

    // pre-computed tuple_idx of the final joined table
    vector<int> tuple_idx;

    // a reference to the static relations, used for filtering
    const vector<Relation> *static_relations = nullptr;

    static SelectionPattern compile_selection_pattern(const Atom &a);

    static Table select_tuples(const Relation &rel, const SelectionPattern &pattern);

    static void compile_join_atom(const Atom &atom, Query &q, const Relation &rel, const SelectionPattern &pattern);

    static JoinAtom compile_join_atom(const Atom &atom, const Relation &rel, const SelectionPattern &pattern);

    static FilterAtom compile_filter_atom(const Atom &atom, const Relation &rel);

    static bool static_ground_atom_satisfied(const Atom &atom, const Relation &rel);

    static bool ground_eq_atom_satisfied(const Atom &atom);

    static void update_filter_atom(FilterAtom &atom, const vector<int> &tuple_idx, const vector<int> &first_step);

    void filter(Table &working_table, int join_step, const vector<Relation> &relations) const;

    void filter_eq(Table &working_table, int join_step, const vector<Relation> &relations) const;
};

#endif //SEARCH_QUERY_H
