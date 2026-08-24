#ifndef GROUNDER_RULES_PROJECT_BODY_H
#define GROUNDER_RULES_PROJECT_BODY_H

#include "rule_body_base.h"
#include "map_variable_position.h"

namespace datalog {

class ProjectBody : public RuleBodyBase {
public:
    using RuleBodyBase::RuleBodyBase;

    void clean_up() override {
    }
    int get_type() const override {
        return PROJECT;
    }

    const Arguments &get_condition_arguments() const {
        return conditions[0].get_arguments();
    }

    std::string get_type_name() const override {
        return "ProjectBody";
    }

    /*
    * Project a sequence of objects into another sequence. The head of the rule H
    * has free(H) <= free(B), where B is the rule body (condition).
    *
    * First, we map every (negative) index in the head to its given position.
    * Then, we loop over the single atom in the body and project the ones
    * that are in the head.  If there are constants in the head, we keep them
    * in the resulting fact when we create the mapping.
    *
    */

    template <typename C>
    void instantiate(Arguments new_arguments_persistent,
        MapVariablePosition variable_position,
        const Fact &fact,
        int position,
        int (*aggregation_function)(int, int),
        C construct_fact) {

        const Arguments &args = get_condition_arguments();
        for (size_t i = 0; i < args.size(); ++i) {
            const auto arg = args[i];
            if (args.is_object(i)) {
                // Constant instead of free var
                if (fact.argument(i)!=arg) {
                    // constants do not match!
                    return;
                }
            } else {
                int pos = variable_position.position_of(arg);
                if (pos!=-1) {
                    // Variable should NOT be projected away by this rule
                    new_arguments_persistent.set_term_to_object(pos, fact.argument(i).get_index());
                }
            }
        }

        // Return a vector with one single fact. The single-int Achievers ctor keeps
        // the achiever body in the inline small_vector (no heap-allocated vector).
        // rule index and cost for achievers have to be filled in by the calling method
        construct_fact(std::move(new_arguments_persistent), 
                fact.get_cost(),
                Achievers(fact.get_fact_index(), -1, 0));
    }
};

}

#endif //GROUNDER_RULES_PROJECT_BODY_H
