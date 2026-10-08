#include "../action.h"
#include "successor_generator.h"
#include "generic_negation_join_successor_generator.h"

#include "../action_schema.h"
#include "../database/hash_join.h"
#include "../database/table.h"
#include "../states/state.h"
#include "../task.h"
#include "../utils/collections.h"

#include <algorithm>
#include <cassert>
#include <vector>

using namespace std;

GenericNegationJoinSuccessorGenerator::GenericNegationJoinSuccessorGenerator(const Task &task)
    : static_information(task.get_static_info()), queries()
{
    queries.reserve(task.get_action_schemas().size());
    for (const ActionSchema &a: task.get_action_schemas()) {
        queries.emplace_back(
            a.get_precondition(),
            a.get_equality_precondition(),
            a.get_positive_nullary_precond(),
            a.get_negative_nullary_precond(),
            static_information.get_relations());
    }
}

DBState GenericNegationJoinSuccessorGenerator::generate_successor(
    const LiftedOperatorId &op,
    const ActionSchema& action,
    const DBState &state) {


    // ************************************************************************
    // TODO:
    // * Support conditional effects by checking effect conditions here
    // * For "forall" effects, use Query.evaluate - If we don't want to support
    //   "forall", we can skip this.
    // ************************************************************************


    added_atoms.clear();
    vector<bool> new_nullary_atoms(state.get_nullary_atoms());
    vector<Relation> new_relation(state.get_relations());
    apply_nullary_effects(action, new_nullary_atoms);

    if (action.is_ground()) {
        apply_ground_action_effects(action, new_relation, op.get_fresh_vars_mapping());
    }
    else {
        apply_lifted_action_effects(action, op.get_instantiation(),
                                    new_relation, op.get_fresh_vars_mapping());
    }


    // ************************************************************************
    // TODO:
    // * Compute extended state by applying all axioms
    // * Evaluate axiom bodies using Query.evaluate
    // * Remove old Relations for derived predicates first
    // ************************************************************************


    return DBState(std::move(new_relation), std::move(new_nullary_atoms), state.get_number_objects()+action.get_fresh_variables().size());
}

void GenericNegationJoinSuccessorGenerator::apply_nullary_effects(const ActionSchema &action,
                                               vector<bool> &new_nullary_atoms)
{
    /*
     * Loop over positive and negative nullary effects and apply them accordingly
     * to the state.
     */
    for (size_t i = 0; i < action.get_negative_nullary_effects().size(); ++i) {
        if (action.get_negative_nullary_effects()[i])
            new_nullary_atoms[i] = false;
    }
    for (size_t i = 0; i < action.get_positive_nullary_effects().size(); ++i) {
        if (action.get_positive_nullary_effects()[i]) {
            new_nullary_atoms[i] = true;
            add_to_added_atoms(i, GroundAtom());
        }
    }
}

void GenericNegationJoinSuccessorGenerator::apply_ground_action_effects(const ActionSchema &action,
                                                       vector<Relation> &new_relation,
                                                       std::unordered_map<int, int> new_objs)
{
    for (const Atom &eff : action.get_effects()) {
        GroundAtom ga;
        for (const Argument &a : eff.get_arguments()) {
            // Create ground atom for each effect given the instantiation
            if (a.is_constant())
                ga.push_back(a.get_index());
            else
                ga.push_back(new_objs.at(a.get_index()));
        }
        assert(eff.get_predicate_symbol_idx() == new_relation[eff.get_predicate_symbol_idx()].predicate_symbol);
        if (eff.is_negated()) {
            // If ground effect is negated, remove it from relation
            new_relation[eff.get_predicate_symbol_idx()].tuples.erase(ga);
        }
        else {
            // If ground effect is not in the state, we add it
            new_relation[eff.get_predicate_symbol_idx()].tuples.insert(ga);
            add_to_added_atoms(eff.get_predicate_symbol_idx(), ga);

        }
    }
}

void GenericNegationJoinSuccessorGenerator::apply_lifted_action_effects(const ActionSchema &action,
                                                       const vector<int> &tuple,
                                                       vector<Relation> &new_relation,
                                                       unordered_map<int, int> new_objs)
{
    for (const Atom &eff : action.get_effects()) {
        GroundAtom ga = tuple_to_atom(tuple, eff, new_objs);
        assert(eff.get_predicate_symbol_idx() == new_relation[eff.get_predicate_symbol_idx()].predicate_symbol);
        if (eff.is_negated()) {
            // Remove from relation
            new_relation[eff.get_predicate_symbol_idx()].tuples.erase(ga);
        }
        else {
            int predicate_symbol_idx = eff.get_predicate_symbol_idx();
            // tuples is an unordered_set, so insert() both adds the atom and
            // tells us (via .second) whether it was new — no need for a prior
            // O(n) linear std::find over the set.
            auto insertion = new_relation[predicate_symbol_idx].tuples.insert(ga);
            if (insertion.second) {
                // Ground atom was not already in the state: record it as added.
                add_to_added_atoms(predicate_symbol_idx, ga);
            }
        }
    }
}

std::vector<LiftedOperatorId> GenericNegationJoinSuccessorGenerator::get_applicable_actions(
        const ActionSchema &action, const DBState &state)
{   
    std::unordered_map<int, int> new_objs;
    int new_obj_idx = state.get_number_objects();
    for (const FreshVariable &arg : action.get_fresh_variables()) {
        new_objs[arg.get_index()] = new_obj_idx++;
    }

    std::vector<LiftedOperatorId> applicable;
    const Query &q = queries[action.get_index()];
    Table instantiations = q.evaluate(state.get_relations(), state.get_nullary_atoms());

    // reorder the tuples according to the original variable indices
    for (const GroundAtom &tuple : instantiations.tuples) {
        vector<int> ordered_tuple(instantiations.tuple_index.size());
        for (size_t i = 0; i < instantiations.tuple_index.size(); ++i) {
            ordered_tuple[instantiations.tuple_index[i]] = tuple[i];
        }
        applicable.emplace_back(action.get_index(), std::move(ordered_tuple), new_objs);
    }
    return applicable;
}

std::vector<LiftedOperatorId> GenericNegationJoinSuccessorGenerator::get_applicable_actions(
            const std::vector<ActionSchema> &actions, const DBState &state)
{
    std::vector<LiftedOperatorId> all_applicable_actions;

    for (const auto& action : actions) {
        const auto applicable_actions = get_applicable_actions(action, state);
        all_applicable_actions.reserve(all_applicable_actions.size() + applicable_actions.size());
        all_applicable_actions.insert(all_applicable_actions.end(), applicable_actions.cbegin(), applicable_actions.cend());
    }

    return all_applicable_actions;
}

/**
 *    This action generates the ground atom produced by an atomic effect given an instantiation of
 *    its parameters.
 *
 *    @details First, we rearrange the indices. Then, we create the atom based on whether the
 * argument is a constant or not. If it is, then we simply pass the constant value; otherwise we use
 *    the instantiation that we found.
 */
const GroundAtom GenericNegationJoinSuccessorGenerator::tuple_to_atom(const vector<int> &tuple,
                                                     const Atom &eff,
                                                     const unordered_map<int, int> &new_objs)
{
    GroundAtom ground_atom;
    ground_atom.reserve(eff.get_arguments().size());
    for (auto argument : eff.get_arguments()) {
        if (!argument.is_constant())
            if (!argument.is_fresh_var())
                ground_atom.push_back(tuple[argument.get_index()]);
            else {
                assert(new_objs.count(argument.get_index()) > 0);
                ground_atom.push_back(new_objs.at(argument.get_index()));
            }
        else
            ground_atom.push_back(argument.get_index());
    }

    // Sanity check: check that all positions of the tuple were initialized
    assert(find(ground_atom.begin(), ground_atom.end(), -1) == ground_atom.end());

    return ground_atom;
}
