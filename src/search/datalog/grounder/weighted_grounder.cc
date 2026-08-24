#include "weighted_grounder.h"

#include "../datalog.h"

#include "../rules/rule_base.h"
#include "../rules/rule_body.h"

#include <limits>
#include <unordered_set>
#include <vector>

using namespace std;

namespace datalog {

/*
 * Exact inside (cheapest derivation) and outside (cheapest completion of a
 * goal derivation) costs of the predicate-level abstraction. The abstract
 * hypergraph has one node per predicate and one hyperedge per rule; both
 * fixpoints are Bellman-Ford style loops over the rules, which is plenty on a
 * graph this small (costs are monotone and integral, so they terminate).
 */
void WeightedGrounder::compute_abstract_costs(Datalog &datalog,
                                              const std::vector<Fact> &state_facts,
                                              int goal_predicate) {
    size_t num_preds = 0;
    for (const auto &rule : datalog.get_rules()) {
        num_preds = std::max(num_preds, size_t(rule->get_effect().get_predicate_index()) + 1);
        for (const DatalogAtom &b : rule->get_conditions()) {
            num_preds = std::max(num_preds, size_t(b.get_predicate_index()) + 1);
        }
    }
    for (const Fact &f : datalog.get_permanent_edb()) {
        num_preds = std::max(num_preds, size_t(f.get_predicate_index()) + 1);
    }
    for (const Fact &f : state_facts) {
        num_preds = std::max(num_preds, size_t(f.get_predicate_index()) + 1);
    }
    num_preds = std::max(num_preds, size_t(goal_predicate) + 1);

    abstract_inside.assign(num_preds, ABSTRACT_INF);
    abstract_outside.assign(num_preds, ABSTRACT_INF);

    // Base: the cheapest initial fact of each predicate. The persistent base
    // lives in the fact vector prefix; the improvable EDB facts and the state
    // facts arrive as arguments.
    for (int i = 0; i < num_base_facts; ++i) {
        const Fact &f = datalog.get_fact_by_index(i);
        int &c = abstract_inside[f.get_predicate_index()];
        c = std::min(c, f.get_cost());
    }
    for (const Fact &f : improvable_edb) {
        int &c = abstract_inside[f.get_predicate_index()];
        c = std::min(c, f.get_cost());
    }
    for (const Fact &f : state_facts) {
        int &c = abstract_inside[f.get_predicate_index()];
        c = std::min(c, f.get_cost());
    }

    const auto &rules = datalog.get_rules();
    bool changed = true;
    while (changed) {
        changed = false;
        for (const auto &rule : rules) {
            int body_agg = 0;
            bool infinite = false;
            for (const DatalogAtom &b : rule->get_conditions()) {
                int c = abstract_inside[b.get_predicate_index()];
                if (c >= ABSTRACT_INF) {
                    infinite = true;
                    break;
                }
                body_agg = aggregation_function(body_agg, c);
            }
            if (infinite) continue;
            int head_cost = body_agg + rule->get_weight();
            int &c = abstract_inside[rule->get_effect().get_predicate_index()];
            if (head_cost < c) {
                c = head_cost;
                changed = true;
            }
        }
    }

    abstract_outside[goal_predicate] = 0;
    changed = true;
    while (changed) {
        changed = false;
        for (const auto &rule : rules) {
            int out_head = abstract_outside[rule->get_effect().get_predicate_index()];
            if (out_head >= ABSTRACT_INF) continue;
            const std::vector<DatalogAtom> &body = rule->get_conditions();
            for (size_t i = 0; i < body.size(); ++i) {
                int others_agg = 0;
                bool infinite = false;
                for (size_t j = 0; j < body.size(); ++j) {
                    if (j == i) continue;
                    int c = abstract_inside[body[j].get_predicate_index()];
                    if (c >= ABSTRACT_INF) {
                        infinite = true;
                        break;
                    }
                    others_agg = aggregation_function(others_agg, c);
                }
                if (infinite) continue;
                // Rule weights add along a derivation chain under both
                // aggregations (cost(head) = w (+/max) bodies telescopes to
                // goal >= g(b) + sum of chain weights), so the outside cost
                // is a weight sum in both cases; sibling inside costs join it
                // only under the additive aggregation. The sibling scan above
                // still runs for h^max: a rule with an underivable body atom
                // (infinite inside) can never fire and propagates no demand.
                int candidate = out_head + rule->get_weight() +
                                (heuristic_type == H_ADD ? others_agg : 0);
                int &out = abstract_outside[body[i].get_predicate_index()];
                if (candidate < out) {
                    out = candidate;
                    changed = true;
                }
            }
        }
    }
}

int WeightedGrounder::ground(Datalog &datalog, std::vector<Fact> &state_facts, int goal_predicate) {
    std::vector<Fact> newfacts;

    queue_pushes = 0;
    atoms_produced = 0;

    if (!base_initialized) {
        // One-time split of the EDB into the persistent base and the
        // improvable remainder (see header comment).

        std::unordered_set<int> derived_preds;
        for (const auto &rule : datalog.get_rules()) {
            derived_preds.insert(rule->get_effect().get_predicate_index());
        }
        Fact::next_fact_index = 0;
        for (const Fact &f : datalog.get_permanent_edb()) {
            if (derived_preds.count(f.get_predicate_index())) {
                improvable_edb.push_back(f);
            }
            else {
                Fact f2 = f;
                f2.set_fact_index();
                datalog.insert_fact(f2);
            }
        }
        num_base_facts = Fact::next_fact_index;
        base_initialized = true;
    }

    // Reset of data structures: drop everything after the persistent base.
    datalog.truncate_facts(num_base_facts);
    Fact::next_fact_index = num_base_facts;
    reached_facts.clear();

    q.clear();
    best_achievers.clear();

    if (goal_predicate >= 0) {
        compute_abstract_costs(datalog, state_facts, goal_predicate);
    }
    else {
        abstract_outside.clear();
    }

    for (int i = 0; i < num_base_facts; ++i) {
        atoms_produced++;
        cumulative_atoms_produced++;
        int priority = priority_of(datalog.get_fact_by_index(i));
        if (priority >= ABSTRACT_INF) continue;
        q.push(priority, i);
        queue_pushes++;
        cumulative_queue_pushes++;
    }

    for (const Fact &f : improvable_edb) {
        Fact f2 = f;
        f2.set_fact_index();
        atoms_produced++;
        cumulative_atoms_produced++;
        datalog.insert_fact(f2);
        reached_facts.insert(f2);
        int priority = priority_of(f2);
        if (priority >= ABSTRACT_INF) continue;
        q.push(priority, f2.get_fact_index());
        queue_pushes++;
        cumulative_queue_pushes++;
    }

    for (Fact &f : state_facts) {
        f.set_fact_index();
        atoms_produced++;
        cumulative_atoms_produced++;
        datalog.insert_fact(f);
        reached_facts.insert(f);
        int priority = priority_of(f);
        if (priority >= ABSTRACT_INF) continue;
        q.push(priority, f.get_fact_index());
        queue_pushes++;
        cumulative_queue_pushes++;
    }

    // EDB + state facts now own the contiguous index range [0, num_initial_facts).
    num_initial_facts = Fact::next_fact_index;
    while (!q.empty()) {
        pair<int, int> queue_top = q.pop();
        int cost = queue_top.first;
        int top_fact_index = queue_top.second;
        // Access the popped fact by reference, not by copy (a copy clones its
        // arguments and achiever body on every pop). is_cheapest_path_to_achieve_fact()
        // below can push_back to — and thus reallocate — datalog's fact vector, so
        // we never hold this reference across it; we re-fetch by index (O(1))
        // inside the rule loop, where no fact is inserted during a single
        // project/join/product call.
        const Fact &popped_fact = datalog.get_fact_by_index(top_fact_index);
        if (popped_fact.get_predicate_index() == goal_predicate) {
            datalog.backchain_from_goal(popped_fact, num_initial_facts);
            return popped_fact.get_cost();
        }
        if (priority_of(popped_fact) < cost) {
            continue;
        }
        int predicate_index = popped_fact.get_predicate_index();
        for (const auto
                &m : rule_matcher.get_matched_rules(predicate_index)) {
            int rule_index = m.get_rule();
            int position_in_the_body = m.get_position();
            RuleBase &rule = datalog.get_rule_by_index(rule_index);

            assert(rule.get_body().get_type()==PROJECT || rule.get_body().get_type() == JOIN || rule.get_body().get_type() == PRODUCT);

            newfacts.clear();
            // Re-fetch: a previous iteration's is_cheapest_path may have grown
            // (and moved) the fact vector. Valid for this single rule application.
            const Fact &current_fact = datalog.get_fact_by_index(top_fact_index);
            rule.visit_body([&](auto& conditions) {
                conditions.instantiate(rule.get_effect_arguments(), rule.get_variable_position_map(), current_fact, position_in_the_body, aggregation_function,
                    [&](Arguments args, int cost, Achievers ach) {

                        ach.set_rule_index(rule.get_index());
                        ach.set_rule_cost(rule.get_weight());

                        newfacts.emplace_back(args,
                            rule.get_effect().get_predicate_index(),
                            cost + rule.get_weight(),
                            ach,
                            rule.get_effect().is_pred_symbol_new());
                    });
            });

            // Note: using for loop for performance reasons, this is a heavily used loop
            for (unsigned i=0, sz=newfacts.size(); i < sz; ++i) {
                auto& new_fact = newfacts[i];
                int id = is_cheapest_path_to_achieve_fact(new_fact, reached_facts, datalog);
                //datalog.output_atom(new_fact);
                //std::cout << std::endl << std::flush;
                if (id!=HAS_CHEAPER_PATH) {
                    // Duplicate detection above already recorded the fact;
                    // queue it only if it can still join a goal derivation.
                    int priority = priority_of(new_fact);
                    if (priority >= ABSTRACT_INF) continue;
                    q.push(priority, id);
                    queue_pushes++;
                    cumulative_queue_pushes++;
                }
            }
        }
    }
    return std::numeric_limits<int>::max();
}

int WeightedGrounder::is_cheapest_path_to_achieve_fact(Fact &new_fact,
                                                       phmap::flat_hash_set<Fact> &reached_facts,
                                                       Datalog &lp) {
    atoms_produced++;
    cumulative_atoms_produced++;
    // Fuse the membership probe and the insert into one hash+probe pass. The old
    // code did find() then, on a miss, a second insert() (two hashes of the whole
    // argument tuple per new fact). lazy_emplace() probes once and constructs the
    // stored copy only when the fact is new.
    bool inserted = false;
    const auto it = reached_facts.lazy_emplace(new_fact, [&](const auto &ctor) {
        new_fact.set_fact_index();
        ctor(new_fact);
        inserted = true;
    });
    if (inserted) {  // The fact wasn't reached yet
        lp.insert_fact(new_fact);
        return new_fact.get_fact_index();
    }
    if (new_fact.get_cost() < it->get_cost()) {
        const int existing_index = it->get_fact_index();
        new_fact.update_fact_index(existing_index);
        // Cost is neither hashed nor compared (Fact keys on predicate+args only),
        // and the stored entry's achiever body is never read back from
        // reached_facts (backchaining reads achievers from Datalog::facts), so
        // lower the cost in place instead of erase+reinsert (one hash saved).
        const_cast<Fact &>(*it).set_cost(new_fact.get_cost());
        lp.update_fact_cost(existing_index, new_fact.get_cost());
        return existing_index;
    }
    return HAS_CHEAPER_PATH;
}


void WeightedGrounder::create_rule_matcher(const Datalog &lp) {
    // Loop over rule conditions
    for (const auto &rule : lp.get_rules()) {
        int cont = 0;
        for (const auto &condition : rule->get_conditions()) {
            rule_matcher.insert(condition.get_predicate_index(),
                                rule->get_index(),
                                cont++);
        }
    }
}

}