#ifndef SEARCH_GENERIC_NEGATION_JOIN_SUCCESSOR_GENERATOR_H
#define SEARCH_GENERIC_NEGATION_JOIN_SUCCESSOR_GENERATOR_H

#include "successor_generator.h"

#include "../atom.h"
#include "../structures.h"
#include "../database/query.h"

#include <map>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <vector>

class PrecompiledActionData;
class Task;
class Table;

/**
 * Based on GenericJoinSuccessor, but supports negated atoms in conjunctions and
 * uses the generic Query class.
 */
class GenericNegationJoinSuccessorGenerator : public SuccessorGenerator {

// TODO: check whether all of these members are still needed after refactoring to use Query instead of PrecompiledActionData

public:
    explicit GenericNegationJoinSuccessorGenerator(const Task &task);

    DBState generate_successor(const LiftedOperatorId &op,
                               const ActionSchema& action,
                               const DBState &state) override;

    std::vector<LiftedOperatorId> get_applicable_actions(
            const ActionSchema &action, const DBState &state) override;

    std::vector<LiftedOperatorId> get_applicable_actions(
            const std::vector<ActionSchema> &action, const DBState &state) override;

    const GroundAtom tuple_to_atom(const std::vector<int> &tuple,
                                   const Atom &eff,
                                   const std::unordered_map<int, int> &new_objs);

    const std::vector<std::pair<int, GroundAtom>> &get_added_atoms() const override {
        return added_atoms;
    }

protected:
    const StaticInformation& static_information;

    // precompiled queries, indexed by schema index
    std::vector<Query> queries;

    void apply_nullary_effects(const ActionSchema &action,
                                      std::vector<bool> &new_nullary_atoms);

    void apply_ground_action_effects(const ActionSchema &action,
                                     std::vector<Relation> &new_relation,
                                     std::unordered_map<int, int> new_objs);

    void apply_lifted_action_effects(const ActionSchema &action,
                                     const std::vector<int> &tuple,
                                     std::vector<Relation> &new_relation,
                                     std::unordered_map<int, int> new_objs);

};

#endif //SEARCH_GENERIC_NEGATION_JOIN_SUCCESSOR_GENERATOR_H
