#include "c_chase.h"

using namespace std;

namespace datalog {


void CChase::add_fact(const DisjunctiveExistentialRule &rule, int head_index, Arguments &instantiation) {
 
    DatalogAtom head_atom = rule.get_effect()[head_index];
    int predicate_index = head_atom.get_predicate_index();

    bool found = true;
    Fact instantiated_atom(instantiation,
        predicate_index,
        head_atom.is_pred_symbol_new());
    // combines find() and insert() into one hash-iterate operation -- see weighted_grounder.cc
    // doesn't change reached_facts if the new_fact is already present
    reached_atoms.lazy_emplace(instantiated_atom, [&](const auto &ctor) {
        ctor(instantiated_atom);
        found = false;
    });
    if (!found) {
        if (rule.has_existential_variables()) {
            // do restricted chase check (try to find an instance of instantiated_atom)
            // TODO: here, it would also be useful to store the generated facts not a single flat vector/hashmap,
            // but organized by predicates (as "tables") -- see also the "Datalog first" issue below
            for (const Fact &known_fact : program.get_facts()) {
                if (known_fact.get_predicate_index() == predicate_index) {
                    found = true;
                    Arguments other_args = known_fact.get_arguments();
                    int position = 0;
                    for (const Term &t : instantiation) {
                        if (t.is_object()) {
                            if (t.get_index() != other_args[position].get_index()) {
                                found = false;
                            }
                        }
                        ++position;
                    }
                    if (found) {
                        break;
                    }
                }
            }

            if (!found) { // we need to add the Skolemized instance (c-chase)
                // replace remaining variables in instantiated_atom by Skolem constants
                int position = 0;
                for (const Term &t : instantiation) {
                    if (!t.is_object()) {
                        int skolem_constant = rule.get_skolem_constant(head_index, position);
                        instantiated_atom.set_term_to_object(position, skolem_constant);
                    }
                    ++position;
                }
            }
        }
    }

    if (!found) { // add the new (Skolemized) fact since the rule application is not blocked
        instantiated_atom.set_fact_index();
        program.insert_fact(instantiated_atom);
        // cout << "Added fact ";
        // program.output_fact(instantiated_atom);
        // cout << " due to rule ";
        // program.output_rule(rule);
        q.push(instantiated_atom.get_fact_index());
    }
}

int CChase::choice_function(const std::vector<DatalogAtom> &effect, const Arguments &instantiation) {
    // Instantiation should be ground due to the normal form (disjunctive rules have no existential variables).
    // Prefer atoms with predicates that are "further away" from \bot in the dependency graph. -- program.get_distances_to_bottom()
    // If a fact of the form \overline{P}(a) is derived by L_1, then try to avoid deriving P(a). -- negated_lower_bound_facts
    int max_dist = std::numeric_limits<int>::min();
    int max_idx;
    int max_dist_nonneg = std::numeric_limits<int>::min();
    int max_idx_nonneg;
    int idx = 0;

    for (const DatalogAtom &atom : effect) {
        int predicate_idx = atom.get_predicate_index();
        int distance_to_bottom = program.get_distances_to_bottom()[predicate_idx];
        if (distance_to_bottom > max_dist) {
            max_dist = distance_to_bottom;
            max_idx = idx;
        }

        Fact f(instantiation, predicate_idx, atom.is_pred_symbol_new());
        if (!utils::contains(negated_lower_bound_facts, f)) {
            if (distance_to_bottom > max_dist_nonneg) {
                max_dist_nonneg = distance_to_bottom;
                max_idx_nonneg = idx;
            }
        }

        ++idx;
    }

    if (max_dist_nonneg != std::numeric_limits<int>::min()) {
        // to to avoid negated_lower_bound_facts if possible
        return max_idx_nonneg;
    }
    else {
        // otherwise, just minimize the distance to \bot
        return max_idx;
    }
}

void CChase::create_rule_matcher() {
    // Loop over rule conditions
    for (const auto &rule : program.get_rules()) {
        int cond_idx = 0;
        for (const auto &condition : rule->get_conditions()) {
            rule_matcher.insert(condition.get_predicate_index(),
                                rule->get_index(),
                                cond_idx++);
        }
    }
}

int aggregation_function(int a, int b) {
    return 0;
}

bool CChase::chase(std::vector<Fact> &state_facts, CChaseMode mode, bool stop_on_bot) {

    bool bot_derived = false;

    // TODO: Datalog first (needs complete rewriting of the processing logic to seminaive evaluation)

    // cout << endl;
    // cout << endl;
    // cout << "Running ";
    // if (mode == SPLIT) {
    //     cout << "U_2, ";
    // }
    // else {
    //     cout << "U_3, ";
    // }
    // if (!stop_on_bot) {
    //     cout << "not ";
    // }
    // cout << "stopping on bottom" << endl;

    queue_pushes = 0;
    atoms_produced = 0;

    Fact::next_fact_index = 0;
    program.reset_facts();
    reached_atoms.clear();

    // call clean_up() on all rule bodies, so that the internal datastructures used in
    // "instantiate" calls can be reused for the next chase computation
    for (auto &rule : program.get_rules()) {
        rule->get_body().clean_up();
    }

    assert(q.empty());

    for (Fact &f : state_facts) {
        f.set_fact_index();
        atoms_produced++;
        cumulative_atoms_produced++;
        program.insert_fact(f);
        reached_atoms.insert(f);
        q.push(f.get_fact_index());
        queue_pushes++;
        cumulative_queue_pushes++;
    }

    // state facts now own the contiguous index range [0, num_initial_facts).
    num_initial_facts = Fact::next_fact_index;
    while (!q.empty()) {
        int top_fact_index = q.front();
        q.pop();
        // Access the popped fact by reference, not by copy (a copy clones its
        // arguments and achiever body on every pop). add_fact()
        // below can push_back to — and thus reallocate — datalog's fact vector, so
        // we never hold this reference across it; we re-fetch by index (O(1))
        // inside the rule loop, where no fact is inserted during a single
        // project/join/product call.
        const Fact &popped_fact = program.get_fact_by_index(top_fact_index);
        // TODO: try to avoid processing facts multiple times -- implement proper seminaive evaluation? (also needed for "Datalog first" strategy)
        int predicate_index = popped_fact.get_predicate_index();
        for (const auto
                &m : rule_matcher.get_matched_rules(predicate_index)) {
            int rule_index = m.get_rule();
            int position_in_the_body = m.get_position();
            DisjunctiveExistentialRule &rule = program.get_rule_by_index(rule_index);

            assert(rule.get_body().get_type() == PROJECT || rule.get_body().get_type() == JOIN || rule.get_body().get_type() == PRODUCT);

            rule.visit_body([&](auto& conditions) {
                // Re-fetch current fact: a previous iteration may have grown (and moved) the fact vector.
                const Fact &current_fact = program.get_fact_by_index(top_fact_index);
                conditions.instantiate(rule.get_effect_arguments(), rule.get_variable_position_map(), current_fact, position_in_the_body, aggregation_function,
                    [&](Arguments args, int cost, Achievers ach) {

                        if (rule.get_effect().size() == 0) {
                            bot_derived = true;
                            // cout << "Derived bottom due to rule ";
                            // program.output_rule(rule);
                        }
                        else { // at least one head atom
                            if (rule.get_effect().size() == 1) {
                                add_fact(rule, 0, args);
                            } 
                            else { // multiple head atoms
                                if (mode == SPLIT) {
                                    for (int atom_idx = 0; atom_idx < rule.get_effect().size(); ++atom_idx) {
                                        add_fact(rule, atom_idx, args);
                                    }
                                } else { // mode == DISJUNCTIVE
                                    int chosen_atom_idx = choice_function(rule.get_effect(), args);
                                    add_fact(rule, chosen_atom_idx, args);
                                }
                            }
                        }
                        
                    });
            });
        }

        if (bot_derived && stop_on_bot) {
            std::queue<int> empty;
            std::swap(q, empty);
            break;
        }

    }

    return bot_derived;
}

const std::vector<Fact> CChase::upper_bound_query(std::vector<Fact> &state_facts) {
    // first run U_2, since that needs to be done in any case
    chase(state_facts, SPLIT, false);
    std::vector<Fact> u2_answers;
    for (const Fact &f : program.get_facts()) {
        if (!program.is_auxiliary_fact(f)) {
            u2_answers.push_back(f);
        }
    }

    // then run U_3, can terminate early if \bot is derived
    if (chase(state_facts, DISJUNCTIVE, true)) {
        // if \bot is derived, return only U_2's answers
        return u2_answers;
    }
    else {
        // if \bot is not derived, compute the intersection
        std::unordered_set<Fact> u2_answer_set(
            u2_answers.begin(),
            u2_answers.end());

        std::vector<Fact> answers;
        for (const Fact &f : program.get_facts()) {
            if (u2_answer_set.count(f)) {
                answers.push_back(f);
            }
        }
        return answers;
    }
}

bool CChase::upper_bound_bottom_query(std::vector<Fact> &state_facts) {
    return chase(state_facts, SPLIT, true) && chase(state_facts, DISJUNCTIVE, true);
}


}
