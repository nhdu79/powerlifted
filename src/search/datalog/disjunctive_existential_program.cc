
#include "disjunctive_existential_program.h"

#include "rules/generic_body.h"

#include "transformations/disjunctive_existential_normal_form.h"

using namespace datalog;
using namespace std;

DisjunctiveExistentialProgram::DisjunctiveExistentialProgram(vector<Predicate> &predicates, vector<Object> &objects, vector<std::unique_ptr<DisjunctiveExistentialRule>> rules) : rules(std::move(rules)) {
    for (auto p : predicates) {
        predicate_names.push_back(p.get_name());
    }
    for (auto o : objects) {
        object_names.push_back(o.get_name());
    }
}

void DisjunctiveExistentialProgram::output_rule(const DisjunctiveExistentialRule &rule) const {
    size_t number_effects = rule.get_effect().size();
    if (number_effects == 0) {
        cout << "⊥";
    }
    for (const auto &effect : rule.get_effect()) {
        --number_effects;
        output_atom(effect);
        if (number_effects > 0) {
            cout << ", ";
        }
    }
    size_t number_conditions = rule.get_conditions().size();
    if (number_conditions == 0) {
        cout << "." << endl;
    }
    else {
        cout << " :- ";
    }
    for (const auto &condition : rule.get_conditions()) {
        --number_conditions;
        output_atom(condition);
        if (number_conditions > 0) {
            cout << ", ";
        }
        else {
            cout << " [" << rule.get_body().get_type_name() << ", index:" << rule.get_index() << "]." << endl;
        }
    }
    rule.get_body().output_variable_table();
}

void DisjunctiveExistentialProgram::output_atom(const DatalogAtom &atom) const {
    std::cout << predicate_names[atom.get_predicate_index()];
    output_parameters(atom.get_arguments());
}

void DisjunctiveExistentialProgram::output_parameters(const Arguments& v) const {
    cout << '(';
    int number_params = v.size();
    for (auto arg : v) {
        if (arg.is_object()) {
            cout << object_names[arg.get_index()];
        } else {
            cout << "?v" << arg.get_index();
        }
        if (--number_params > 0) cout << ", ";
    }
    cout << ')';
}

const std::vector<Fact> &DisjunctiveExistentialProgram::get_facts() {
    return facts;
}

int DisjunctiveExistentialProgram::get_number_of_facts() const {
    return facts.size();
}
