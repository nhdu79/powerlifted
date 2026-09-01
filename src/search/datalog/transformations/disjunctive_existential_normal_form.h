#ifndef SEARCH_DATALOG_TRANSFORMATIONS_DENF_H_
#define SEARCH_DATALOG_TRANSFORMATIONS_DENF_H_

#include "shared.h"
#include "greedy_join.h"

namespace datalog {

DatalogAtom DisjunctiveExistentialProgram::split_connected_component(std::unique_ptr<DisjunctiveExistentialRule> &original_rule, const std::vector<int> &component, std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &new_rules, int component_counter) {

    if (component.size() == 1) {
        return update_source_table(original_rule->get_body(), component[0], component_counter);
    }

    auto new_rule_conditions = select_conditions(original_rule->get_conditions(), component);

    int idx = create_new_auxiliary_predicate();

    Arguments new_args = get_relevant_joining_arguments(original_rule->get_effect_arguments(), new_rule_conditions, original_rule->get_conditions(), component, true);

    DatalogAtom new_atom(new_args, idx, true);
    std::unique_ptr<DisjunctiveExistentialRule> new_split_rule =
        std::make_unique<DisjunctiveExistentialRule>(new_atom, RuleBody(GenericBody(new_rule_conditions)));
    VariableSource new_source = update_source_after_component_split(original_rule->get_body().get_variable_source_object(),
                                                                    component,
                                                                    component_counter,
                                                                    new_split_rule->get_body().get_variable_source_object_by_ref());

    original_rule->get_body().update_variable_source_table(std::move(new_source));
    new_rules.push_back(std::move(new_split_rule));

    return new_atom;
}

void DisjunctiveExistentialProgram::split_into_connected_components(std::unique_ptr<DisjunctiveExistentialRule> &rule, std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &new_rules) {
    std::vector<std::vector<int>> components = get_components(rule->get_body());

    if (components.size() == 1) return;

    std::vector<DatalogAtom> new_rule_conditions;

    int component_counter = 0;
    for (const auto &component : components) {
        new_rule_conditions.push_back(split_connected_component(rule, component, new_rules, component_counter++));
    }

    rule->get_body().set_conditions(new_rule_conditions);

}

// new_split_rule should have a body of type JoinBody
void add_missing_entries_to_source_table(int position, std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &join_rules,
                                         const std::vector<DatalogAtom> &new_rule_conditions,
                                         std::unique_ptr<DisjunctiveExistentialRule> &new_split_rule,
                                         std::vector<int> &term_indices_in_new_args) {
    int idx_condition = new_rule_conditions[position].get_predicate_index();
    VariableSource source = new_split_rule->get_body().get_variable_source_object();
    for (const auto &join_rule : join_rules) {
        if ((join_rule->get_effect().size() == 1) && (join_rule->get_effect()[0].get_predicate_index() == idx_condition)) {
            const VariableSource source_join_rule = join_rule->get_body().get_variable_source_object_by_ref();
            for (size_t entry_table_counter = 0; entry_table_counter < source_join_rule.get_table().size(); ++entry_table_counter) {
                int entry_term = source_join_rule.get_term_from_table_entry_index(entry_table_counter);
                if (!utils::contains(term_indices_in_new_args, entry_term)) {
                    source.add_entry(entry_term, position, entry_table_counter);
                    term_indices_in_new_args.push_back(entry_term);
                }
            }
        }
    }
    new_split_rule->get_body().update_variable_source_table(std::move(source));
}

std::unique_ptr<DisjunctiveExistentialRule> DisjunctiveExistentialProgram::convert_into_project_rule(const std::unique_ptr<DisjunctiveExistentialRule> &rule) {
    VariableSource old_source = rule->get_body().get_variable_source_object();
    std::unique_ptr<DisjunctiveExistentialRule> project_rule =
        std::make_unique<DisjunctiveExistentialRule>(rule->get_effect(), RuleBody(ProjectBody(rule->get_conditions())));
    project_rule->get_body().update_variable_source_table(std::move(old_source));
    return project_rule;
}

std::unique_ptr<DisjunctiveExistentialRule> DisjunctiveExistentialProgram::convert_into_product_rule(const std::unique_ptr<DisjunctiveExistentialRule> &rule) {
    VariableSource old_source = rule->get_body().get_variable_source_object();
    std::unique_ptr<DisjunctiveExistentialRule> product_rule =
        std::make_unique<DisjunctiveExistentialRule>(rule->get_effect(), RuleBody(ProductBody(rule->get_conditions())));
    product_rule->get_body().update_variable_source_table(std::move(old_source));
    return product_rule;
}

void DisjunctiveExistentialProgram::split_rule(std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &join_rules,
        std::unique_ptr<DisjunctiveExistentialRule> &rule, std::vector<int> body_ids) {

    std::vector<DatalogAtom> new_rule_conditions = select_conditions(rule->get_conditions(), body_ids);

    int idx = create_new_auxiliary_predicate();

    Arguments new_args = get_relevant_joining_arguments(rule->get_effect_arguments(), new_rule_conditions, rule->get_conditions(), body_ids, false);

    DatalogAtom new_atom(new_args, idx, true);
    std::unique_ptr<DisjunctiveExistentialRule> new_split_rule =
        std::make_unique<DisjunctiveExistentialRule>(new_atom, RuleBody(JoinBody(new_rule_conditions)));

    // We need to get the entries of the variables in the tables of the conditions that were not
    // carried to the new split rule (because these variables have been projected out).
    // This part is unfortunately very inefficient....

    std::vector<int> term_indices_in_new_args;
    for (const auto &c : new_split_rule->get_conditions()) {
        for (const Term &t: c.get_arguments()) {
            if (t.is_object()) continue;
            term_indices_in_new_args.push_back(t.get_index());
        }
    }

    add_missing_entries_to_source_table(0, join_rules,
                                        new_rule_conditions,
                                        new_split_rule,
                                        term_indices_in_new_args);
    add_missing_entries_to_source_table(1, join_rules,
                                        new_rule_conditions,
                                        new_split_rule,
                                        term_indices_in_new_args);

    rule->get_body().update_conditions(new_atom,
                            new_rule_conditions,
                            new_split_rule->get_body().get_variable_source_object(),
                            std::move(body_ids));

    join_rules.push_back(std::move(new_split_rule));
}

void DisjunctiveExistentialProgram::convert_into_join_rules(
        std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &join_rules, std::unique_ptr<DisjunctiveExistentialRule> &rule) {
    
    while(rule->get_conditions().size() > 2) {
        JoinCost join_cost;
        int idx1 = std::numeric_limits<int>::max();
        int idx2 = std::numeric_limits<int>::max();
        for (int i = 0; i < rule->get_conditions().size() - 1; ++i) {
            for (int j = i+1; j < rule->get_conditions().size(); ++j) {
                JoinCost cost = compute_join_cost_fast_downward(rule->get_conditions()[i],
                                                                rule->get_conditions()[j]);
                if (cost < join_cost) {
                    join_cost = cost;
                    idx1 = i;
                    idx2 = j;
                }
            }
        }
        std::vector<int> indices = {idx1,idx2};
        std::sort(indices.begin(), indices.end());
        split_rule(join_rules, rule, indices);
    }
    std::unique_ptr<DisjunctiveExistentialRule> join_rule =
        std::make_unique<DisjunctiveExistentialRule>(rule->get_effect(), RuleBody(JoinBody(rule->get_conditions())));

    join_rule->get_body().update_variable_source_table(rule->get_body().get_variable_source_object());

    join_rules.emplace_back(std::move(join_rule));
}

void DisjunctiveExistentialProgram::convert_rules_to_normal_form() {
    std::vector<std::unique_ptr<DisjunctiveExistentialRule>> new_rules;

    /*
     * First step, split rules into connected components.
     */

    for (auto &rule : rules) {
        if (rule->get_conditions().size() > 1) {
            split_into_connected_components(rule, new_rules);
        }
    }
    for (auto &rule : new_rules) {
        rules.emplace_back(std::move(rule));
    }

    new_rules.clear();

    /*** TODO This is a quick solution to the problem with constant in join rules.
        Ideally we want to either check before the join if the constants match, or make the
        rule matcher also take into account the constants.
   */
    for (auto &rule : rules) {
        if (rule->get_conditions().size() > 1) {
            /*
             * Idea: Iterate over body of rule. If there's one atom with a constant, we call a function
             * that creates a new auxiliary atom projecting out this constant and also a rule with
             * the original atom in the body and the projected atom in the head.
             *
             * Then, we replace the old body atom in the original rule by the new one. We loop over
             * the VariableSource table, looking for entries that point to the original atom. If then
             * simply need to change the indices of the second element of the variable source table.
             */

            for (size_t i = 0; i < rule->get_conditions().size(); ++i) {
                auto &condition = rule->get_conditions()[i];
                bool project_away = false;
                std::vector<Term> remaining_args;
                for (size_t j = 0; j < condition.get_arguments().size() and !project_away; ++j) {
                    if (condition.argument(j).is_object()) {
                        project_away = true;
                    } else {
                        remaining_args.push_back(condition.argument(j));
                    }
                }
                if (project_away) {
                    int idx = create_new_auxiliary_predicate();
                    Arguments new_args(std::move(remaining_args));
                    DatalogAtom new_atom(new_args, idx, true);
                    std::unique_ptr<DisjunctiveExistentialRule> new_rule =
                        std::make_unique<DisjunctiveExistentialRule>(new_atom, RuleBody(ProjectBody{condition}));
                    rule->get_body().update_single_condition_and_variable_source_table(i, new_atom);
                    new_rules.emplace_back(std::move(new_rule));
                }
            }
        }
    }

    /*
     * This part is commented out because Fast Downward does not seem to do it.
     *  Project out variables that are not relevant to the join. This means variables that:
     * (i) do not join with any other atom in the rule condition; AND (important *AND* and not *OR*)
     * (ii) do not appear in the head of the rule.
     */

    /*for (auto &rule : rules) {
        if (rule->get_conditions().size() <= 1) continue;
        project_out_variables(rule, new_rules);
    }
    for (auto &rule : new_rules) {
        rules.emplace_back(std::move(rule));
    }
    new_rules.clear();*/


    /*
     * Last step, transform rules into product/project rules or split them into multiple join rules.
     */
    for (auto &rule : rules) {
        if (rule->get_conditions().size() == 1) {
            new_rules.push_back(convert_into_project_rule(rule));
        }
        else {
            if (is_product_body(rule->get_conditions())) {
                new_rules.push_back(convert_into_product_rule(rule));
            }
            else {
                std::vector<std::unique_ptr<DisjunctiveExistentialRule>> join_rules;
                convert_into_join_rules(join_rules, rule);
                for (auto &join_rule : join_rules) {
                    new_rules.push_back(std::move(join_rule));
                }
            }
        }
    }

    rules = std::move(new_rules);
}

}

#endif //SEARCH_DATALOG_TRANSFORMATIONS_DENF_H_
