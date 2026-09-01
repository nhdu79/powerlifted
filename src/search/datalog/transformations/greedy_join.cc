
#include "greedy_join.h"

namespace datalog {

Arguments compute_joining_variables(const Arguments &head_args,
                                    const std::vector<DatalogAtom> &conditions,
                                    const DatalogAtom &atom1,
                                    const DatalogAtom &atom2)
{
    const Arguments &args1 = atom1.get_arguments();
    const Arguments &args2 = atom2.get_arguments();
    std::unordered_set<Term, std::hash<Term>> variables_in_both_atoms;
    for (const auto &t : args1) {
        if (not t.is_object()) {
            variables_in_both_atoms.insert(t);
        }
    }
    for (const auto &t : args2) {
        if (not t.is_object()) {
            variables_in_both_atoms.insert(t);
        }
    }

    std::unordered_set<Term, std::hash<Term>> important_vars_for_body_and_head;
    for (const auto &t : head_args) {
        if (not t.is_object())
            important_vars_for_body_and_head.insert(t);
    }
    for (const DatalogAtom &condition : conditions) {
        if (condition == atom1 or condition == atom2)
            continue;
        for (const auto &t : condition.get_arguments()) {
            important_vars_for_body_and_head.insert(t);
        }
    }

    std::vector<Term> joining_variables;
    for (auto i = variables_in_both_atoms.begin(); i != variables_in_both_atoms.end(); i++) {
        if (important_vars_for_body_and_head.find(*i) != important_vars_for_body_and_head.end())
            joining_variables.push_back(*i);
    }
    return Arguments(std::move(joining_variables));
}

JoinCost compute_join_cost_helmert2009(const Arguments &head_args,
                                       const std::vector<DatalogAtom> &conditions,
                                       const DatalogAtom &atom1,
                                       const DatalogAtom &atom2)
{
    std::unordered_set<Term, std::hash<Term>> free_variables_atom1;
    for (const auto &t : atom1.get_arguments()) {
        if (not t.is_object()) {
            free_variables_atom1.insert(t);
        }
    }

    std::unordered_set<Term, std::hash<Term>> free_variables_atom2;
    for (const auto &t : atom2.get_arguments()) {
        if (not t.is_object()) {
            free_variables_atom2.insert(t);
        }
    }

    int arity_atom1 = free_variables_atom1.size();
    int arity_atom2 = free_variables_atom2.size();

    int new_arity = compute_joining_variables(head_args, conditions, atom1, atom2).size();
    int max_arity = std::max(arity_atom1, arity_atom2);
    int min_arity = std::min(arity_atom1, arity_atom2);
    return JoinCost(new_arity, max_arity, min_arity, HELMERT_2009);
}

JoinCost compute_join_cost_fast_downward(const DatalogAtom &atom1,
                                         const DatalogAtom &atom2)
{
    std::unordered_set<int> free_variables_atom1;
    for (const auto &t : atom1.get_arguments()) {
        if (not t.is_object()) {
            free_variables_atom1.insert(t.get_index());
        }
    }

    std::unordered_set<int> free_variables_atom2;
    std::unordered_set<int> common_vars;
    for (const auto &t : atom2.get_arguments()) {
        if (not t.is_object()) {
            free_variables_atom2.insert(t.get_index());
            if (free_variables_atom1.count(t.get_index()) > 0)
                common_vars.insert(t.get_index());
        }
    }

    int arity_atom1 = free_variables_atom1.size();
    int arity_atom2 = free_variables_atom2.size();

    int max_arity = std::max(arity_atom1, arity_atom2);
    int min_arity = std::min(arity_atom1, arity_atom2);

    int common_vars_arity = common_vars.size();

    return JoinCost(common_vars_arity, max_arity, min_arity);
}

}  // namespace datalog
