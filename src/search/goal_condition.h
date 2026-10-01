#ifndef SEARCH_GOAL_CONDITION_H
#define SEARCH_GOAL_CONDITION_H

#include "structures.h"

#include <unordered_set>
#include <utility>
#include <vector>

/**
 * @brief Define a single atom contained in the goal condition.
 *
 * @var predicate: Index of the predicate symbol of the atom.
 * @var args: Object indices instantiating the atom. Stored as a GroundAtom so
 * it can be looked up directly in a relation's tuple set and reused as a
 * GroundAtom by the BFWS evaluators.
 * @var negated: Boolean value indicating whether the atom is negated in the
 * goal.
 * @var mko: Boolean value indicating whether the atom stands for an mko, i.e.
 * is to be evaluated w.r.t. the lowerbound rules instead of the state.
 *
 */
class AtomicGoal {
    int predicate;
    GroundAtom args;
    bool negated;
    bool mko;

public:
    AtomicGoal(int predicate, std::vector<int> args, bool negated, bool mko = false)
        : predicate(predicate), args(args.begin(), args.end()), negated(negated), mko(mko) {}

    int get_predicate_index() const {
        return predicate;
    }

    const GroundAtom &get_arguments() const {
        return args;
    }

    bool is_negated() const {
        return negated;
    }

    bool is_mko() const {
        return mko;
    }
};

/**
 * @brief Represent the goal condition of the task
 *
 * @var goal: Vector of ground atoms (AtomicGoal) in the goal condition.
 * @var positive_nullary_goals: Nullary predicates that appear in the goal.
 * @var negative_nullary_goals: Nullary predicates that appear negated in the
 * goal.
 * @var positive_nullary_mko_goals, negative_nullary_mko_goals: Likewise, for
 * the nullary atoms standing for an mko (see AtomicGoal::mko).
 *
 * @see AtomicGoal (goal_condition.h)
 *
 */
class GoalCondition {
public:
    std::vector<AtomicGoal> goal;
    std::unordered_set<int> positive_nullary_goals;
    std::unordered_set<int> negative_nullary_goals;
    std::unordered_set<int> positive_nullary_mko_goals;
    std::unordered_set<int> negative_nullary_mko_goals;

    GoalCondition() = default;

    explicit GoalCondition(std::vector<AtomicGoal> goal,
                           std::unordered_set<int> positive_nullary_goals,
                           std::unordered_set<int> negative_nullary_goals,
                           std::unordered_set<int> positive_nullary_mko_goals,
                           std::unordered_set<int> negative_nullary_mko_goals)
        : goal(std::move(goal)),
          positive_nullary_goals(std::move(positive_nullary_goals)),
          negative_nullary_goals(std::move(negative_nullary_goals)),
          positive_nullary_mko_goals(std::move(positive_nullary_mko_goals)),
          negative_nullary_mko_goals(std::move(negative_nullary_mko_goals)) {}
};

#endif // SEARCH_GOAL_CONDITION_H
