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

// The translated query of the mko predicate(arguments), arguments object names
// or variables "?0", "?1", ... (numbered by first occurrence); null if none.
const KoncludeQuery *mko_query(const Task &task, const string &predicate,
                               const vector<string> &arguments) {
    for (const KoncludeMkoQuery &mko : task.get_ontology().mko_queries) {
        bool same = mko.predicate == predicate_index(task, predicate) &&
                    mko.arguments.size() == arguments.size() && mko.cqs.size() == 1;
        for (size_t i = 0; same && i < arguments.size(); ++i) {
            const Argument &argument = mko.arguments[i];
            same = arguments[i][0] == '?'
                       ? !argument.is_constant() &&
                             argument.get_index() == stoi(arguments[i].substr(1))
                       : argument.is_constant() &&
                             argument.get_index() == object_index(task, arguments[i]);
        }
        if (same) {
            return &mko.cqs[0];
        }
    }
    return nullptr;
}

// The translated query of the only QUERY<i> of the given arity (their numbers
// follow their rendering); null if there is none or several.
const KoncludeQuery *query_of_arity(const Task &task, int arity) {
    const KoncludeQuery *result = nullptr;
    for (const auto &[predicate, cqs] : task.get_ontology().query_predicate_queries) {
        if (task.predicates[predicate].getArity() == arity) {
            if (result || cqs.size() != 1) {
                return nullptr;
            }
            result = &cqs[0];
        }
    }
    return result;
}

bool is_ask(const string &sparql) { return sparql.rfind("ASK ", 0) == 0; }

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

// known_issue: a known Konclude bug makes the answers wrong or the query fail;
// reported, but not counted as a failure.
void check_answers(KoncludeStateReasoner &reasoner, const Task &task,
                   const string &label, const KoncludeQuery &query,
                   const vector<vector<string>> &expected,
                   const string &known_issue = "") {
    vector<GroundAtom> answers;
    if (!reasoner.answer(query, answers)) {
        if (!known_issue.empty()) {
            cout << "  KNOWN (" << known_issue << ") " << label << ": "
                 << reasoner.last_error() << endl;
            return;
        }
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

    // The mkos of the team task (see its domain.pddl): Recruit and Transfer
    // share (mko (and (Team ?t) (Player ?p))), Recruit and Celebrate
    // (mko (exists (?c) (and (hasCaptain ?t ?c) (Captain ?c)))); Transfer reads
    // (mko (hasMember ?from ?p)), Celebrate (mko (hasMember ?t star)), with the
    // domain's constant star; the goal (mko (hasMember red bob)),
    // (mko (hasMember red carol)) and
    // (mko (exists (?t) (and (Team ?t) (hasMember ?t star)))). The queries
    // below are hand-written; the translator's (one per mko) are checked too.
    // A team-and-player query is disconnected, so it has two components.
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
    // ASK components select no variable: the empty tuple if entailed.
    auto object = [&](const string &name) {
        return "<" + ontology.vocabulary.object_iri_prefix + name + ">";
    };
    KoncludeQuery ask_red_bob{
        {PREFIXES + "ASK { " + object("red") + " team:hasMember " + object("bob") + " . }"}, {}};
    KoncludeQuery ask_star_member{
        {PREFIXES + "ASK { _:t team:hasMember " + object("star") + " . }"}, {}};
    // Team ⊑ ∃hasCaptain.Captain: blue's captain is anonymous.
    KoncludeQuery ask_blue_captained{
        {PREFIXES + "ASK { " + object("blue") + " team:hasCaptain _:c . _:c rdf:type team:Captain . }"},
        {}};
    // Only a role atom on the blank node: once wrongly true for every
    // individual (ASK) or bound to an anonymous individual (SELECT).
    KoncludeQuery ask_bob_captained{
        {PREFIXES + "ASK { " + object("bob") + " team:hasCaptain _:c . }"}, {}};
    KoncludeQuery captained_teams{
        {PREFIXES + "SELECT ?t WHERE { ?t team:hasCaptain _:c . }"}, {"t"}};
    // A SELECT and an ASK component: the teams, if red has bob.
    KoncludeQuery teams_if_red_bob{
        {PREFIXES + "SELECT ?t WHERE { ?t rdf:type team:Team . }", ask_red_bob.components[0]},
        {"t"}};

    // The translator's: three QUERY<i> (the shared ones and the goal's), four
    // atomic mkos.
    check(ontology.query_predicate_queries.size() == 3 && ontology.mko_queries.size() == 4,
          "3 translated QUERY<i>, 4 translated atomic mkos");
    // Its answer variables are its free variables, sorted: ?p, ?t.
    const KoncludeQuery *player_and_team = query_of_arity(task, 2);
    const KoncludeQuery *captained = query_of_arity(task, 1);
    // No answer variable, so an ASK.
    const KoncludeQuery *star_signed = query_of_arity(task, 0);
    check(player_and_team && player_and_team->components.size() == 2,
          "QUERY<i>(?p,?t) translated: two components");
    check(captained && captained->components.size() == 1, "QUERY<i>(?t) translated");
    check(star_signed && star_signed->components.size() == 1 &&
              is_ask(star_signed->components[0]),
          "QUERY<i>() translated: an ASK");
    const KoncludeQuery *member = mko_query(task, "hasmember", {"?0", "?1"});
    const KoncludeQuery *has_star = mko_query(task, "hasmember", {"?0", "star"});
    // Ground, so an ASK.
    const KoncludeQuery *red_bob = mko_query(task, "hasmember", {"red", "bob"});
    const KoncludeQuery *red_carol = mko_query(task, "hasmember", {"red", "carol"});
    check(member && has_star, "hasmember(?0,?1), hasmember(?0,star) translated");
    check(red_bob && is_ask(red_bob->components[0]) && red_carol &&
              is_ask(red_carol->components[0]),
          "hasmember(red,bob), hasmember(red,carol) translated: ASKs");
    auto answers = [&](const string &label, const KoncludeQuery *query,
                       const vector<vector<string>> &expected) {
        if (query) {
            check_answers(reasoner, task, "translated " + label, *query, expected);
        }
    };
    // A query without answer variables: the empty tuple if entailed, none
    // otherwise.
    auto entailed_if = [](bool entailed) {
        return entailed ? vector<vector<string>>{{}} : vector<vector<string>>{};
    };
    // The goal's mkos.
    auto goal_entailed = [&](bool bob, bool carol, bool star) {
        answers("hasmember(red,bob)", red_bob, entailed_if(bob));
        answers("hasmember(red,carol)", red_carol, entailed_if(carol));
        answers("QUERY<i>() (star in a team)", star_signed, entailed_if(star));
    };
    // The hand-written ASK queries; star is in a team and blue captained in
    // every state.
    auto asks = [&](bool red_has_bob) {
        check_answers(reasoner, task, "ASK hasMember(red,bob)", ask_red_bob,
                      entailed_if(red_has_bob));
        check_answers(reasoner, task, "ASK hasMember(_,star)", ask_star_member, entailed_if(true));
        check_answers(reasoner, task, "ASK hasCaptain(blue,_), Captain(_)", ask_blue_captained,
                      entailed_if(true));
        check_answers(reasoner, task, "ASK hasCaptain(bob,_)", ask_bob_captained, entailed_if(false));
        check_answers(reasoner, task, "hasCaptain(t,_)", captained_teams, {{"red"}, {"blue"}});
        check_answers(reasoner, task, "Team(t) if ASK hasMember(red,bob)", teams_if_red_bob,
                      red_has_bob ? vector<vector<string>>{{"red"}, {"blue"}}
                                  : vector<vector<string>>{});
    };

    const DBState &initial = task.get_initial_state();
    int has_member_index = predicate_index(task, "hasmember");
    DBState after_bob = initial;
    after_bob.add_tuple(has_member_index, tuples(task, {{"red", "bob"}})[0]);
    DBState after_carol = after_bob;
    after_carol.add_tuple(has_member_index, tuples(task, {{"red", "carol"}})[0]);
    // (transfer blue red star); DBState can't remove a tuple, so rebuild it.
    vector<Relation> relations = after_carol.get_relations();
    relations[has_member_index].tuples.erase(tuples(task, {{"blue", "star"}})[0]);
    vector<bool> nullary_atoms = after_carol.get_nullary_atoms();
    DBState after_star(move(relations), move(nullary_atoms),
                       after_carol.get_number_objects());
    after_star.add_tuple(has_member_index, tuples(task, {{"red", "star"}})[0]);
    vector<GroundAtom> goal = tuples(task, {{"red", "bob"}, {"red", "carol"}});
    vector<GroundAtom> entailed;

    cout << "initial state" << endl;
    check(reasoner.set_state(initial), "set_state");
    check(reasoner.current_facts().size() == 4, "4 facts told (hascaptain, 3 hasmember)");
    bool consistent = false;
    check(reasoner.is_consistent(consistent) && consistent, "consistent");
    // Only entailed: nothing in the state says who is a team or a player.
    check_answers(reasoner, task, "Team(t), Player(p)", team_and_player,
                  {{"red", "alice"}, {"red", "bob"}, {"red", "carol"}, {"red", "star"},
                   {"blue", "alice"}, {"blue", "bob"}, {"blue", "carol"}, {"blue", "star"}});
    answers("QUERY<i>(p,t) (player and team)", player_and_team,
            {{"alice", "red"}, {"bob", "red"}, {"carol", "red"}, {"star", "red"},
             {"alice", "blue"}, {"bob", "blue"}, {"carol", "blue"}, {"star", "blue"}});
    // Team ⊑ ∃hasCaptain.Captain: blue's captain is anonymous.
    answers("QUERY<i>(t) (captained team)", captained, {{"red"}, {"blue"}});
    answers("hasmember(t,p)", member, {{"blue", "bob"}, {"blue", "carol"}, {"blue", "star"}});
    answers("hasmember(t,star)", has_star, {{"blue"}});
    goal_entailed(false, false, true);
    asks(false);
    check_answers(reasoner, task, "hasMember(t,p)", has_member,
                  {{"blue", "bob"}, {"blue", "carol"}, {"blue", "star"}});
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
                  {{"red", "bob"}, {"blue", "bob"}, {"blue", "carol"}, {"blue", "star"}});
    check(reasoner.entailed(has_member, goal, entailed) &&
              entailed == tuples(task, {{"red", "bob"}}),
          "goal: only hasMember(red,bob) entailed");
    goal_entailed(true, false, true);
    asks(true);

    cout << "after (recruit red carol)" << endl;
    check(reasoner.set_state(after_carol), "set_state");
    check(reasoner.entailed(has_member, goal, entailed) && entailed == goal,
          "goal entailed");
    goal_entailed(true, true, true);

    cout << "after (transfer blue red star)" << endl;
    diff = KoncludeStateReasoner::diff(reasoner.current_facts(), reasoner.facts_of(after_star));
    check(diff.tell.size() == 1 && diff.retract.size() == 1, "diff tells 1, retracts 1 fact");
    check(reasoner.set_state(after_star), "set_state");
    answers("hasmember(t,star)", has_star, {{"red"}});
    goal_entailed(true, true, true);
    asks(true);

    cout << "back to the initial state" << endl;
    diff = KoncludeStateReasoner::diff(reasoner.current_facts(), reasoner.facts_of(initial));
    check(diff.retract.size() == 3 && diff.tell.size() == 1, "diff retracts 3, tells 1 fact");
    check(reasoner.set_state(initial), "set_state");
    check_answers(reasoner, task, "hasMember(t,p)", has_member,
                  {{"blue", "bob"}, {"blue", "carol"}, {"blue", "star"}});
    answers("hasmember(t,star)", has_star, {{"blue"}});
    asks(false);
    check_answers(reasoner, task, "Captain(x)", captain, {{"alice"}}, CAPTAIN_ISSUE);
    check(reasoner.set_state(initial) && reasoner.number_state_changes() == 5,
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
