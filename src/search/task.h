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
#include <utility>
#include <vector>

namespace datalog {
class DisjunctiveExistentialProgram;
}

/**
 * @brief Which task predicates are ontology classes and properties, and the
 * IRIs the ontology (and Konclude) knows them and the task's objects by.
 *
 * @details Unary predicates are classes, binary ones object properties; the
 * others (translator-generated ones like type@object, QUERY<i>, "=") aren't
 * listed.
 */
struct OntologyVocabulary {
    // Task predicate name -> IRI of its ontology class or object property.
    std::unordered_map<std::string, std::string> predicate_iris;
    // An object's IRI is object_iri_prefix + its name.
    std::string object_iri_prefix;
};

/**
 * @brief A conjunctive query for Konclude, as one SPARQL SELECT or ASK (one
 * basic graph pattern) per connected component.
 *
 * @details Konclude answers only the first component of a disconnected
 * pattern (e.g. { ?t a :Team . ?p a :Player }), leaving the other variables
 * unbound. So each component is its own query, and the answers are their
 * product. Each component selects the variables of it that are answer
 * variables, or is an ASK if it has none.
 */
struct KoncludeQuery {
    // An ASK component selects no variable: it only filters (the product
    // keeps its answers if it is entailed, and is empty otherwise).
    std::vector<std::string> components;
    // The answer variables (without "?"), in the order of the answer tuples;
    // each selected by exactly one component.
    std::vector<std::string> answer_variables;
};

/**
 * @brief The SPARQL query of an atomic mko, i.e. of an atom flagged mko, up to
 * the names of its variables: preconditions (and goal atoms) with the same
 * predicate and arguments, variables numbered by first occurrence, share it.
 */
struct KoncludeMkoQuery {
    int predicate;
    // Constants (object indices) and variables (numbered 0, 1, ... by first
    // occurrence); variable i is the answer variable x<i>.
    std::vector<Argument> arguments;
    // Conjunctive queries whose answers' union are the mko's (one, for now).
    std::vector<KoncludeQuery> cqs;
};

/**
 * @brief The ontology for the Konclude reasoner, as the translator wrote it
 * (the .lifted file's ONTOLOGY section): the normalized ontology in OWL
 * functional syntax at path, which must exist until the search ends (the
 * Konclude worker reloads it on every restart). path is empty if the
 * translator wrote none (no ontology, or no --konclude-ontology-file).
 */
struct TaskOntology {
    std::string path;
    OntologyVocabulary vocabulary;
    // The SPARQL query of each mko (an atom flagged mko) of the action
    // preconditions and the goal, translated once (the KONCLUDE-QUERIES
    // section, written for every task with an ontology, even when path is
    // empty); an mko without a translation isn't listed. QUERY<i> atoms, by
    // the predicate index of their QUERY<i>: its conjunctive queries, whose
    // answers' union are the query's, answer variable x<j> its argument j.
    std::unordered_map<int, std::vector<KoncludeQuery>> query_predicate_queries;
    // The other atoms flagged mko.
    std::vector<KoncludeMkoQuery> mko_queries;
};

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
    // Complement predicate index -> index of the predicate it complements:
    // the fresh complement concepts the lowerbound rules use (empty without
    // an ontology).
    std::unordered_map<int, int> lowerbound_complements;
    TaskOntology ontology;

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

    void set_lowerbound_complements(std::unordered_map<int, int> complements) {
        lowerbound_complements = std::move(complements);
    }

    const std::unordered_map<int, int> &get_lowerbound_complements() const {
        return lowerbound_complements;
    }

    void set_ontology(TaskOntology o) { ontology = std::move(o); }

    const TaskOntology &get_ontology() const { return ontology; }

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
