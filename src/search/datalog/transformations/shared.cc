#include "shared.h"

// code shared between the normalization code of Datalog and DisjunctiveExistentialProgram


namespace datalog {

bool is_product_body(const std::vector<DatalogAtom> &conditions) {
    std::set<int> vars;
    for (const auto &condition : conditions) {
        for (const auto &arg : condition.get_arguments()) {
            if (!arg.is_object()) {
                if (vars.find(arg.get_index()) != vars.end()) return false;
                vars.insert(arg.get_index());
            }
        }
    }
    return true;
}

std::vector<DatalogAtom> select_conditions(std::vector<DatalogAtom> conditions, std::vector<int> indices) {
    std::vector<DatalogAtom> new_conditions;
    new_conditions.reserve(indices.size());
    for (int id : indices) {
        new_conditions.push_back(conditions[id]);
    }
    return new_conditions;
}

Arguments get_relevant_joining_arguments(const Arguments &head_args, const std::vector<DatalogAtom> &selected_conditions,
                                         const std::vector<DatalogAtom> &all_conditions, const std::vector<int> selected_ids,
                                         const bool disconnected) {
    std::vector<Term> joining_args;

    std::vector<Term> other_args;
    if (!disconnected) { // we have to consider which variables are shared with the rest of the conditions
        int counter = 0;
        for (const auto &c : all_conditions) {
            if (utils::contains(selected_ids, counter)) { // skip selected conditions
                ++counter;
                continue;
            }
            for (const auto &t : c.get_arguments()) { // don't bother removing duplicates, we only need it in utils::contains below
                other_args.emplace_back(t);
            }
            ++counter;
        }
    }

    for (const auto &c : selected_conditions) {
        for (const auto &t : c.get_arguments()) {
            // add all variables from selected_conditions to joining_args that are shared with head_args or other_args
            if (!t.is_object() && !utils::contains(joining_args, t) && (utils::contains(head_args, t) || utils::contains(other_args, t))) {
                joining_args.emplace_back(t);
            }
        }
    }

    return Arguments(std::move(joining_args));
}

VariableSource update_source_after_component_split(VariableSource source_original_rule,
                                                   const std::vector<int> &component,
                                                   int component_counter,
                                                   const VariableSource &source_new_split_rule) {// Update variable new_source of original rule
    int counter = 0;
    for (auto entry : source_original_rule.get_table()) {
        /*
         * TODO Change so it works for indirect entries as well. Currently, it only works for direct
         * queries, but it should work for both if we do a case splitting.
         */
        if (entry.first >= 0 or !utils::contains(component, source_original_rule.get_position_of_atom_in_same_body_rule(entry.first))) {
            counter++;
            continue;
        }

        int term = source_original_rule.get_term_from_table_entry_index(counter);
        int new_position_in_condition = component_counter;
        int new_position_in_indirect_table = -1;

        int entry_position_indirect_table = source_new_split_rule.get_table_entry_index_from_term(term);
        new_position_in_indirect_table = entry_position_indirect_table ;

        source_original_rule.update_ith_entry(counter, new_position_in_condition, new_position_in_indirect_table);
        counter++;
    }
    return source_original_rule;
}

std::vector<std::vector<int>> get_components(RuleBodyBase &body) {

    std::vector<int> variables = body.get_variables_in_body();

    const std::vector<DatalogAtom> &conditions = body.get_conditions();
    Graph g(conditions.size());

    int condition_counter = 0;
    for (const auto &condition : conditions) {
        if (condition.is_nullary() or condition.is_ground()) {
            g.add_node(condition_counter);
        } else {
            g.add_node(condition_counter);
            for (size_t j = condition_counter + 1; j < conditions.size(); ++j) {
                if (conditions[condition_counter].share_variables(conditions[j])) {
                    g.add_edge(condition_counter, j);
                    g.add_edge(j, condition_counter);
                }
            }
        }
        ++condition_counter;
    }

    return g.get_connected_components();

}

DatalogAtom update_source_table(RuleBodyBase &body, int atom, int idx) {
    VariableSource new_source = body.get_variable_source_object();
    int counter = 0;
    for (auto entry : new_source.get_table()) {
        if (new_source.get_position_of_atom_in_same_body_rule(entry.first) != atom) {
            counter++;
            continue;
        }
        if (entry.first >= 0)
            new_source.update_ith_entry(counter, idx, entry.second);
        else
            new_source.update_ith_entry(counter, (-1*idx)-1, entry.second);
        counter++;
    }
    body.update_variable_source_table(std::move(new_source));
    return body.get_conditions()[atom];
}

}
