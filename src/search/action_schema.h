#ifndef SEARCH_ACTION_SCHEMA_H
#define SEARCH_ACTION_SCHEMA_H

#include "atom.h"
#include "conditional_effect.h"
#include "structures.h"

#include <string>
#include <utility>
#include <vector>

class ActionSchema {

    std::string name;
    int index;
    int cost;
    int num_external_parameters;
    std::vector<Parameter> parameters;
    std::vector<FreshVariable> fresh_variables;
    std::vector<Atom> precondition;
    std::vector<ConditionalEffect> effects;
    std::vector<Atom> equality_precondition;

    /*
     * Nullary predicates are represented as boolean vectors to simplify
     * other parts of the code (e.g., successor generation and action
     * applicability)
     */
    std::vector<bool> positive_nullary_precond;
    std::vector<bool> negative_nullary_precond;

public:
    explicit ActionSchema(std::string name,
                          int index,
                          int cost,
                          int num_external_parameters,
                          std::vector<Parameter> parameters,
                          std::vector<FreshVariable> fresh_variables,
                          std::vector<Atom> precondition,
                          std::vector<ConditionalEffect> effects,
                          std::vector<Atom> equality_precondition,
                          std::vector<bool> positive_nullary_precond,
                          std::vector<bool> negative_nullary_precond);

    const std::string &get_name() const {
        return name;
    }

    int get_index() const {
        return index;
    }

    int get_cost() const {
        return cost;
    }

    const std::vector<Parameter> &get_parameters() const {
        return parameters;
    }

    const std::vector<FreshVariable> &get_fresh_variables() const {
        return fresh_variables;
    }

    const std::vector<Atom> &get_precondition() const {
        return precondition;
    }


    // TODO GR: This is what we actually want but it won't work with the rest of
    // the code, so we (wrongly and inefficently) discard the effect
    // conditions.
    // const std::vector<ConditionalEffect> &get_effects() const {
    //    return effects;
    //}
    const std::vector<Atom> get_effects() const {
        std::vector<Atom> effs;
        for (auto e: effects) 
          effs.push_back(e.get_effect());
        return effs;
    }
   
    // TODO GR: This is a very expensive stub for no such effects.
    // We do not handle nullary effects specially anymore, so this method should
    // no longer be used and be removed.
    // I only added it so that the intermediate code compiles.
    const std::vector<bool> get_positive_nullary_effects() const {
        std::vector<bool> positive_nul_eff(positive_nullary_precond.size(), false);
        return positive_nul_eff;
    }
   
    // TODO GR: This is a very expensive stub for no such effects.
    // We do not handle nullary effects specially anymore, so this method should
    // no longer be used and be removed. 
    // I only added it so that the intermediate code compiles.
    const std::vector<bool> get_negative_nullary_effects() const {
        std::vector<bool> negative(positive_nullary_precond.size(), false);
        return negative;
    }

    const std::vector<Atom> &get_equality_precondition() const {
        return equality_precondition;
    }

    const std::vector<bool> &get_positive_nullary_precond() const {
        return positive_nullary_precond;
    }

    const std::vector<bool> &get_negative_nullary_precond() const {
        return negative_nullary_precond;
    }

    bool is_ground() const {
        return parameters.empty();
    }

    bool operator<(const ActionSchema& other) const {
        return index < other.index;
    }

    bool operator==(const ActionSchema& other) const {
        return index == other.index;
    }

    bool operator!=(const ActionSchema& other) const {
        return index != other.index;
    }
};

namespace std {
template <>
struct hash<ActionSchema> {
    size_t operator()(const ActionSchema &action) const {
        return hash<int>()(action.get_index());
    }
};
}  // namespace std

#endif //SEARCH_ACTION_SCHEMA_H
