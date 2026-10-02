#ifndef SEARCH_TASK_H
#define SEARCH_TASK_H

#include "action_schema.h"
#include "goal_condition.h"
#include "object.h"
#include "predicate.h"
#include "states/state.h"

#include <cassert>
#include <memory>
#include <ostream>
#include <string>
#include <unordered_map>
#include <vector>

namespace datalog {
class DisjunctiveExistentialProgram;
}

/**
 * @brief Represents the task, with all its objects, goals, action schemas, etc.
 * Variable and function names should be self-explanatory.
 *
 * @attention The initial state and the static info have info for all predicates.
 * However, the static predicates will always be empty in any state and the fluents are
 * always empty in the static_info variable.
 *
 */

class Task {

    std::vector<ActionSchema> action_schemas;
    GoalCondition goal;
    bool object_creation = false;
    // The ontology's rules, read by the parser (both empty without an
    // ontology): the lowerbound (Clipper's rewriting) and the upperbound
    // (Table 1 rules, equality axioms and UNA rules).
    std::unique_ptr<datalog::DisjunctiveExistentialProgram> lowerbound_program;
    std::unique_ptr<datalog::DisjunctiveExistentialProgram> upperbound_program;

public:
    std::vector<Predicate> predicates;
    std::vector<Object> objects;
    std::vector<std::string> type_names;
    DBState initial_state;
    std::unordered_set<int> nullary_predicates;
    StaticInformation static_info;

    // Both out of line: datalog::DisjunctiveExistentialProgram is incomplete
    // here.
    Task(const std::string &domain_name, const std::string &task_name);

    ~Task();

    const std::string &get_domain_name() const { return domain_name; }

    const std::string &get_task_name() const { return task_name; }

    void add_type(const std::string &type_name);

    void add_predicate(std::string &name, int index, int arity,
                       bool static_predicate, std::vector<int> &types);

    void add_object(const std::string &name, int index,
                    const std::vector<int> &types);

    const std::string &get_object_name(int index) const {
        return objects[index].get_name();
    }

    void create_empty_initial_state(size_t number_predicates, int num_objects);

    void create_goal_condition(std::vector<AtomicGoal> goals,
                               std::unordered_set<int> nullary_goals,
                               std::unordered_set<int> negative_nullary_goals,
                               std::unordered_set<int> nullary_mko_goals,
                               std::unordered_set<int> negative_nullary_mko_goals);

    void initialize_action_schemas(const std::vector<ActionSchema> &action_list);

    const GoalCondition &get_goal() const {
        return goal;
    }

    const DBState &get_initial_state() const {
        return initial_state;
    }

    void dump_state(DBState s) const;

    void dump_goal();

    void flag_object_creation() {
        object_creation  = true;
    }

    bool has_object_creation() {
        return object_creation;
    }

    void set_lowerbound_program(std::unique_ptr<datalog::DisjunctiveExistentialProgram> program);

    void set_upperbound_program(std::unique_ptr<datalog::DisjunctiveExistentialProgram> program);

    datalog::DisjunctiveExistentialProgram &get_lowerbound_program() const {
        assert(lowerbound_program);
        return *lowerbound_program;
    }

    datalog::DisjunctiveExistentialProgram &get_upperbound_program() const {
        assert(upperbound_program);
        return *upperbound_program;
    }

    bool is_goal(const DBState &state) const;

    bool is_trivially_unsolvable() const;

    void set_static_info(StaticInformation &s) {
        static_info = std::move(s);
    }

    const StaticInformation& get_static_info() const {
        return static_info;
    }

    const std::vector<ActionSchema>& get_action_schemas() const {
        return action_schemas;
    }

    const ActionSchema& get_action_schema_by_index(int i) const {
        return action_schemas[i];
    }

    size_t get_number_action_schemas() const {
        return action_schemas.size();
    }

    const std::string get_predicate_name(int idx) const {
        return predicates[idx].get_name();
    }

  //! Return a vector R where R[i] contains all objects of type i (or of some subtype).
  std::vector<std::vector<int>> compute_object_index() const;

private:
    const std::string &domain_name;
    const std::string &task_name;
};

#endif // SEARCH_TASK_H
