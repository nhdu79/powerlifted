#include "c_chase.h"

using namespace std;

namespace datalog {


void CChase::add_fact(const DisjunctiveExistentialRule &rule, Fact &fact) {
    // we assume here that the fact has already been added to reached_atoms
    // (e.g. while checking whether it is already contained)
    fact.set_fact_index();
    program.insert_fact(fact);
    // cout << "Added fact ";
    // program.output_fact(fact);
    // cout << " due to rule ";
    // program.output_rule(rule);
    q.push(fact.get_fact_index());
}

void CChase::check_and_add_atom(const DisjunctiveExistentialRule &rule, int head_index, const Arguments &instantiation, bool ground) {

    // single atom, instantiation may be partial
    const DatalogAtom &atom = rule.get_effect()[head_index];
    int predicate_index = atom.get_predicate_index();

    bool found = true;
    Fact instantiated_atom(instantiation,
        predicate_index,
        atom.is_pred_symbol_new());
    // combines find() and insert() into one hash-iterate operation -- see weighted_grounder.cc
    // doesn't change reached_atoms if the new_fact is already present
    reached_atoms.lazy_emplace(instantiated_atom, [&](const auto &ctor) {
        // TODO: EQ: this uses a syntactic equality check, so we may add facts P(a,b) and P(a,c) even though =(b,c) holds
        ctor(instantiated_atom);
        found = false;
    });
    if (!found && !ground) {
        // restricted chase check with existentially quantified variables
        // TODO: here, it would also be useful to store the generated facts not a in single flat vector/hashmap,
        // but organized by predicates (as "tables") -- see also the "Datalog first" issue

        // cout << "Checking rule application: ";
        // program.output_rule(rule);
        // program.output_parameters(instantiation);
        // cout << endl;
        // program.output_atom(instantiated_atom);
        // cout << endl;

        // we cannot use reached_atoms for this loop, because we have just added instantiated_atom into it
        for (const Fact &known_fact : program.get_facts()) {
            if (known_fact.get_predicate_index() == predicate_index) {
                found = true;
                Arguments other_args = known_fact.get_arguments();
                int position = 0;
                for (const Term &t : instantiation) {
                    if (t.is_object()) {
                        // TODO: EQ: don't just check for syntactic equality here, but check the equality predicate =(x,y)
                        if (t.get_index() != other_args[position].get_index()) {
                            found = false;
                            break;
                        }
                    }
                    ++position;
                }
                if (found) {
                    // cout << "Found matching atom: ";
                    // program.output_atom(known_fact);
                    // cout << endl;
                    return;
                }
            }
        }

        // cout << "Didn't find matching atom" << endl;

        if (!found) {
            // replace remaining variables in instantiated_atom by Skolem constants
            int position = 0;
            for (const Term &t : instantiation) {
                if (!t.is_object()) {
                    int skolem_constant = rule.get_skolem_constant(head_index, position);
                    instantiated_atom.set_term_to_object(position, skolem_constant);
                }
                ++position;
            }

            // cout << "Fully instantiated atom:";
            // program.output_atom(instantiated_atom);
            // cout << endl;
        }
    }

    if (!found) {
        // add the new (possibly Skolemized) fact since the rule application is not blocked
        add_fact(rule, instantiated_atom);
    }
}

int CChase::choice_function(const std::vector<DatalogAtom> &effect, const std::vector<Fact> &instantiated_facts, std::vector<Fact> &negated_lower_bound) {
    // Instantiation should be ground due to the normal form (disjunctive rules have no existential variables).
    // Even if not, it shouldn't be problematic, but the negated lower bound does not provide much guidance in that case.

    // Prefer atoms with predicates that are "further away" from \bot in the dependency graph.
    // If a fact of the form \overline{P}(a) is derived by L_1, then try to avoid deriving P(a).
    int max_dist = std::numeric_limits<int>::min();
    int max_idx;
    int max_dist_nonneg = std::numeric_limits<int>::min();
    int max_idx_nonneg;
    int atom_idx = 0;

    // TODO: EQ: how to choose between multiple =(x,y) atoms?

    for (const DatalogAtom &atom : effect) {
        int predicate_idx = atom.get_predicate_index();
        int distance_to_bottom = program.get_distances_to_bottom()[predicate_idx];
        if (distance_to_bottom > max_dist) {
            max_dist = distance_to_bottom;
            max_idx = atom_idx;
        }

        if (!utils::contains(negated_lower_bound, instantiated_facts[atom_idx])) {
            if (distance_to_bottom > max_dist_nonneg) {
                max_dist_nonneg = distance_to_bottom;
                max_idx_nonneg = atom_idx;
            }
        }

        ++atom_idx;
    }

    if (max_dist_nonneg != std::numeric_limits<int>::min()) {
        // to avoid negated_lower_bound_facts if possible
        return max_idx_nonneg;
    }
    else {
        // otherwise, only minimize the distance to \bot
        return max_idx;
    }
}

const Arguments map_args(const Arguments &args, const vector<int> &map) {
    Arguments mapped_args;
    for (int pos : map) {
        mapped_args.push_back(args[pos]);
    }
    return mapped_args;
}

const Arguments select(const Arguments &args, int idx) {
    return args;
}

const Arguments select(const vector<Arguments> &mapped_args, int idx) {
    return mapped_args[idx];
}

template<typename A>
void CChase::check_and_add_disjunction(const DisjunctiveExistentialRule &rule, const A &instantiation, CChaseMode mode, std::vector<Fact> &negated_lower_bound) {

    // head contains multiple atoms, instantiation grounds all of them

    if (mode == SPLIT) { // U_2
        for (int atom_idx = 0; atom_idx < rule.get_effect().size(); ++atom_idx) {
            check_and_add_atom(rule, atom_idx, select(instantiation, atom_idx), true);
        }
    } else { // mode == CHOICE / U_3

        // restricted chase check
        std::vector<Fact> instantiated_facts;
        int atom_idx = 0;
        for (const DatalogAtom &eff: rule.get_effect()) {
            Fact instantiated_fact(select(instantiation, atom_idx),
                eff.get_predicate_index(),
                eff.is_pred_symbol_new());
            if (reached_atoms.contains(instantiated_fact)) {
                return;
            }
            instantiated_facts.push_back(instantiated_fact);
            ++atom_idx;
        }

        // add new fact according to choice function
        int chosen_atom_idx = choice_function(rule.get_effect(), instantiated_facts, negated_lower_bound);
        Fact chosen_fact = instantiated_facts[chosen_atom_idx];
        reached_atoms.insert(chosen_fact);
        add_fact(rule, chosen_fact);
    }

}

void CChase::create_rule_matcher() {
    // TODO: EQ: adapt this for =(x,y) and \neq(x,y) atoms?

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

// initialized by facts and negated facts (\overline{}) derived from a previous
// Datalog materialization to compute a lower bound via shifted Datalog rules
// (pre-computed positive facts are used to initialize the c-chase)
// (negated facts are used for the choice_function, assumes that the facts use
// the non-negated predicate indices)
bool CChase::chase(std::vector<Fact> &lower_bound, std::vector<Fact> &negated_lower_bound, CChaseMode mode, bool stop_on_bot) {

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

    for (Fact &f : lower_bound) {
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
        // TODO: EQ: "canonicalize" the fact to work only over representatives for =? -> maybe re-fetching (see below) already deals with this (if we canonicalize facts in-place)?
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
                // TODO: EQ: rewrite all "instantiate" implementations to take care of inequality atoms \neq(x,y)? (=(x,y) should not occur in bodies)
                conditions.instantiate(rule.get_effect_arguments(), rule.get_variable_position_map(), current_fact, position_in_the_body, aggregation_function,
                    [&](Arguments instantiation, int cost, Achievers ach) {

                        int number_of_effects = rule.get_effect().size();

                        if (number_of_effects == 0) {
                            bot_derived = true;
                            // cout << "Derived bottom due to rule ";
                            // program.output_rule(rule);
                        }
                        else { // at least one head atom
                            if (number_of_effects == 1) {
                                if (!rule.has_uniform_unique_effect_arguments()) {
                                    instantiation = map_args(instantiation, rule.get_map_orig_args()[0]);
                                }
                                check_and_add_atom(rule, 0, instantiation, !rule.has_existential_variables());
                            }
                            else { // multiple head atoms
                                if (!rule.has_uniform_unique_effect_arguments()) {
                                    vector<Arguments> mapped_args;
                                    for (std::vector<int> map : rule.get_map_orig_args()) {
                                        mapped_args.push_back(map_args(instantiation, map));
                                    }
                                    check_and_add_disjunction(rule, mapped_args, mode, negated_lower_bound);
                                } else {
                                    check_and_add_disjunction(rule, instantiation, mode, negated_lower_bound);
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

const std::vector<Fact> CChase::upper_bound_query(std::vector<Fact> &lower_bound, std::vector<Fact> &negated_lower_bound) {
    // first run U_2, since that needs to be done in any case
    chase(lower_bound, negated_lower_bound, SPLIT, false);
    std::vector<Fact> u2_answers;
    for (const Fact &f : program.get_facts()) {
        if (!program.is_auxiliary_fact(f)) {
            u2_answers.push_back(f);
        }
    }

    // then run U_3, can terminate early if \bot is derived
    if (chase(lower_bound, negated_lower_bound, CHOICE, true)) {
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

bool CChase::upper_bound_bottom_query(std::vector<Fact> &lower_bound, std::vector<Fact> &negated_lower_bound) {
    return chase(lower_bound, negated_lower_bound, SPLIT, true) && chase(lower_bound, negated_lower_bound, CHOICE, true);
}


}
