#ifndef SEARCH_KONCLUDE_STATE_REASONER_H
#define SEARCH_KONCLUDE_STATE_REASONER_H

#include "../structures.h"
#include "../task.h"

#include "konclude_worker_client.h"

#include <set>
#include <string>
#include <tuple>
#include <unordered_map>
#include <vector>

/**
 * @brief One ontology fact: predicate(first) or predicate(first, second),
 * with object indices. second is -1 for a class assertion.
 */
struct KoncludeFact {
    int predicate;
    int first;
    int second;

    bool operator<(const KoncludeFact &other) const {
        return std::tie(predicate, first, second) <
               std::tie(other.predicate, other.first, other.second);
    }
    bool operator==(const KoncludeFact &other) const {
        return predicate == other.predicate && first == other.first &&
               second == other.second;
    }
};

using KoncludeFacts = std::set<KoncludeFact>;

struct KoncludeStateDiff {
    std::vector<KoncludeFact> tell;
    std::vector<KoncludeFact> retract;

    bool empty() const { return tell.empty() && retract.empty(); }
};

/**
 * @brief A conjunctive query for Konclude, as one SPARQL SELECT (one basic
 * graph pattern) per connected component.
 *
 * @details Konclude answers only the first component of a disconnected
 * pattern (e.g. { ?t a :Team . ?p a :Player }), leaving the other variables
 * unbound. So each component is its own query, and the answers are their
 * product. Each component selects the variables of it that are answer
 * variables (or any one variable, if it has none).
 */
struct KoncludeQuery {
    std::vector<std::string> components;
    // The answer variables (without "?"), in the order of the answer tuples;
    // each selected by exactly one component.
    std::vector<std::string> answer_variables;
};

/**
 * @brief Keeps Konclude's ABox equal to a search state and answers
 * conjunctive queries over it, w.r.t. the ontology.
 *
 * @details Konclude runs in a worker process (KoncludeWorkerClient, from
 * Konclude's Tools/KoncludeWorker/) that is restarted every restart_every
 * state changes, since Konclude leaks memory per state change. Each state
 * change sends only the diff to the facts Konclude holds.
 *
 * Typical use: set_state(s) for the state at hand, then answer(q) for a
 * query, or entailed(q, candidates) for the tuples the lowerbound and
 * upperbound disagree on.
 */
class KoncludeStateReasoner {
public:
    /**
     * @param vocabulary Only the predicates listed in it are sent to
     * Konclude; unary ones as class assertions, binary ones as object-property
     * assertions.
     * @param ontology_path An OWL 2 XML or functional-syntax file (Konclude's
     * embedded build reads no Turtle/RDF), e.g. the one the translator writes
     * (Task::get_ontology()). It must exist as long as the reasoner: the
     * worker reloads it on every restart.
     * @param worker_path The konclude_worker executable.
     * @param restart_every Restart the worker after this many state changes
     * (0: never).
     */
    KoncludeStateReasoner(const Task &task,
                          const OntologyVocabulary &vocabulary,
                          const std::string &ontology_path,
                          const std::string &worker_path,
                          int restart_every);

    // False if the vocabulary doesn't fit the task, the worker didn't start
    // or load the ontology, or a state change failed (Konclude's state is
    // then unknown); see last_error(). A failed query leaves it true.
    bool ok() const { return usable; }

    const std::string &last_error() const { return error; }

    // The ontology facts of state, including the task's static facts.
    KoncludeFacts facts_of(const DBState &state) const;

    static KoncludeStateDiff diff(const KoncludeFacts &from,
                                  const KoncludeFacts &to);

    // Makes Konclude's ABox the ontology facts of state (one state change,
    // none if nothing changed).
    bool set_state(const DBState &state);

    // Applies diff to the facts Konclude holds (one state change). For when
    // the caller knows the diff, e.g. from an action's effects.
    bool apply_diff(const KoncludeStateDiff &diff);

    const KoncludeFacts &current_facts() const { return told_facts; }

    // All certain answers of query over the current state, as object
    // indices in the order of query.answer_variables; sorted, no duplicates.
    bool answer(const KoncludeQuery &query, std::vector<GroundAtom> &answers);

    // The candidates (e.g. upperbound minus lowerbound answers) that are
    // certain answers of query, in the order given.
    bool entailed(const KoncludeQuery &query,
                  const std::vector<GroundAtom> &candidates,
                  std::vector<GroundAtom> &result);

    bool is_consistent(bool &consistent);

    // Diagnostics.
    int number_state_changes() const { return state_changes; }
    int number_worker_restarts() const { return client.restartCount(); }
    long worker_rss_kb() const { return client.workerRssKb(); }

private:
    // Sets last_error() and returns false.
    bool fail(const std::string &message);
    bool fail_unusable(const std::string &message);

    // The answers of one component query: per row, the object of each
    // selected variable (variables as listed in variables).
    bool answer_component(const std::string &sparql,
                          std::vector<std::string> &variables,
                          std::vector<std::vector<int>> &rows);

    // Per predicate index: its IRI, empty if it isn't in the vocabulary.
    std::vector<std::string> predicate_iris;
    std::vector<std::string> object_iris;
    std::unordered_map<std::string, int> object_by_iri;
    KoncludeFacts static_facts;
    KoncludeFacts told_facts;
    KoncludeWorkerClient client;
    int state_changes = 0;
    bool usable = true;
    std::string error;
};

#endif // SEARCH_KONCLUDE_STATE_REASONER_H
