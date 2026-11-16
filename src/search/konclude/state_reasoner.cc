#include "state_reasoner.h"

#include "../task.h"

#include <algorithm>
#include <unordered_set>

using namespace std;

namespace {

bool ground_atom_less(const GroundAtom &a, const GroundAtom &b)
{ return lexicographical_compare(a.begin(), a.end(), b.begin(), b.end()); }

void collect_facts(const DBState &state, const vector<string> &predicate_iris, KoncludeFacts &facts)
{
    for (const Relation &relation : state.get_relations()) {
        int predicate = relation.predicate_symbol;
        if (predicate < 0 || predicate >= int(predicate_iris.size()) ||
            predicate_iris[predicate].empty()) {
            continue;
        }
        for (const GroundAtom &tuple : relation.tuples) {
            facts.insert({predicate, tuple[0], tuple.size() == 2 ? tuple[1] : -1});
        }
    }
}

}  // namespace

KoncludeStateReasoner::KoncludeStateReasoner(const Task &task,
                                             const OntologyVocabulary &vocabulary,
                                             const string &ontology_path,
                                             const string &worker_path,
                                             int restart_every)
    : predicate_iris(task.predicates.size()), client(worker_path, restart_every)
{
    unordered_set<string> mapped;
    for (const Predicate &predicate : task.predicates) {
        auto it = vocabulary.predicate_iris.find(predicate.get_name());
        if (it == vocabulary.predicate_iris.end()) {
            continue;
        }
        if (predicate.getArity() != 1 && predicate.getArity() != 2) {
            fail_unusable("predicate " + predicate.get_name() + " has arity " +
                          to_string(predicate.getArity()) +
                          "; only unary and binary predicates can be ontology facts");
            return;
        }
        predicate_iris[predicate.get_index()] = it->second;
        mapped.insert(predicate.get_name());
    }
    for (const auto &entry : vocabulary.predicate_iris) {
        if (!mapped.count(entry.first)) {
            fail_unusable("the vocabulary names predicate " + entry.first +
                          ", which the task doesn't have");
            return;
        }
    }
    for (const Object &object : task.objects) {
        object_by_iri[vocabulary.object_iri_prefix + object.get_name()] = object.get_index();
    }
    object_iris.resize(task.objects.size());
    for (const auto &entry : object_by_iri) {
        object_iris[entry.second] = entry.first;
    }
    collect_facts(task.get_static_info(), predicate_iris, static_facts);

    if (!client.ok()) {
        fail_unusable(string("starting the Konclude worker failed: ") + client.lastError());
        return;
    }
    if (!client.loadOntology(ontology_path)) {
        fail_unusable("loading " + ontology_path + " failed: " + client.lastError());
    }
}

bool KoncludeStateReasoner::fail(const string &message)
{
    error = message;
    return false;
}

bool KoncludeStateReasoner::fail_unusable(const string &message)
{
    usable = false;
    return fail(message);
}

KoncludeFacts KoncludeStateReasoner::facts_of(const DBState &state) const
{
    KoncludeFacts facts = static_facts;
    collect_facts(state, predicate_iris, facts);
    return facts;
}

KoncludeStateDiff KoncludeStateReasoner::diff(const KoncludeFacts &from, const KoncludeFacts &to)
{
    KoncludeStateDiff result;
    set_difference(to.begin(), to.end(), from.begin(), from.end(), back_inserter(result.tell));
    set_difference(from.begin(), from.end(), to.begin(), to.end(), back_inserter(result.retract));
    return result;
}

bool KoncludeStateReasoner::set_state(const DBState &state)
{ return apply_diff(diff(told_facts, facts_of(state))); }

bool KoncludeStateReasoner::apply_diff(const KoncludeStateDiff &diff)
{
    if (!ok()) {
        return false;
    }
    if (diff.empty()) {
        return true;
    }
    // The IRIs point into predicate_iris and object_iris, which outlive the
    // call.
    vector<KoncludeClassAssertion> tell_class, retract_class;
    vector<KoncludeObjectPropertyAssertion> tell_property, retract_property;
    auto add = [this](const KoncludeFact &fact,
                      vector<KoncludeClassAssertion> &classes,
                      vector<KoncludeObjectPropertyAssertion> &properties) {
        const string &predicate = predicate_iris[fact.predicate];
        if (fact.second < 0) {
            classes.push_back({object_iris[fact.first].c_str(), predicate.c_str()});
        }
        else {
            properties.push_back({object_iris[fact.first].c_str(),
                                  predicate.c_str(),
                                  object_iris[fact.second].c_str()});
        }
    };
    for (const KoncludeFact &fact : diff.tell) {
        add(fact, tell_class, tell_property);
    }
    for (const KoncludeFact &fact : diff.retract) {
        add(fact, retract_class, retract_property);
    }
    if (!client.tellAndRetractAssertions(
            tell_class, retract_class, tell_property, retract_property)) {
        return fail_unusable(string("state change failed: ") + client.lastError());
    }
    for (const KoncludeFact &fact : diff.retract) {
        told_facts.erase(fact);
    }
    told_facts.insert(diff.tell.begin(), diff.tell.end());
    ++state_changes;
    return true;
}

bool KoncludeStateReasoner::answer_component(const string &sparql,
                                             vector<string> &variables,
                                             vector<vector<int>> &rows)
{
    variables.clear();
    rows.clear();
    if (!client.query(sparql)) {
        return fail(string("query failed: ") + client.lastError());
    }
    if (client.resultBoolean() >= 0) {
        // An ASK: no variables, and the empty row if entailed.
        if (client.resultBoolean() == 1) {
            rows.emplace_back();
        }
        return true;
    }
    for (int i = 0; i < client.resultVariableCount(); ++i) {
        variables.push_back(client.resultVariableName(i));
    }
    for (int row = 0; row < client.resultRowCount(); ++row) {
        vector<int> objects;
        for (size_t column = 0; column < variables.size(); ++column) {
            const char *binding = client.resultBinding(row, int(column));
            if (!binding || !*binding) {
                return fail("Konclude left ?" + variables[column] +
                            " unbound (is the query's pattern connected?): " + sparql);
            }
            auto it = object_by_iri.find(binding);
            if (it == object_by_iri.end()) {
                // Not a task object: no answer over the task's objects.
                break;
            }
            objects.push_back(it->second);
        }
        if (objects.size() == variables.size()) {
            rows.push_back(move(objects));
        }
    }
    return true;
}

bool KoncludeStateReasoner::answer(const KoncludeQuery &query, vector<GroundAtom> &answers)
{
    answers.clear();
    if (!ok()) {
        return false;
    }
    const vector<string> &answer_variables = query.answer_variables;
    // The product of the components' answers so far, over the answer
    // variables (-1: bound by a later component).
    set<vector<int>> tuples = {vector<int>(answer_variables.size(), -1)};
    vector<bool> bound(answer_variables.size(), false);
    for (const string &component : query.components) {
        vector<string> variables;
        vector<vector<int>> rows;
        if (!answer_component(component, variables, rows)) {
            return false;
        }
        // Position of each selected variable among the answer variables.
        vector<int> positions;
        for (const string &variable : variables) {
            auto it = find(answer_variables.begin(), answer_variables.end(), variable);
            int position = it == answer_variables.end() ? -1 : int(it - answer_variables.begin());
            if (position >= 0) {
                if (bound[position]) {
                    return fail("?" + variable + " is selected by two components");
                }
                bound[position] = true;
            }
            positions.push_back(position);
        }
        set<vector<int>> extended;
        for (const vector<int> &row : rows) {
            for (vector<int> tuple : tuples) {
                for (size_t i = 0; i < positions.size(); ++i) {
                    if (positions[i] >= 0) {
                        tuple[positions[i]] = row[i];
                    }
                }
                extended.insert(move(tuple));
            }
        }
        tuples = move(extended);
        if (tuples.empty()) {
            // Answers are a product: one empty factor empties it.
            return true;
        }
    }
    for (size_t i = 0; i < answer_variables.size(); ++i) {
        if (!bound[i]) {
            return fail("no component selects ?" + answer_variables[i]);
        }
    }
    // tuples is sorted, as answers must be.
    for (const vector<int> &tuple : tuples) {
        GroundAtom atom;
        for (int object : tuple) {
            atom.push_back(object);
        }
        answers.push_back(move(atom));
    }
    return true;
}

bool KoncludeStateReasoner::entailed(const KoncludeQuery &query,
                                     const vector<GroundAtom> &candidates,
                                     vector<GroundAtom> &result)
{
    result.clear();
    vector<GroundAtom> answers;
    if (!answer(query, answers)) {
        return false;
    }
    for (const GroundAtom &candidate : candidates) {
        if (binary_search(answers.begin(), answers.end(), candidate, ground_atom_less)) {
            result.push_back(candidate);
        }
    }
    return true;
}

bool KoncludeStateReasoner::is_consistent(bool &consistent)
{
    if (!ok()) {
        return false;
    }
    if (!client.checkConsistency(&consistent)) {
        return fail(string("consistency check failed: ") + client.lastError());
    }
    return true;
}
