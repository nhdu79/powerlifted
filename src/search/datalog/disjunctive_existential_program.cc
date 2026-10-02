
#include "disjunctive_existential_program.h"

#include "rules/generic_body.h"

#include "transformations/disjunctive_existential_normal_form.h"

using namespace datalog;
using namespace std;

DisjunctiveExistentialProgram::DisjunctiveExistentialProgram(vector<Predicate> &predicates, vector<Object> &objects, vector<std::unique_ptr<DisjunctiveExistentialRule>> rules) : rules(std::move(rules)) {
    for (const auto &p : predicates) {
        predicate_names.push_back(p.get_name());
    }
    num_initial_predicates = predicates.size();
    for (const auto &o : objects) {
        object_names.push_back(o.get_name());
    }
    num_initial_objects = objects.size();
}

void DisjunctiveExistentialProgram::generate_skolem_constants() {
    for (auto &rule : rules) {
        if (rule->has_existential_variables()) {
            // collect all body variables
            std::vector<Term> condition_variables;
            for (const auto &condition: rule->get_conditions()) {
                for (const auto &t: condition.get_arguments()) {
                    if (!t.is_object() && !utils::contains(condition_variables, t)) {
                        condition_variables.emplace_back(t);
                    }
                }
            }

            // select head positions that do not contain a body variable and generate a unique constant for each variable
            int atom_idx = 0;
            for (const auto &effect_atom : rule->get_effect()) {
                int position = 0;
                std::unordered_map<Term, int> skolem_constants;
                for (const auto &t : effect_atom.get_arguments()) {
                    if (!t.is_object() && !utils::contains(condition_variables, t)) {
                        auto it = skolem_constants.find(t);
                        if (it == skolem_constants.end()) {
                            it = skolem_constants.emplace(t, create_new_skolem_constant()).first;
                        }
                        int &idx = it->second;
                        rule->set_skolem_mapping(atom_idx, position, idx);
                    }
                    ++position;
                }
                ++atom_idx;
            }
        }
    }
}

void DisjunctiveExistentialProgram::compute_distances_to_bottom() {
    // construct dependency graph with inverted edges, then use Dijkstra in the standard direction
    // index 0 stands for \bot, all others are shifted by 1
    Graph g(predicate_names.size() + 1);

    g.add_node(0);
    for (int i=0; i < predicate_names.size(); ++i) {
        g.add_node(i + 1);
    }

    for (const auto &rule : rules) {
        if (rule->get_effect().size() == 0) {
            for (const auto &cond : rule->get_conditions()) {
                g.add_edge(0, cond.get_predicate_index() + 1);
            }
        }
        for (const auto &eff : rule->get_effect()) {
            int idx = eff.get_predicate_index() + 1;
            for (const auto &cond : rule->get_conditions()) {
                g.add_edge(idx, cond.get_predicate_index() + 1);
            }
        }
    }

    std::vector<int> dist = g.dijkstra(0);

    // shift back the indices
    distances_to_bottom = std::vector<int>(dist.begin() + 1, dist.end());
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
            cout << " [" << rule.get_body().get_type_name() << ", index:" << rule.get_index() << "].";
        }
    }
    cout << " " << rule.get_map_orig_args() << (rule.has_existential_variables() ? " ∃" : "") << endl;
    // for (const auto &map : rule.get_map_orig_args()) {
    //     cout << map << endl;
    // }
    // rule.get_body().output_variable_table();
}

void DisjunctiveExistentialProgram::output_atom(const DatalogAtom &atom) const {
    if (atom.is_negated()) {
        std::cout << "not ";
    }
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

const std::vector<Fact> &DisjunctiveExistentialProgram::get_facts() const {
    return facts;
}

int DisjunctiveExistentialProgram::get_number_of_facts() const {
    return facts.size();
}
