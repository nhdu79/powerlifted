
#include "query.h"
#include "hash_join.h"
#include "../utils/collections.h"

using namespace std;

Query::Query(const vector<Atom> &atoms, const vector<Atom> &equality_atoms,
    const vector<bool> &nullary_positive_atoms, const vector<bool> &nullary_negated_atoms,
    const vector<Relation> &static_relations) :
    static_relations(&static_relations) {

    // Nullary atoms could be static, because the translator does not eliminate them.
    // Here, we have to treat them as non-static, because they are not present in static_relations
    // (nor in task.get_static_info()).
    // TODO: fix this in the translator and parser
    for (int i = 0; i < nullary_positive_atoms.size(); ++i) {
        if (nullary_positive_atoms[i]) {
            nullary_atoms.emplace_back(i, false);
        }
        if (nullary_negated_atoms[i]) {
            nullary_atoms.emplace_back(i, true);
        }
    }

    int join_step = 0;
    vector<int> first_step;  // join step at which each column in q.tuple_idx is added
    for (const Atom &atom : atoms) {
        const Relation &rel = static_relations[atom.get_predicate_symbol_idx()];

        bool ground = true;
        for (const Argument &arg : atom.get_arguments()) {
            if (!arg.is_constant()) {
                ground = false;
                break;
            }
        }
        if (ground) {
            if (!rel.tuples.empty()) {
                // static ground atom
                if (!static_ground_atom_satisfied(atom, rel)) {
                    statically_unsatisfiable = true;
                    return;
                } // if it is satisfied, discard the atom
            } else {
                // non-static ground atom are special filter atoms that are checked
                // before computing any joins
                ground_atoms.push_back(compile_filter_atom(atom, rel));
            }
            continue;
        }

        if (atom.is_negated()) {
            // all negated atoms are filter atoms
            filter_atoms.push_back(compile_filter_atom(atom, rel));
            continue;
        }

        // positive, non-ground atom: continue building q.tuple_idx and first_step
        SelectionPattern pattern = compile_selection_pattern(atom);
        bool new_vars = false;
        vector<int> before = tuple_idx;
        for (int var : pattern.vars) {
            if (!utils::contains(before, var)) {
                tuple_idx.push_back(var);
                first_step.push_back(join_step);
                new_vars = true;
            }
        }
        if (new_vars) {
            // atom contributes at least one new variable
            join_atoms.push_back(compile_join_atom(atom, rel, pattern));
            ++join_step;
        } else {
            // atom is used as a filter over the existing variables
            filter_atoms.push_back(compile_filter_atom(atom, rel));
        }
    }

    for (const Atom &atom : equality_atoms) {
        vector<Argument> args = atom.get_arguments();
        assert(args.size() == 2);
        if (args[0].is_constant() && args[1].is_constant()) {
            // ground equality atom
            if (!ground_eq_atom_satisfied(atom)) {
                statically_unsatisfiable = true;
                return;
            } // if it is satisfied, discard the atom
        } else {
            // non-ground equality atoms are always (static) filter atoms
            eq_filters.push_back(
                compile_filter_atom(atom, static_relations[atom.get_predicate_symbol_idx()]));
        }
    }

    // update arg_map and join_step for every filter atom, based on the final tuple_idx and first_step
    for (FilterAtom &atom : filter_atoms) {
        update_filter_atom(atom, tuple_idx, first_step);
    }
    for (FilterAtom &atom: eq_filters) {
        update_filter_atom(atom, tuple_idx, first_step);
    }

}

// TODO: for semi-naive evaluation, add a "Delta" argument
Table Query::evaluate(const vector<Relation> &relations, const vector<bool> &nullary_relations) const {

    if (statically_unsatisfiable) {
        return Table::EMPTY_TABLE();
    }

    // for nullary atoms, check if they are satisfied in nullary_data
    for (const auto [pred_idx, negated] : nullary_atoms) {
        if (nullary_relations[pred_idx] == negated) {
            return Table::EMPTY_TABLE();
        }
    }

    // handle ground atoms first via lookups to avoid joins with single-tuple relations
    // (these ground atoms cannot be static)
    for (const FilterAtom &atom : ground_atoms) {
        GroundAtom tuple;
        for (int const_idx : atom.arg_map) {
            tuple.push_back(-const_idx - 1);
        }
        const Relation &rel = relations[atom.predicate_idx];
        bool present = (rel.tuples.find(tuple) != rel.tuples.end());
        if (present == atom.negated) {
            return Table::EMPTY_TABLE();
        }
    }

    if (join_atoms.size() == 0) {
        // special case: no join atoms (i.e., a ground query)
        // -> return "unit" table with a single, empty tuple (not empty table)
        Table unit;
        unit.tuples.emplace_back();
        return unit;
    }

    vector<Table> tables;
    for (const JoinAtom &atom : join_atoms) {
        if (atom.is_static) {
            tables.push_back(atom.precompiled);
        } else {
            Table table = select_tuples(relations[atom.pattern.predicate_idx], atom.pattern);
            if (table.tuples.empty()) {
                return Table::EMPTY_TABLE();
            }
            tables.push_back(table);
        }
    }

    Table &working_table = tables[0];
    filter(working_table, 0, relations);
    filter_eq(working_table, 0, relations);

    for (int join_step = 1; join_step < tables.size(); ++join_step) {
        hash_join(working_table, tables[join_step]);
        filter(working_table, join_step, relations);
        filter_eq(working_table, join_step, relations);
        if (working_table.tuples.empty()) {
            return Table::EMPTY_TABLE();
        }
    }

    assert(working_table.tuple_index == tuple_idx);

    return working_table;
}

SelectionPattern Query::compile_selection_pattern(const Atom &a) {
    SelectionPattern pattern;
    pattern.predicate_idx = a.get_predicate_symbol_idx();
    int pos = 0;
    for (const Argument &arg : a.get_arguments()) {
        if (arg.is_constant()) {
            pattern.const_checks.emplace_back(pos, arg.get_index());
            continue;
        }
        auto it = find(pattern.vars.begin(), pattern.vars.end(), arg.get_index());
        if (it == pattern.vars.end()) {
            // new variable
            pattern.vars.push_back(arg.get_index());
            pattern.project.push_back(pos);
        } else {
            // duplicate variable
            pattern.eq_checks.emplace_back(pos, pattern.project[it - pattern.vars.begin()]);
        }
        ++pos;
    }
    return pattern;
}

Table Query::select_tuples(const Relation &rel, const SelectionPattern &pattern) {
    Table table;
    table.tuple_index = pattern.vars;
    for (const GroundAtom &t : rel.tuples) {
        bool ok = true;

        for (auto [pos, obj] : pattern.const_checks) {
            if (t[pos] != obj) {
                ok = false;
                break;
            }
        }
        if (!ok) continue;

        for (auto [pos, first] : pattern.eq_checks) {
            if (t[pos] != t[first]) {
                ok = false;
                break;
            }
        }
        if (!ok) continue;

        Table::tuple_t projected_tuple;
        projected_tuple.reserve(pattern.project.size());
        for (int pos : pattern.project) {
            projected_tuple.push_back(t[pos]);
        }
        table.tuples.push_back(std::move(projected_tuple));
    }
    return table;
}

JoinAtom Query::compile_join_atom(const Atom &atom, const Relation &rel, const SelectionPattern &pattern) {
    JoinAtom compiled_atom;
    compiled_atom.pattern = pattern;
    compiled_atom.is_static = !rel.tuples.empty();
    if (compiled_atom.is_static) {
        compiled_atom.precompiled = select_tuples(rel, compiled_atom.pattern);
    }
    return compiled_atom;
}

FilterAtom Query::compile_filter_atom(const Atom &atom, const Relation &rel) {
    FilterAtom compiled_filter;
    compiled_filter.predicate_idx = atom.get_predicate_symbol_idx();
    compiled_filter.negated = atom.is_negated();
    compiled_filter.is_static = !rel.tuples.empty();
    compiled_filter.arg_map.reserve(atom.get_arguments().size());
    for (const Argument &arg : atom.get_arguments()) {
        if (arg.is_constant()) {
            // constants get negative numbers, to distinguish them from variables
            compiled_filter.arg_map.push_back(-arg.get_index() - 1);
        } else {
            // at first, store the variable index in src
            // this will later be updated to the column index of the variable in q.tuple_idx,
            // once q.tuple_idx has been fully computed
            compiled_filter.arg_map.push_back(arg.get_index());
        }
    }
    return compiled_filter;
}

bool Query::static_ground_atom_satisfied(const Atom &atom, const Relation &rel) {
    GroundAtom tuple;
    for (const Argument &arg : atom.get_arguments()) {
        tuple.push_back(arg.get_index());
    }
    bool found = (rel.tuples.find(tuple) != rel.tuples.end());
    return found != atom.is_negated(); // atom is satisfied
}

bool Query::ground_eq_atom_satisfied(const Atom &atom) {
    bool equal = atom.get_arguments()[0].get_index() == atom.get_arguments()[1].get_index();
    return equal != atom.is_negated(); // atom is satisfied
}

void Query::update_filter_atom(FilterAtom &atom, const vector<int> &tuple_idx, const vector<int> &first_step) {
    for (int i = 0; i < atom.arg_map.size(); i++) {
        if (atom.arg_map[i] >= 0) {
            // if the argument is a variable, point instead to the column it comes from
            int var_idx = utils::index_of(tuple_idx, atom.arg_map[i]);
            assert(var_idx != -1);
            atom.arg_map[i] = var_idx;
            if (atom.join_step < first_step[var_idx]) {
                // the join_step is the first step at which all variables of the filter atom
                // are present in the join table
                atom.join_step = first_step[var_idx];
            }
        }
    }
}

void Query::filter(Table &working_table, int join_step, const vector<Relation> &relations) const {
    for (const FilterAtom &filter : filter_atoms) {
        if (filter.join_step != join_step) {
            // the filter has already been applied or cannot be applied yet
            continue;
        }
    
        const unordered_set<GroundAtom, TupleHash> &tuples =
            filter.is_static
            ? (*static_relations)[filter.predicate_idx].tuples
            : relations[filter.predicate_idx].tuples;

        vector<Table::tuple_t> newtuples;
        GroundAtom probe;
        probe.resize(filter.arg_map.size());
        for (const GroundAtom &t : working_table.tuples) {
            // construct probe tuple into filter relation
            for (size_t i = 0; i < filter.arg_map.size(); ++i) {
                if (filter.arg_map[i] >= 0) {
                    // variable -> look up corresponding column in working_table
                    probe[i] = t[filter.arg_map[i]];
                } else {
                    // constant -> decode into positive constant index
                    probe[i] = -filter.arg_map[i] - 1;
                }
            }
            bool present = (tuples.find(probe) != tuples.end());
            if (present != filter.negated) {
                newtuples.push_back(std::move(t));
            }
        }
        working_table.tuples = std::move(newtuples);
    }
}

void Query::filter_eq(Table &working_table, int join_step, const vector<Relation> &relations) const {
    for (const FilterAtom &filter : eq_filters) {
        if (filter.join_step != join_step) {
            // the filter has already been applied or cannot be applied yet
            continue;
        }
        
        // we can assume that the filter is not ground, since that case was handled during precompilation
        if (filter.arg_map[0] < 0 || filter.arg_map[1] < 0) {
            // one argument is a constant, the other a variable
            int const_idx = -1;
            int col_idx = -1;
            if (filter.arg_map[0] < 0) {
                const_idx = -filter.arg_map[0] - 1;
                col_idx = filter.arg_map[1];
            } else {
                const_idx = -filter.arg_map[1] - 1;
                col_idx = filter.arg_map[0];
            }
            vector<Table::tuple_t> newtuples;
            for (const GroundAtom &t : working_table.tuples) {
                bool equal = const_idx == t[col_idx];
                if (equal != filter.negated) {
                    newtuples.push_back(t);
                }
            }
            working_table.tuples = std::move(newtuples);
        } else {
            // both arguments are variables
            int col_idx1 = filter.arg_map[0];
            int col_idx2 = filter.arg_map[1];
            vector<Table::tuple_t> newtuples;
            for (const GroundAtom &t : working_table.tuples) {
                bool equal = t[col_idx1] == t[col_idx2];
                if (equal != filter.negated) {
                    newtuples.push_back(t);
                }
            }
            working_table.tuples = std::move(newtuples);
        }
    }
}
