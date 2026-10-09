#ifndef SEARCH_QUERY_H
#define SEARCH_QUERY_H

#include "../atom.h"
#include "../structures.h"
#include "table.h"

#include <vector>
#include <utility>

class Query {
public:
    Query(const std::vector<Atom> &atoms,
        const std::vector<Atom> &equality_atoms,
        const std::vector<bool> &nullary_positive_atoms,
        const std::vector<bool> &nullary_negated_atoms,
        const std::vector<Relation> &static_relations);

    // TODO: for semi-naive evaluation, add a "Delta" argument
    Table evaluate(const std::vector<Relation> &relations,
        const std::vector<bool> &nullary_atoms) const;

private:

    struct SelectionPattern {
        int predicate_idx;
        std::vector<std::pair<int, int>> const_checks;  // (position, object index)
        std::vector<std::pair<int, int>> eq_checks;     // (position, first occurrence of same var)
        std::vector<int> project;                       // first position of each var
        std::vector<int> vars;                          // final variable indices (-> tuple_index)
    };

    struct JoinAtom {
        bool is_static;
        Table precompiled;         // if static: precompiled table
        SelectionPattern pattern;  // if not static: pattern for select_tuples
    };

    struct FilterAtom {
        int predicate_idx;
        bool negated;
        bool is_static;
        int join_step = -1;        // step in the join program at which the filter becomes applicable
        std::vector<int> arg_map;  // per position:
                                   //  for variables, the source column (>= 0) in the joined table
                                   //  for constants with index c, stores -c-1
    };

    struct GroundFilter {
        int predicate_idx;
        bool negated;
        GroundAtom tuple;
    };

    // Whether the query is statically unsatisfiable
    bool statically_unsatisfiable = false;

    // positive query atoms that contribute new variables to the join, static or not
    std::vector<JoinAtom> join_atoms;

    // all ground atoms (except nullary), only non-static
    // (static ground atoms are removed by precompilation)
    std::vector<GroundFilter> ground_atoms;

    // indicators for nullary atoms, of the form (predicate_idx, negated)
    std::vector<std::pair<int, bool>> nullary_atoms;

    // all filter atoms (except nullary or =), static or not, negation is assumed to be safe
    // this also includes positive atoms whose variables are already covered by the join_atoms
    std::vector<FilterAtom> filter_atoms;

    // =-atoms (non-ground), which are filtered separately
    // ground =-atoms are removed by precompilation
    std::vector<FilterAtom> eq_filters;

    // pre-computed tuple_idx of the final joined table
    std::vector<int> tuple_idx;

    // a reference to the static relations, used for filtering
    const std::vector<Relation> *static_relations = nullptr;

    static SelectionPattern compile_selection_pattern(const Atom &a);

    static Table select_tuples(const Relation &rel, const SelectionPattern &pattern);

    static JoinAtom compile_join_atom(const SelectionPattern &pattern, const Relation &rel);

    static FilterAtom compile_filter_atom(const Atom &atom, const Relation &rel);

    static GroundFilter compile_ground_filter_atom(const Atom &atom);

    static bool static_ground_atom_violated(const Atom &atom, const Relation &rel);

    static bool ground_eq_atom_violated(const Atom &atom);

    static void update_filter_atom(FilterAtom &atom, const std::vector<int> &tuple_idx,
        const std::vector<int> &first_step);
    
    template <class Pred>
    static void discard_tuples(std::vector<Table::tuple_t> &v, Pred p);

    void filter(Table &working_table, int join_step, const std::vector<Relation> &relations) const;

    void filter_eq(Table &working_table, int join_step) const;
};

#endif //SEARCH_QUERY_H
