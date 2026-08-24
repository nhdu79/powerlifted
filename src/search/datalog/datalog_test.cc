#include "datalog.h"
#include "grounder/weighted_grounder.h"

using namespace datalog;
using namespace std;

int main(int argc, char *argv[]) {

    vector<Predicate> predicates;
    predicates.emplace_back("edge", 0, 2, false, vector(2, 0));
    predicates.emplace_back("interesting", 1, 1, false, vector(1, 0));
    predicates.emplace_back("node", 2, 1, false, vector(1, 0));
    predicates.emplace_back("reach", 3, 2, false, vector(2, 0));
    predicates.emplace_back("inner", 4, 1, false, vector(1, 0));
    predicates.emplace_back("answer", 5, 1, false, vector(1, 0));
    predicates.emplace_back("square", 6, 2, false, vector(2, 0));

    vector<datalog::Object> objects;
    objects.emplace_back("a");
    objects.emplace_back("b");
    objects.emplace_back("c");
    objects.emplace_back("d");
    objects.emplace_back("e");

    Term x(0, TERM_TYPES::VARIABLE);
    Term y(1, TERM_TYPES::VARIABLE);
    Term z(2, TERM_TYPES::VARIABLE);

    vector<unique_ptr<RuleBase>> rules;
    DatalogAtom edgexy(Arguments{x, y}, 0, false);
    DatalogAtom nodex(Arguments{x}, 2, false);
    rules.push_back(make_unique<RuleBase>(0, nodex, RuleBody(GenericBody{edgexy}), nullptr));
    DatalogAtom nodey(Arguments{y}, 2, false);
    rules.push_back(make_unique<RuleBase>(0, nodey, RuleBody(GenericBody{edgexy}), nullptr));
    DatalogAtom reachxy(Arguments{x, y}, 3, false);
    rules.push_back(make_unique<RuleBase>(0, reachxy, RuleBody(GenericBody{edgexy}), nullptr));
    DatalogAtom reachxz(Arguments{x, z}, 3, false);
    DatalogAtom edgezy(Arguments{z, y}, 0, false);
    rules.push_back(make_unique<RuleBase>(0, reachxy, RuleBody(GenericBody{reachxz, edgezy}), nullptr));
    DatalogAtom reachyx(Arguments{y, x}, 3, false);
    DatalogAtom innerx(Arguments{x}, 4, false);
    rules.push_back(make_unique<RuleBase>(0, innerx, RuleBody(GenericBody{reachyx, reachxz}), nullptr));
    DatalogAtom interestingx(Arguments{x}, 1, false);
    DatalogAtom answerx(Arguments{x}, 5, false);
    rules.push_back(make_unique<RuleBase>(0, answerx, RuleBody(GenericBody{innerx, nodex, interestingx}), nullptr));
    DatalogAtom answery(Arguments{y}, 5, false);
    DatalogAtom squarexy(Arguments{x, y}, 6, false);
    rules.push_back(make_unique<RuleBase>(0, squarexy, RuleBody(GenericBody{answerx, answery}), nullptr));

    Datalog program(predicates, objects, std::move(rules));
    program.convert_rules_to_normal_form();
    program.update_rule_indices();
    program.output_rules();
    program.print_statistics();
    WeightedGrounder grounder(program, datalog::H_ADD, false);
    
    vector<Fact> database;
    Term a(0, TERM_TYPES::OBJECT);
    Term b(1, TERM_TYPES::OBJECT);
    Term c(2, TERM_TYPES::OBJECT);
    Term d(3, TERM_TYPES::OBJECT);
    Term e(4, TERM_TYPES::OBJECT);
    // node(.) facts -- are derived
    // database.emplace_back(Arguments(vector<Term>{a}), 2, false);
    // database.emplace_back(Arguments(vector<Term>{b}), 2, false);
    // database.emplace_back(Arguments(vector<Term>{c}), 2, false);
    // database.emplace_back(Arguments(vector<Term>{d}), 2, false);
    // database.emplace_back(Arguments(vector<Term>{e}), 2, false);
    // edge(.,.) facts
    database.emplace_back(Arguments(vector<Term>{a, b}), 0, false);
    database.emplace_back(Arguments(vector<Term>{a, c}), 0, false);
    database.emplace_back(Arguments(vector<Term>{b, d}), 0, false);
    database.emplace_back(Arguments(vector<Term>{c, d}), 0, false);
    database.emplace_back(Arguments(vector<Term>{d, c}), 0, false);
    database.emplace_back(Arguments(vector<Term>{d, e}), 0, false);
    // interesting(.) facts
    database.emplace_back(Arguments(vector<Term>{c}), 1, false);
    database.emplace_back(Arguments(vector<Term>{d}), 1, false);

    grounder.ground(program, database, -1);
    grounder.print_statistics(program);

    for (Fact f : program.get_facts()) {
        program.output_fact(f);
        cout << endl;
    }

    return 0;
}
