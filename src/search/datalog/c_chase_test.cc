#include "disjunctive_existential_program.h"
#include "grounder/c_chase.h"

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
    predicates.emplace_back("hascolor", 7, 2, false, vector(2, 0));
    predicates.emplace_back("color", 8, 1, false, vector(1, 0));
    predicates.emplace_back("green", 9, 1, false, vector(1, 0));
    predicates.emplace_back("red", 10, 1, false, vector(1, 0));
    predicates.emplace_back("blue", 11, 1, false, vector(1, 0));
    predicates.emplace_back("greennode", 12, 1, false, vector(1, 0));
    predicates.emplace_back("rednode", 13, 1, false, vector(1, 0));
    predicates.emplace_back("bluenode", 14, 1, false, vector(1, 0));

    vector<datalog::Object> objects;
    objects.emplace_back("a");
    objects.emplace_back("b");
    objects.emplace_back("c");
    objects.emplace_back("d");
    objects.emplace_back("e");

    Term x(0, TERM_TYPES::VARIABLE);
    Term y(1, TERM_TYPES::VARIABLE);
    Term z(2, TERM_TYPES::VARIABLE);
    Term w(3, TERM_TYPES::VARIABLE);

    vector<unique_ptr<DisjunctiveExistentialRule>> rules;
    DatalogAtom edgexy(Arguments{x, y}, 0, false);
    DatalogAtom nodex(Arguments{x}, 2, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(nodex, RuleBody(GenericBody{edgexy})));
    DatalogAtom nodey(Arguments{y}, 2, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(nodey, RuleBody(GenericBody{edgexy})));
    DatalogAtom reachxy(Arguments{x, y}, 3, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(reachxy, RuleBody(GenericBody{edgexy})));
    DatalogAtom reachxz(Arguments{x, z}, 3, false);
    DatalogAtom edgezy(Arguments{z, y}, 0, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(reachxy, RuleBody(GenericBody{reachxz, edgezy})));
    DatalogAtom reachyx(Arguments{y, x}, 3, false);
    DatalogAtom innerx(Arguments{x}, 4, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(innerx, RuleBody(GenericBody{reachyx, reachxz})));
    DatalogAtom interestingx(Arguments{x}, 1, false);
    DatalogAtom answerx(Arguments{x}, 5, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(answerx, RuleBody(GenericBody{innerx, nodex, interestingx})));
    DatalogAtom answery(Arguments{y}, 5, false);
    DatalogAtom squarexy(Arguments{x, y}, 6, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(squarexy, RuleBody(GenericBody{answerx, answery})));

    rules.push_back(make_unique<DisjunctiveExistentialRule>(edgexy, RuleBody(GenericBody{nodex})));
    DatalogAtom hascolorxz(Arguments{x, z}, 7, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(hascolorxz, RuleBody(GenericBody{nodex})));
    DatalogAtom colorz(Arguments{z}, 8, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(colorz, RuleBody(GenericBody{hascolorxz})));
    DatalogAtom colorx(Arguments{x}, 8, false);
    DatalogAtom greenx(Arguments{x}, 9, false);
    DatalogAtom redx(Arguments{x}, 10, false);
    DatalogAtom bluex(Arguments{x}, 11, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(vector<DatalogAtom>{greenx, redx, bluex}, RuleBody(GenericBody{colorx})));
    DatalogAtom hascoloryw(Arguments{y, w}, 7, false);
    DatalogAtom greenz(Arguments{z}, 9, false);
    DatalogAtom greenw(Arguments{w}, 9, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(vector<DatalogAtom>{}, RuleBody(GenericBody{edgexy, hascolorxz, hascoloryw, greenz, greenw})));
    DatalogAtom edgexx(Arguments{x, x}, 0, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(interestingx, RuleBody(GenericBody{edgexx})));
    DatalogAtom hascoloryx(Arguments{y, x}, 7, false);
    DatalogAtom greennodey(Arguments{y}, 12, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(greennodey, RuleBody(GenericBody{hascoloryx, greenx})));
    DatalogAtom rednodey(Arguments{y}, 13, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(rednodey, RuleBody(GenericBody{hascoloryx, redx})));
    DatalogAtom bluenodey(Arguments{y}, 14, false);
    rules.push_back(make_unique<DisjunctiveExistentialRule>(bluenodey, RuleBody(GenericBody{hascoloryx, bluex})));

    DisjunctiveExistentialProgram program(predicates, objects, std::move(rules));
    program.convert_rules_to_normal_form();
    program.update_rule_indices();
    program.generate_skolem_constants();
    program.compute_distances_to_bottom();

    program.output_rules();
    program.print_statistics();
    vector<Fact> nlbf;
    CChase engine(program, nlbf);
    
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
    database.emplace_back(Arguments{a, b}, 0, false);
    database.emplace_back(Arguments{a, c}, 0, false);
    database.emplace_back(Arguments{b, d}, 0, false);
    database.emplace_back(Arguments{c, d}, 0, false);
    database.emplace_back(Arguments{d, c}, 0, false);
    database.emplace_back(Arguments{d, e}, 0, false);
    // interesting(.) facts
    database.emplace_back(Arguments{c}, 1, false);
    database.emplace_back(Arguments{d}, 1, false);

    cout << "Program inconsistent: " <<  engine.upper_bound_bottom_query(database) << endl;
    cout << "Upper bound:" << endl;
    for (Fact f : engine.upper_bound_query(database)) {
        program.output_fact(f);
        cout << endl;
    }
    engine.print_statistics();

    // for (Fact f : program.get_facts()) {
    //     program.output_fact(f);
    //     cout << endl;
    // }

    return 0;
}
