#ifndef GROUNDER_RULES_PRODUCT_BODY_H
#define GROUNDER_RULES_PRODUCT_BODY_H

#include "rule_body_base.h"
#include "map_variable_position.h"

#include <limits>
#include <deque>

namespace datalog {

struct ProductDequeEntry {
    ProductDequeEntry(const Arguments& arguments, int i, int c)
    : arguments(arguments), index(i), cost(c) {}

    ProductDequeEntry(const Arguments& arguments, int i, int c, const std::vector<int>& a)
        : arguments(arguments), index(i), cost(c), achiever_atoms_indices(a) {}

    ProductDequeEntry(Arguments&& arguments, int i, int c, std::vector<int>&& a)
            : arguments(std::move(arguments)), index(i), cost(c), achiever_atoms_indices(std::move(a)) {}

    Arguments arguments;
    int index;
    int cost;
    std::vector<int> achiever_atoms_indices;
};

class ReachedFacts {
    // We do not use a vector of Facts because the Fact class is more complex than
    // what we need here for this use case.
    std::vector<Arguments> facts;
    std::vector<int> fact_indices;
    std::vector<int> costs;
    // Cheapest reached tuple, tracked incrementally so product() does not have to
    // re-scan every tuple on every call. Strict "<" keeps the first tuple that
    // reached the minimum cost, matching the old min-scan's tie-break exactly.
    int min_cost = std::numeric_limits<int>::max();
    int min_fact_index = -1;

public:
    ReachedFacts() = default;

    void push_back(const Fact &fact, int i) {
        facts.push_back(fact.get_arguments());
        fact_indices.push_back(fact.get_fact_index());
        costs.push_back(i);
        if (i < min_cost) {
            min_cost = i;
            min_fact_index = fact.get_fact_index();
        }
    }

    int get_min_cost() const { return min_cost; }

    int get_min_fact_index() const { return min_fact_index; }

    bool empty() const {
        return facts.empty();
    }

    std::vector<Arguments>::const_iterator begin() const {
        return facts.begin();
    }

    std::vector<Arguments>::const_iterator end() const {
        return facts.end();
    }

    int get_cost(int i) const {
        return costs[i];
    }

    std::vector<int> get_costs() const {
        return costs;
    }

    int get_fact_index(int fact) const {
        return fact_indices[fact];
    }

};

class ProductBody : public RuleBodyBase {
    std::vector<ReachedFacts> reached_facts_per_condition;
public:
    ProductBody(std::vector<DatalogAtom> c)
        : RuleBodyBase(std::move(c)),
          reached_facts_per_condition(conditions.size()) {
    }

    int get_type() const override {
        return PRODUCT;
    }

    void clean_up() override  {
        reached_facts_per_condition.clear();
        reached_facts_per_condition.resize(conditions.size());
    }

    void add_reached_fact_to_condition(const Fact &fact, int position, int cost) {
        reached_facts_per_condition[position].push_back(fact, cost);
    }

    ReachedFacts &get_reached_facts_of_condition(int i) {
        return reached_facts_per_condition[i];
    }

    const std::vector<ReachedFacts> &get_reached_facts_all_conditions() const {
        return reached_facts_per_condition;
    }

    int get_cost_reached_fact_in_position(int position_counter, int reached_fact_index) const {
        return reached_facts_per_condition[position_counter].get_cost(reached_fact_index);
    }

    int get_fact_index_reached_fact_in_position(int position_counter, int reached_fact_index) const {
        return reached_facts_per_condition[position_counter].get_fact_index(reached_fact_index);
    }

    std::string get_type_name() const override {
        return "ProductRule";
    }

    /*
    * In product rules, none of the free variables join and there might be
    * several atoms in the body.
    *
    * In practice, this means two scenarios:
    *
    * (1) the head is empty;
    * (2) every free variable in the body is also in the head
    *
    */
    // TODO: include option to not compute costs (for unweighted scenarios)? and not to compute achievers?
    template <typename C>
    void instantiate(Arguments new_arguments_persistent,
        MapVariablePosition variable_position,
        const Fact &fact,
        int position,
        int (*aggregation_function)(int, int),
        C construct_fact) {

        const auto& args = get_condition_arguments(position);

        // Verify that if there is a ground object in the condition of this atom,
        // then it matches the fact being expanded
        int c = 0;
        for (const auto& term : args) {
            if (term.is_object() and term.get_index()!=fact.argument(c).get_index()) {
                return;
            }
            ++c;
        }

        // Check that *all* other positions of the effect have at least one tuple
        add_reached_fact_to_condition(fact, position, fact.get_cost());
        const std::vector<ReachedFacts> &all_conditions = get_reached_facts_all_conditions();
        for (const ReachedFacts &v : all_conditions) {
            if (v.empty()) return;
        }

        // If there is one reachable ground atom for every condition and the head
        // is nullary or has no free variable, then simply trigger it. Only the
        // cheapest tuple of each condition matters here, and ReachedFacts tracks that
        // minimum incrementally, so this is O(#conditions) instead of re-scanning
        // (and copying) every reached tuple's costs on every call. The min-scan is
        // pointless for non-ground heads, so we skip it entirely in that case.
        if (variable_position.size() == 0) {
            int total_cost = 0;
            std::vector<int> nullary_head_achievers;
            nullary_head_achievers.reserve(all_conditions.size());
            for (const ReachedFacts &v : all_conditions) {
                nullary_head_achievers.push_back(v.get_min_fact_index());
                total_cost = aggregation_function(total_cost, v.get_min_cost());
            }
            // rule index and cost for achievers have to be filled in by the calling method
            construct_fact(new_arguments_persistent, 
                total_cost,
                Achievers(std::move(nullary_head_achievers), -1, 0));
            return;
        }

        // Second: start creating a base for the new effect atom based on the fact
        // that we are currently expanding

        int position_counter = 0;
        for (const auto& arg:args) {
            if (arg.is_object()) continue;
            int pos = variable_position.position_of(arg);
            if (pos!=-1) {
                new_arguments_persistent.set_term_to_object(pos,
                                                            fact.argument(position_counter).get_index());
            }
            position_counter++;
        }

        // Third: in this case, we just loop over the other conditions and its already
        // reached facts and instantiate all possibilities (i.e., cartesian product).
        // We do this using a queue
        std::deque<ProductDequeEntry> q;
        //deque<pair<Arguments, int>> q;
        q.emplace_back(new_arguments_persistent, 0, fact.get_cost());
        while (!q.empty()) {
            auto& next = q.front();

            if (next.index >= int(get_conditions().size())) {
                // rule index and cost for achievers have to be filled in by the calling method
                construct_fact(next.arguments, 
                        next.cost,
                        Achievers(next.achiever_atoms_indices, -1, 0));
            } else if (next.index==position) {
                // If it is the condition that we are currently reaching, we do not need
                // to consider the other tuples with this predicate
                next.achiever_atoms_indices.push_back(fact.get_fact_index());
                q.emplace_back(next.arguments, next.index + 1, next.cost, next.achiever_atoms_indices);
            } else {
                int vector_counter = 0;
                for (const auto &assignment : get_reached_facts_of_condition(next.index)) {
                    Arguments new_arguments = next.arguments; // start as a copy
                    size_t value_counter = 0;
                    for (const Term &arg : get_condition_arguments(next.index)) {
                        assert (value_counter < assignment.size());
                        int pos = variable_position.position_of(arg);
                        if (pos!=-1) {
                            new_arguments.set_term_to_object(pos,
                                                            assignment[value_counter].get_index());
                        }
                        ++value_counter;
                    }
                    std::vector<int> new_achievers = next.achiever_atoms_indices;
                    new_achievers.push_back(get_fact_index_reached_fact_in_position(next.index, vector_counter));
                    q.emplace_back(
                            std::move(new_arguments),
                            next.index + 1,
                            aggregation_function(next.cost, get_cost_reached_fact_in_position(next.index, vector_counter++)),
                            std::move(new_achievers));
                }
            }
            q.pop_front();
        }
    }

};

}

#endif //GROUNDER_RULES_PRODUCT_BODY_H