#ifndef SEARCH_DATALOG_DEPROGRAM_H_
#define SEARCH_DATALOG_DEPROGRAM_H_

#include "rules/disjunctive_existential_rule.h"

#include <map>
#include <memory>
#include <vector>

namespace datalog {

class DisjunctiveExistentialProgram {

    std::vector<Fact> facts;
    std::vector<std::unique_ptr<DisjunctiveExistentialRule>> rules;
    std::vector<std::string> predicate_names;
    std::vector<std::string> object_names;

    int num_initial_predicates;
    int num_initial_objects;

    std::vector<int> distances_to_bottom;
    
    int get_next_auxiliary_predicate_idx() {
        return predicate_names.size();
    }

    int create_new_auxiliary_predicate() {
        int idx = get_next_auxiliary_predicate_idx();
        std::string predicate_name = "p$" + std::to_string(idx);
        predicate_names.push_back(predicate_name);
        return idx;
    }

    int get_next_skolem_constant_idx() {
        return object_names.size();
    }

    int create_new_skolem_constant() {
        int idx = get_next_skolem_constant_idx();
        std::string object_name = "c$" + std::to_string(idx);
        object_names.push_back(object_name);
        return idx;
    }

    void output_parameters(const Arguments& v) const;

    std::unique_ptr<DisjunctiveExistentialRule> convert_into_project_rule(const std::unique_ptr<DisjunctiveExistentialRule> &rule);

    std::unique_ptr<DisjunctiveExistentialRule> convert_into_product_rule(const std::unique_ptr<DisjunctiveExistentialRule> &rule);

    void convert_into_join_rules(std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &join_rules,
                                 std::unique_ptr<DisjunctiveExistentialRule> &rule);

    void split_rule(std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &join_rules,
                    std::unique_ptr<DisjunctiveExistentialRule> &rule, std::vector<int> body_ids);

    void split_into_connected_components(std::unique_ptr<DisjunctiveExistentialRule> &rule, std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &new_rules);

    DatalogAtom split_connected_component(std::unique_ptr<DisjunctiveExistentialRule> &original_rule, const std::vector<int> &component, std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &new_rules, int component_counter);

public:
    DisjunctiveExistentialProgram(std::vector<Predicate> &predicates, std::vector<Object> &objects, std::vector<std::unique_ptr<DisjunctiveExistentialRule>> rules);

    std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &get_rules() {
        return rules;
    }

    const std::vector<std::unique_ptr<DisjunctiveExistentialRule>> &get_rules() const {
        return rules;
    }

    const std::vector<int> get_distances_to_bottom() const {
        return distances_to_bottom;
    }

    void convert_rules_to_normal_form();

    void generate_skolem_constants();

    void compute_distances_to_bottom();

    void output_rule(const DisjunctiveExistentialRule &rule) const;

    void output_rules() const {
        for (const auto &rule : rules) output_rule(*rule);
    }

    const std::vector<Fact> &get_facts() const;

    const Fact &get_fact_by_index(int i) const {
        return facts[i];
    }

    DisjunctiveExistentialRule &get_rule_by_index(int index) {
        return *rules[index];
    }

    void insert_fact(const Fact &f) {
        facts.push_back(f);
    }

    void update_rule_indices() {
        for (size_t i = 0; i < rules.size(); ++i) {
            rules[i]->update_index(int(i));
        }
    }

    void output_fact(const Fact &f) const {
        output_atom(f);
    }

    void reset_facts() {
        facts.clear();
    }

    bool is_auxiliary_fact(const Fact &f) const {
        if (f.get_predicate_index() >= num_initial_predicates) {
            return true;
        }
        for (const Term &t : f.get_arguments()) {
            assert(t.is_object());
            if (t.get_index() >= num_initial_objects) {
                return true;
            }
        }
        return false;
    }

    void print_statistics() {
        std::cout << "Total number of facts: " << facts.size() << std::endl;
        std::cout << "Total number of rules: " << rules.size() << std::endl;
    }

    std::vector<int> extract_variable_instantiation_from_rule(int head) const;

    int get_number_of_facts() const;

    void output_atom(const DatalogAtom &atom) const;
};

}

#endif //SEARCH_DATALOG_DEPROGRAM_H_
