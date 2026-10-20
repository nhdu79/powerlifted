// Runs KoncludeStateReasoner on the team task (dev/domains/team, ontology
// dev/ontologies/team.owl): state changes as the plan (recruit red bob)
// (recruit red carol) makes them, a jump back to the initial state, and the
// queries of the task's mkos. Exit code 0 = all checks passed.
//
//   konclude_test TASK.lifted [WORKER] [RESTART_EVERY]
//
// WORKER defaults to the build's konclude_worker (also if empty), RESTART_EVERY
// to 2. TASK.lifted is the translator's output for the team task, with the
// normalized ontology in functional syntax (--konclude-ontology-file), whose
// path and vocabulary the test reads from it; dev/test-konclude.py
// translates it and runs this test.

#include "state_reasoner.h"

#include "../parser.h"
#include "../task.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using namespace std;

namespace {

const string TEAM = "http://www.semanticweb.org/anon/ontologies/2026/9/Team/";
const string PREFIXES =
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
    "PREFIX team: <" + TEAM + ">\n";

// Konclude's realization misses this entailment (its CLI too; consistency
// checking does find it): see docs/INCREMENTAL_REASONING.md §4 in Konclude.
const string CAPTAIN_ISSUE = "Konclude misses Captain via max cardinality";

int failures = 0;

int object_index(const Task &task, const string &name) {
    for (const Object &object : task.objects) {
        if (object.get_name() == name) {
            return object.get_index();
        }
    }
    cerr << "no object " << name << endl;
    exit(2);
}

int predicate_index(const Task &task, const string &name) {
    for (const Predicate &predicate : task.predicates) {
        if (predicate.get_name() == name) {
            return predicate.get_index();
        }
    }
    cerr << "no predicate " << name << endl;
    exit(2);
}

// Tuples of object names, e.g. {{"red", "bob"}}.
vector<GroundAtom> tuples(const Task &task, const vector<vector<string>> &names) {
    vector<GroundAtom> result;
    for (const vector<string> &tuple : names) {
        GroundAtom atom;
        for (const string &name : tuple) {
            atom.push_back(object_index(task, name));
        }
        result.push_back(atom);
    }
    return result;
}

string to_string(const Task &task, const vector<GroundAtom> &atoms) {
    string result = "{";
    for (size_t i = 0; i < atoms.size(); ++i) {
        result += i ? " (" : "(";
        for (size_t j = 0; j < atoms[i].size(); ++j) {
            result += (j ? "," : "") + task.get_object_name(atoms[i][j]);
        }
        result += ")";
    }
    return result + "}";
}

void check(bool ok, const string &what) {
    cout << (ok ? "  ok   " : "  FAIL ") << what << endl;
    if (!ok) {
        ++failures;
    }
}

// known_issue: a known Konclude bug makes the answers wrong; reported, but not
// counted as a failure.
void check_answers(KoncludeStateReasoner &reasoner, const Task &task,
                   const string &label, const KoncludeQuery &query,
                   const vector<vector<string>> &expected,
                   const string &known_issue = "") {
    vector<GroundAtom> answers;
    if (!reasoner.answer(query, answers)) {
        check(false, label + ": " + reasoner.last_error());
        return;
    }
    // answer() sorts by object index; tuples() keeps the given order.
    vector<GroundAtom> wanted = tuples(task, expected);
    sort(wanted.begin(), wanted.end(), [](const GroundAtom &a, const GroundAtom &b) {
        return lexicographical_compare(a.begin(), a.end(), b.begin(), b.end());
    });
    string what = label + " = " + to_string(task, answers) +
                  (answers == wanted ? "" : ", expected " + to_string(task, wanted));
    if (!known_issue.empty()) {
        cout << (answers == wanted ? "  ok   (known issue fixed: " : "  KNOWN (")
             << known_issue << ") " << what << endl;
        return;
    }
    check(answers == wanted, what);
}

} // namespace

int main(int argc, char *argv[]) {
    if (argc < 2) {
        cerr << "usage: " << argv[0] << " TASK.lifted [WORKER] [RESTART_EVERY]" << endl;
        return 2;
    }
    string worker = argc > 2 && argv[2][0] ? argv[2] : KONCLUDE_WORKER_PATH;
    int restart_every = argc > 3 ? atoi(argv[3]) : 2;

    ifstream task_file(argv[1]);
    if (!task_file) {
        cerr << "cannot open " << argv[1] << endl;
        return 2;
    }
    cin.rdbuf(task_file.rdbuf());
    string domain_name, task_name;
    cin >> domain_name >> task_name;
    Task task(domain_name, task_name);
    if (!parse(task, task_file)) {
        cerr << "parsing " << argv[1] << " failed" << endl;
        return 2;
    }

    const TaskOntology &ontology = task.get_ontology();
    if (ontology.path.empty()) {
        cerr << argv[1] << " names no ontology (translate with --konclude-ontology-file)"
             << endl;
        return 2;
    }
    // The translator keeps the team ontology's IRIs.
    check(ontology.vocabulary.predicate_iris.count("hasmember") &&
              ontology.vocabulary.predicate_iris.at("hasmember") == TEAM + "hasMember",
          "vocabulary: hasmember is " + TEAM + "hasMember");

    KoncludeStateReasoner reasoner(task, ontology.vocabulary, ontology.path, worker,
                                   restart_every);
    if (!reasoner.ok()) {
        cerr << reasoner.last_error() << endl;
        return 1;
    }

    // The mkos of the team task: (Recruit ?t ?p)'s precondition
    // (mko (and (Team ?t) (Player ?p))) and the goal's (mko (hasMember red bob)),
    // (mko (hasMember red carol)).
    // The team-and-player mko is disconnected, so it has two components.
    KoncludeQuery team_and_player{
        {PREFIXES + "SELECT ?t WHERE { ?t rdf:type team:Team . }",
         PREFIXES + "SELECT ?p WHERE { ?p rdf:type team:Player . }"},
        {"t", "p"}};
    KoncludeQuery has_member{
        {PREFIXES + "SELECT ?t ?p WHERE { ?t team:hasMember ?p . }"}, {"t", "p"}};
    KoncludeQuery captain{
        {PREFIXES + "SELECT ?x WHERE { ?x rdf:type team:Captain . }"}, {"x"}};
    // Not split into components: must fail rather than answer partially.
    KoncludeQuery disconnected{
        {PREFIXES + "SELECT ?t ?p WHERE { ?t rdf:type team:Team . ?p rdf:type team:Player . }"},
        {"t", "p"}};

    const DBState &initial = task.get_initial_state();
    int has_member_index = predicate_index(task, "hasmember");
    DBState after_bob = initial;
    after_bob.add_tuple(has_member_index, tuples(task, {{"red", "bob"}})[0]);
    DBState after_carol = after_bob;
    after_carol.add_tuple(has_member_index, tuples(task, {{"red", "carol"}})[0]);
    vector<GroundAtom> goal = tuples(task, {{"red", "bob"}, {"red", "carol"}});
    vector<GroundAtom> entailed;

    cout << "initial state" << endl;
    check(reasoner.set_state(initial), "set_state");
    check(reasoner.current_facts().size() == 3, "3 facts told (hascaptain, 2 hasmember)");
    bool consistent = false;
    check(reasoner.is_consistent(consistent) && consistent, "consistent");
    // Only entailed: nothing in the state says who is a team or a player.
    check_answers(reasoner, task, "Team(t), Player(p)", team_and_player,
                  {{"red", "alice"}, {"red", "bob"}, {"red", "carol"},
                   {"blue", "alice"}, {"blue", "bob"}, {"blue", "carol"}});
    check_answers(reasoner, task, "hasMember(t,p)", has_member,
                  {{"blue", "bob"}, {"blue", "carol"}});
    // Team ⊑ ∃hasCaptain.Captain ⊓ ≤1 hasCaptain.Player: red's captain is alice.
    check_answers(reasoner, task, "Captain(x)", captain, {{"alice"}}, CAPTAIN_ISSUE);
    check(reasoner.entailed(has_member, goal, entailed) && entailed.empty(),
          "goal not entailed");
    vector<GroundAtom> partial;
    bool answered = reasoner.answer(disconnected, partial);
    check(!answered && reasoner.ok() &&
              reasoner.last_error().find("unbound") != string::npos,
          "a disconnected component fails, the reasoner stays usable");

    cout << "after (recruit red bob)" << endl;
    KoncludeStateDiff diff =
        KoncludeStateReasoner::diff(reasoner.current_facts(), reasoner.facts_of(after_bob));
    check(diff.tell.size() == 1 && diff.retract.empty(), "diff tells 1 fact");
    check(reasoner.apply_diff(diff), "apply_diff");
    check_answers(reasoner, task, "hasMember(t,p)", has_member,
                  {{"red", "bob"}, {"blue", "bob"}, {"blue", "carol"}});
    check(reasoner.entailed(has_member, goal, entailed) &&
              entailed == tuples(task, {{"red", "bob"}}),
          "goal: only hasMember(red,bob) entailed");

    cout << "after (recruit red carol)" << endl;
    check(reasoner.set_state(after_carol), "set_state");
    check(reasoner.entailed(has_member, goal, entailed) && entailed == goal,
          "goal entailed");

    cout << "back to the initial state" << endl;
    check(KoncludeStateReasoner::diff(reasoner.current_facts(), reasoner.facts_of(initial))
                  .retract.size() == 2,
          "diff retracts 2 facts");
    check(reasoner.set_state(initial), "set_state");
    check_answers(reasoner, task, "hasMember(t,p)", has_member,
                  {{"blue", "bob"}, {"blue", "carol"}});
    check_answers(reasoner, task, "Captain(x)", captain, {{"alice"}}, CAPTAIN_ISSUE);
    check(reasoner.set_state(initial) && reasoner.number_state_changes() == 4,
          "same state again: no state change");

    cout << reasoner.number_state_changes() << " state changes, "
         << reasoner.number_worker_restarts() << " worker restarts (every "
         << restart_every << "), worker RSS " << reasoner.worker_rss_kb() << " kB" << endl;
    if (restart_every > 0 && restart_every < reasoner.number_state_changes()) {
        check(reasoner.number_worker_restarts() > 0, "the worker was restarted");
    }
    cout << (failures ? "FAILED: " + std::to_string(failures) + " checks" : "PASS") << endl;
    return failures ? 1 : 0;
}
