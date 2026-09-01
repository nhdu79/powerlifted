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

// TODO: special handling of unsatisfiability query (\bot)?
// TODO: implement splitting: replace \bot by \bot_s  and convert disjunction to conjunction
//    (-> set of non-disjunctive existential rules)
//    -> implement (non-disjunctive) c-chase
// TODO: implement choice function and the disjunctive c-chase (also replace \bot by \bot_s, but keep disjunctions)

class DisjunctiveExistentialRule {
protected:
    std::vector<DatalogAtom> effect;
    bool bottom_rule;
    RuleBody body;
    int index;
    bool ground_effect;

    MapVariablePosition variable_position;

    static int next_index;

public:
    DisjunctiveExistentialRule(std::vector<DatalogAtom> eff, RuleBody b)
        : effect(std::move(eff)),
          body(std::move(b)),
          index(next_index++)
    {
        // variable map and ground status are computed from the first atom,
        // because all atoms have the same arguments
        ground_effect = true;
        bottom_rule = true;
        if (effect.size() > 0) {
            bottom_rule = false;
            variable_position.create_map(effect[0]);
            for (const auto &e : effect[0].get_arguments()) {
                if (!e.is_object()) {
                    ground_effect = false;
                }
            }
        }
    }

    DisjunctiveExistentialRule(DatalogAtom eff, RuleBody b)
        : DisjunctiveExistentialRule(std::vector<DatalogAtom>{eff}, b)
        { }

    virtual ~DisjunctiveExistentialRule() = default;

    bool head_is_ground() const { return ground_effect; }

    bool is_bottom_rule() const { return bottom_rule; }

    void update_index(int i) { index = i; }

    // TODO: check if this is needed
    void recreate_map_variable_position(const std::vector<DatalogAtom> &eff)
    {
        if (eff.size() > 0) {
            variable_position.create_map(eff[0]);
        } else {
            variable_position.clear();
        }
    }

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

    bool is_equivalent(const DisjunctiveExistentialRule &other) const
    {
        return (get_effect_arguments() == other.get_effect_arguments()) &&
               (get_conditions() == other.get_conditions());
    }

    // TODO: check if this is still needed
    void update_effect_arguments(std::vector<Term> &terms) {
        for (DatalogAtom atom : effect) {
            atom.update_arguments(terms);
        }
    }
};

}  // namespace datalog


#endif  // GROUNDER_DERULES_H
