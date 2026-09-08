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
        if (effect.size() > 0) {
            // variable map is computed from the first atom, because all atoms have the same arguments
            variable_position.create_map(effect[0]);
            std::vector<Term> body_terms;
            for (const DatalogAtom &cond : ((RuleBodyBase &)body).get_conditions()) {
                for(const Term &t : cond.get_arguments()) {
                    body_terms.emplace_back(t);
                }
            }
            for (const Term &t : effect[0].get_arguments()) {
                if (!t.is_object()) {
                    if (!utils::contains(body_terms, t)) {
                        existential_variables = true;
                    }
                }
            }
        }
        skolem_mapping.resize(effect.size());
        for (size_t atom_idx = 0; atom_idx < effect.size(); ++atom_idx) {
            skolem_mapping[atom_idx].resize(effect[atom_idx].get_arguments().size());
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
        if (effect.size() > 0) {
            return effect[0].get_arguments();
        } else {
            static const Arguments empty{};
            return empty;
        }
    }

    const MapVariablePosition get_variable_position_map() const { return variable_position; }

    bool has_existential_variables() const { return existential_variables; }

    int get_skolem_constant(int atom_idx, int position) const {
        return skolem_mapping[atom_idx][position];
    }

    void set_skolem_mapping(int atom_idx, int position, int object) {
        skolem_mapping[atom_idx][position] = object;
    }

};

}  // namespace datalog


#endif  // GROUNDER_DERULES_H
