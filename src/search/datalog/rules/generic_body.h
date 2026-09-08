#ifndef SEARCH_DATALOG_RULES_GENERIC_BODY_H_
#define SEARCH_DATALOG_RULES_GENERIC_BODY_H_

#include "rule_body_base.h"

namespace datalog {

class GenericBody : public RuleBodyBase {

    // Rules created through the inherited constructor have no associated
    // action schema; -1 makes the annotation generators return no annotation.
    int schema_index = -1;

public:
    using RuleBodyBase::RuleBodyBase;

    GenericBody(std::vector<DatalogAtom> c, int schema_index)
      : RuleBodyBase(c), schema_index(schema_index) {

    }

    void clean_up() override {}

    int get_type() const override {
        return GENERIC;
    }

    int get_schema_index() const {
        return schema_index;
    }

    std::string get_type_name() const override {
        return "GenericBody";
    }

    template <typename C>
    void instantiate(Arguments new_arguments_persistent,
        MapVariablePosition variable_position,
        const Fact &fact,
        int position,
        int (*aggregation_function)(int, int),
        C construct_fact) {
    }

};

}


#endif //SEARCH_DATALOG_RULES_GENERIC_BODY_H_
