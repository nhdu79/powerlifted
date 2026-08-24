#ifndef SEARCH_DATALOG_TRANSFORMATIONS_ACTION_PREDICATE_REMOVAL_H_
#define SEARCH_DATALOG_TRANSFORMATIONS_ACTION_PREDICATE_REMOVAL_H_

#include "../datalog.h"

#include "../rules/rule_base.h"

namespace  datalog {

void Datalog::remove_action_predicates(AnnotationGenerator &annotation_generator, const Task &task) {
    std::vector<std::unique_ptr<RuleBase>> new_rules;

    for (const auto &action_rule : rules) {
        if (action_rule->get_effect().is_pred_symbol_new()) {
            // At this point, a new predicate symbol *must be* an action predicate
            int idx = action_rule->get_effect().get_predicate_index();
            RuleBase *action_rule_base = dynamic_cast<RuleBase *>(action_rule.get());
            for (auto &effect_rule : rules) {
                if (effect_rule->get_conditions().size() != 1)
                    continue; // Not effect rule
                if (effect_rule->get_conditions()[0].get_predicate_index() == idx) {
                    int schema_index = ((GenericBody&)action_rule_base->get_body()).get_schema_index();
                    std::unique_ptr<Annotation> ann = annotation_generator(schema_index, task);
                    std::unique_ptr<RuleBase> new_rule = std::make_unique<RuleBase>(action_rule->get_weight(),
                                                                                       effect_rule->get_effect(),
                                                                                       GenericBody{action_rule->get_conditions(), schema_index},
                                                                                       std::move(ann));
                    new_rule->get_body().update_variable_source_table(action_rule->get_body().get_variable_source_object());
                    new_rules.emplace_back(std::move(new_rule));
                }
            }
        }
    }

    rules = std::move(new_rules);
}
}

#endif //SEARCH_DATALOG_TRANSFORMATIONS_ACTION_PREDICATE_REMOVAL_H_
