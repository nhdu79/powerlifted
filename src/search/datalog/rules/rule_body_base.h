#ifndef GROUNDER_RULE_BODY_BASE_H
#define GROUNDER_RULE_BODY_BASE_H

#include "variable_source.h"

#include "../datalog_atom.h"
#include "../datalog_fact.h"

#include "../annotations/annotation.h"

#include <memory>
#include <string>
#include <unordered_set>
#include <utility>

namespace datalog {

/*
 * Rule bodies: Class implementing the rule bodies of the Datalog program.
 * Divided into three distinct types:
 *
 * Join bodies: Binary bodies where all vars in the head occur in the body
 * and all variables in the body but not in the head occur in both atoms.
 *
 * Product bodies: Special bodies for the rules which are not necessarily in
 * any format of the ones above. The goal rule always falls into this case.
 *
 * Project bodies: Unary bodies where all variables in the head occur in
 * the body.
 *
 */

enum RuleType { GENERIC, JOIN, PRODUCT, PROJECT };

class RuleBodyBase {
protected:
    std::vector<DatalogAtom> conditions;

    VariableSource variable_source;

    // TODO: check if this is still needed
    int get_position_of_atom_in_same_body_rule(int i) const
    {
        return variable_source.get_position_of_atom_in_same_body_rule(i);
    }


public:
    RuleBodyBase(std::vector<DatalogAtom> c)
        : conditions(std::move(c)),
          variable_source(conditions) {}

    RuleBodyBase(std::initializer_list<DatalogAtom> c)
        : conditions(c.begin(), c.end()),
          variable_source(conditions) {}

    virtual ~RuleBodyBase() = default;

    virtual void clean_up() = 0;

    const std::vector<DatalogAtom> &get_conditions() const { return conditions; }

    const Arguments &get_condition_arguments(int i) const { return conditions[i].get_arguments(); }

    std::vector<std::pair<int, int>> get_variable_source_table()
    {
        return variable_source.get_table();
    }

    void update_variable_source_table(VariableSource &&new_source)
    {
        variable_source = std::move(new_source);
    }

    VariableSource get_variable_source_object() { return variable_source; }

    const VariableSource &get_variable_source_object_by_ref() const { return variable_source; }

    void update_conditions(DatalogAtom new_atom,
                           const std::vector<DatalogAtom> &new_rule_conditions,
                           const VariableSource &variable_source_new_rule,
                           std::vector<size_t> &&body_ids);

    void update_single_condition_and_variable_source_table(size_t j, DatalogAtom atom);

    void set_conditions(std::vector<DatalogAtom> new_rule_conditions);

    void replace_single_condition(size_t j, DatalogAtom atom);

    void output_variable_table() const;

    std::vector<int> get_variables_in_body() const
    {
        std::vector<int> variables;
        for (const DatalogAtom &atom : conditions) {
            for (const Term &term : atom.get_arguments()) {
                if (!term.is_object()) {
                    variables.push_back(term.get_index());
                }
            }
        }
        return variables;
    }

    bool is_equivalent(const RuleBodyBase &other) const
    {
        return (conditions == other.get_conditions());
    }

    virtual int get_type() const = 0;

    // TODO: check where this is used
    virtual std::string get_type_name() const { return "RuleBodyBase"; }

    void set_specific_condition(size_t i, DatalogAtom atom);

    void update_condition_arguments(int i, std::vector<Term> &terms)
    {
        conditions[i].update_arguments(terms);
    }

};

}  // namespace datalog


#endif  // GROUNDER_RULE_BODY_BASE_H
