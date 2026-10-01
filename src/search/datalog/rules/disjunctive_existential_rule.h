#ifndef GROUNDER_DERULES_H
#define GROUNDER_DERULES_H

#include "rule_body.h"
#include "map_variable_position.h"

#include "../datalog_atom.h"
#include "../datalog_fact.h"

#include "../annotations/annotation.h"

#include <memory>
#include <string>
#include <unordered_set>
#include <utility>

namespace datalog {


/*
 * DisjunctiveExistentialRule: Class implementing the rules of a disjunctive
 * existential program. The assumption is that all head atoms have the same Arguments.
 *
 */

class DisjunctiveExistentialRule {
protected:
    std::vector<DatalogAtom> effect;
    RuleBody body;
    int index;

    // in case there are multiple effect atoms with different variables, or a
    // variable occurs twice in the effect atom, we pre-compute a "merged"
    // argument vector that can be used in the "instantiate" methods
    Arguments merged_effect_arguments;
    // indicates whether merging took place or not
    bool uniform_unique_effect_arguments;
    // in that case, we then also need to map the original effect atoms back
    // from the merged effect arguments (after instantiation)
    std::vector<std::vector<int>> map_orig_args;
    // map every effect variable to its unique position in the merged effect arguments
    MapVariablePosition variable_position;
    // map every position of every head atom to a constant
    std::vector<std::vector<int>> skolem_mapping;
    bool existential_variables;

    static int next_index;

public:
    DisjunctiveExistentialRule(std::vector<DatalogAtom> eff, RuleBody b)
        : effect(std::move(eff)),
          body(std::move(b)),
          index(next_index++)
    {
        existential_variables = false;
        std::vector<Term> body_terms;
        for (const DatalogAtom &cond : ((RuleBodyBase &)body).get_conditions()) {
            for(const Term &t : cond.get_arguments()) {
                body_terms.emplace_back(t);
            }
        }
        map_orig_args.resize(effect.size());
        int eff_idx = 0;
        for (const DatalogAtom &eff: effect) {
            Arguments args = eff.get_arguments();
            for (const Term &t : args) {
                // populate merged_effect_arguments and map_orig_args
                int idx = utils::index_of(merged_effect_arguments, t);
                if (idx == -1) {
                    idx = merged_effect_arguments.size();
                    merged_effect_arguments.push_back(t);
                }
                map_orig_args[eff_idx].push_back(idx);

                // check for existential variables
                if (!t.is_object()) {
                    if (!utils::contains(body_terms, t)) {
                        existential_variables = true;
                    }
                }
            }
            ++eff_idx;
        }

        // check whether all effect atoms use the same variables with unique positions (if yes, we don't need to use map_orig_args later)
        uniform_unique_effect_arguments = true;
        for (const DatalogAtom &eff : effect) {
            if (eff.get_arguments() != merged_effect_arguments) {
                uniform_unique_effect_arguments = false;
                break;
            }
        }

        variable_position.create_map(merged_effect_arguments);

        if (existential_variables) {
            skolem_mapping.resize(effect.size());
            for (size_t atom_idx = 0; atom_idx < effect.size(); ++atom_idx) {
                skolem_mapping[atom_idx].resize(effect[atom_idx].get_arguments().size());
            }
        }
    }

    DisjunctiveExistentialRule(DatalogAtom eff, RuleBody b)
        : DisjunctiveExistentialRule(std::vector<DatalogAtom>{eff}, b)
        { }

    virtual ~DisjunctiveExistentialRule() = default;

    void update_index(int i) { index = i; }

    const std::vector<DatalogAtom> &get_effect() const { return effect; }

    template <typename F>
    decltype(auto) visit_body(F&& f) {
        return std::visit(std::forward<F>(f), body);
    }

    template <typename F>
    decltype(auto) visit_body(F&& f) const {
        return std::visit(std::forward<F>(f), body);
    }

    // needed to "convert" from the std::variant RuleBody to the abstract base class RuleBodyBase
    RuleBodyBase &get_body() {
      return visit_body([](RuleBodyBase &c) -> RuleBodyBase& { return c; });
    }
    const RuleBodyBase &get_body() const {
      return visit_body([](const RuleBodyBase &c) -> const RuleBodyBase& { return c; });
    }

    const std::vector<DatalogAtom> &get_conditions() const {
      return get_body().get_conditions();
    }

    int get_index() const { return index; }

    const Arguments &get_effect_arguments() const {
        return merged_effect_arguments;
    }

    const bool has_uniform_unique_effect_arguments() const {
        return uniform_unique_effect_arguments;
    }

    const std::vector<std::vector<int>> get_map_orig_args() const {
        return map_orig_args;
    }

    const MapVariablePosition get_variable_position_map() const { return variable_position; }

    bool has_existential_variables() const { return existential_variables; }

    int get_skolem_constant(int eff_idx, int position) const {
        return skolem_mapping[eff_idx][position];
    }

    void set_skolem_mapping(int eff_idx, int position, int object) {
        skolem_mapping[eff_idx][position] = object;
    }

};

}  // namespace datalog


#endif  // GROUNDER_DERULES_H
