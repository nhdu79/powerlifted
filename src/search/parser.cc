#include "parser.h"
#include "action_schema.h"
#include "goal_condition.h"
#include "task.h"

#include "datalog/disjunctive_existential_program.h"

#include "utils/system.h"
#include "utils/string_utils.h"

#include <cassert>
#include <iostream>
#include <unordered_map>
#include <vector>

using namespace std;

/**
 * For the format of the intermediate file produced by the PDDL translation,
 * check the comments of the translation source code.
 *
 * @param task
 * @param in
 * @return
 */

bool parse(Task &task, const ifstream &in)
{

    // String used to guarantee consistency throughout the parsing
    string canary;

    if (not is_sparse_representation(canary)) {
        return false;
    }

    int number_types;
    cin >> canary >> number_types;
    if (not is_next_section_correct(canary, "TYPES")) {
        return false;
    }
    cout << "Total number of types: " << number_types << endl;
    parse_types(task, number_types);

    int number_predicates;
    cin >> canary >> number_predicates;
    if (not is_next_section_correct(canary, "PREDICATES")) {
        return false;
    }
    cout << "Total number of predicates: " << number_predicates << endl;
    parse_predicates(task, number_predicates);


    int number_objects;
    cin >> canary >> number_objects;
    if (not is_next_section_correct(canary, "OBJECTS")) {
        return false;
    }
    cout << "Total number of objects: " << number_objects << endl;
    parse_objects(task, number_objects);


    int initial_state_size;
    cin >> canary >> initial_state_size;
    if (not is_next_section_correct(canary, "INITIAL-STATE")) {
        return false;
    }
    cout << "Total number of atoms in the initial state: " << initial_state_size << endl;
    task.create_empty_initial_state(task.predicates.size(), number_objects);
    parse_initial_state(task, initial_state_size);
    

    // ************************************************************************
    // TODO:
    // * Parse axioms
    // * Apply axioms to initial state (maybe a separate part for derived
    //   predicates?)
    // ************************************************************************


    int goal_size;
    cin >> canary >> goal_size;
    if (not is_next_section_correct(canary, "GOAL")) {
        return false;
    }
    cout << "Total number of fluent atoms in the goal state: " << goal_size << endl;
    int number_mko_atoms = parse_goal(task, goal_size);


    int number_action_schemas;
    cin >> canary >> number_action_schemas;
    if (not is_next_section_correct(canary, "ACTION-SCHEMAS")) {
        return false;
    }
    cout << "Total number of action schemas: " << number_action_schemas << endl;
    number_mko_atoms += parse_action_schemas(task, number_action_schemas);

    int number_lowerbound_rules;
    cin >> canary >> number_lowerbound_rules;
    if (not is_next_section_correct(canary, "LOWERBOUND-RULES")) {
        return false;
    }
    cout << "Total number of lowerbound rules: " << number_lowerbound_rules << endl;
    task.set_lowerbound_program(parse_rules(task, canary, number_lowerbound_rules));

    int number_complements;
    cin >> canary >> number_complements;
    if (not is_next_section_correct(canary, "LOWERBOUND-COMPLEMENTS")) {
        return false;
    }
    if (!parse_complements(task, number_complements)) {
        return false;
    }
    cout << "Total number of lowerbound complements: " << number_complements << endl;

    int number_upperbound_rules;
    cin >> canary >> number_upperbound_rules;
    if (not is_next_section_correct(canary, "UPPERBOUND-RULES")) {
        return false;
    }
    cout << "Total number of upperbound rules: " << number_upperbound_rules << endl;
    task.set_upperbound_program(parse_rules(task, canary, number_upperbound_rules));

    int has_ontology;
    cin >> canary >> has_ontology;
    if (not is_next_section_correct(canary, "ONTOLOGY")) {
        return false;
    }
    if (has_ontology) {
        if (!parse_ontology(task)) {
            return false;
        }
        cout << "Ontology for Konclude: " << task.get_ontology().path << " ("
             << task.get_ontology().vocabulary.predicate_iris.size()
             << " predicates in its vocabulary)" << endl;
    }

    int number_konclude_queries;
    cin >> canary >> number_konclude_queries;
    if (not is_next_section_correct(canary, "KONCLUDE-QUERIES")) {
        return false;
    }
    // Written for every task with an ontology, also without an ONTOLOGY
    // section (i.e. without --use-konclude).
    if (!parse_konclude_queries(task, number_konclude_queries)) {
        return false;
    }
    if (number_konclude_queries > 0) {
        cout << "Mko queries in SPARQL for Konclude: " << number_konclude_queries << endl;
    }

    if (number_mko_atoms > 0) {
        cerr << "Warning: the task has " << number_mko_atoms
             << " mko atoms, which the search does not evaluate w.r.t. the "
                "lowerbound rules yet: non-nullary ones are evaluated on the "
                "state, nullary ones are ignored."
             << endl;
    }

    return true;
}

int parse_action_schemas(Task &task, int number_action_schemas)
{
    int number_mko_atoms = 0;
    vector<ActionSchema> actions;
    for (int i = 0; i < number_action_schemas; ++i) {
        string name;
        int cost, args, num_fresh_vars, precond_size, eff_size;
        cin >> name >> cost >> args >> num_fresh_vars >> precond_size >> eff_size;
        vector<Parameter> parameters;
        vector<FreshVariable> fresh_vars;
        vector<Atom> preconditions, equality_preconditions, effects;
        vector<bool> positive_nul_precond(task.predicates.size(), false),
            negative_nul_precond(task.predicates.size(), false),
            positive_nul_mko_precond(task.predicates.size(), false),
            negative_nul_mko_precond(task.predicates.size(), false),
            positive_nul_eff(task.predicates.size(), false),
            negative_nul_eff(task.predicates.size(), false);
        for (int j = 0; j < args; ++j) {
            string param_name;
            int index, type;
            cin >> param_name >> index >> type;
            parameters.emplace_back(param_name, index, type);
        }
        if (num_fresh_vars > 0)
            task.flag_object_creation();
        for (int j = 0; j < num_fresh_vars; ++j) {
            string var_name;
            int index, type;
            cin >> var_name >> index >> type;
            fresh_vars.emplace_back(var_name, index, false);
        }
        for (int j = 0; j < precond_size; ++j) {
            string precond_name;
            int index;
            bool negated;
            int arguments_size;
            cin >> precond_name >> index >> negated >> arguments_size;
            if (arguments_size == 0) {
                assert(task.nullary_predicates.find(index) != task.nullary_predicates.end());
                bool mko;
                cin >> mko;
                number_mko_atoms += mko;
                if (mko)
                    (negated ? negative_nul_mko_precond : positive_nul_mko_precond)[index] = true;
                else if (!negated)
                    positive_nul_precond[index] = true;
                else
                    negative_nul_precond[index] = true;
            }
            else if (utils::iequals(precond_name, "=")) {
                int id1, id2;
                char c, d;
                bool mko;
                cin >> c >> id1 >> d >> id2 >> mko;
                // (In)equality is never an mko: the translator reads mko(= ?x ?y)
                // as (= ?x ?y), under the unique name assumption.
                assert(!mko);

                vector<Argument> arguments;
                arguments.emplace_back(id1, c == 'c', false);
                arguments.emplace_back(id2, d == 'c', false);
                equality_preconditions.emplace_back(
                    std::move(arguments), std::move(precond_name), index, negated);
            }
            else {
                vector<Argument> arguments;
                for (int k = 0; k < arguments_size; ++k) {
                    char c;
                    int obj_index;
                    cin >> c >> obj_index;
                    if (c == 'c') {
                        arguments.emplace_back(obj_index, true, false);
                    }
                    else if (c == 'p') {
                        arguments.emplace_back(obj_index, false, false);
                    }
                    else {
                        cerr << "Error while reading action schema " << name
                             << ". Argument is neither constant or "
                                "object"
                             << endl;
                        utils::exit_with(utils::ExitCode::SEARCH_INPUT_ERROR);
                    }
                }
                bool mko;
                cin >> mko;
                number_mko_atoms += mko;
                preconditions.emplace_back(
                    std::move(arguments), std::move(precond_name), index, negated, mko);
            }
        }
        for (int j = 0; j < eff_size; ++j) {
            string eff_name;
            int index;
            bool negated;
            int arguments_size;
            cin >> eff_name >> index >> negated >> arguments_size;
            vector<Argument> arguments;
            if (arguments_size == 0) {
                assert(task.nullary_predicates.find(index) != task.nullary_predicates.end());
                if (!negated)
                    positive_nul_eff[index] = true;
                else
                    negative_nul_eff[index] = true;
                continue;
            }
            for (int k = 0; k < arguments_size; ++k) {
                char c;
                int obj_index;
                cin >> c >> obj_index;
                if (c == 'c') {
                    arguments.emplace_back(obj_index, true, false);
                }
                else if (c == 'p') {
                    arguments.emplace_back(obj_index, false, false);
                }
                else if (c == 'f') {
                    arguments.emplace_back(obj_index, false, true);
                }
                else {
                    cerr << "Error while reading action schema " << name
                         << ". Argument is neither constant or "
                            "object"
                         << endl;
                    utils::exit_with(utils::ExitCode::SEARCH_INPUT_ERROR);
                }
            }
            effects.emplace_back(std::move(arguments), std::move(eff_name), index, negated);
        }
        ActionSchema a(name,
                       i,
                       cost,
                       parameters,
                       fresh_vars,
                       preconditions,
                       effects,
                       equality_preconditions,
                       positive_nul_precond,
                       negative_nul_precond,
                       positive_nul_mko_precond,
                       negative_nul_mko_precond,
                       positive_nul_eff,
                       negative_nul_eff);
        actions.push_back(a);
    }
    task.initialize_action_schemas(actions);
    return number_mko_atoms;
}

/*
 * Per rule (see print_rules in the translator's translate.py): a line with
 * the number of effect atoms (0: bottom), body atoms and variables, then
 * one line per effect atom and per body atom:
 *   name predicate_index negated number_args (c|p index)*
 * 'c' is an object index, 'p' a variable index, numbered per rule. Negated
 * atoms aren't supported (the translator rewrites Clipper's inequality
 * denials into rules deriving "="), so negated must be 0.
 */
static datalog::DatalogAtom parse_rule_atom(const string &section)
{
    string name;
    int predicate_index;
    bool negated;
    int number_args;
    cin >> name >> predicate_index >> negated >> number_args;
    if (negated) {
        cerr << "Error while reading " << section << ": negated atom " << name
             << " is not supported." << endl;
        utils::exit_with(utils::ExitCode::SEARCH_UNSUPPORTED);
    }
    vector<datalog::Term> terms;
    for (int k = 0; k < number_args; ++k) {
        char c;
        int index;
        cin >> c >> index;
        if (c == 'c') {
            terms.emplace_back(index, datalog::OBJECT);
        }
        else if (c == 'p') {
            terms.emplace_back(index, datalog::VARIABLE);
        }
        else {
            cerr << "Error while reading " << section << ": argument of " << name
                 << " is neither constant nor variable." << endl;
            utils::exit_with(utils::ExitCode::SEARCH_INPUT_ERROR);
        }
    }
    return datalog::DatalogAtom(
        datalog::Arguments(std::move(terms)), predicate_index, false);
}

unique_ptr<datalog::DisjunctiveExistentialProgram>
parse_rules(Task &task, const string &section, int number_rules)
{
    vector<unique_ptr<datalog::DisjunctiveExistentialRule>> rules;
    for (int i = 0; i < number_rules; ++i) {
        int effect_size, body_size, number_variables;
        cin >> effect_size >> body_size >> number_variables;
        vector<datalog::DatalogAtom> effect, body;
        for (int j = 0; j < effect_size; ++j) {
            effect.push_back(parse_rule_atom(section));
        }
        for (int j = 0; j < body_size; ++j) {
            body.push_back(parse_rule_atom(section));
        }
        rules.push_back(make_unique<datalog::DisjunctiveExistentialRule>(
            std::move(effect), datalog::RuleBody(datalog::GenericBody(std::move(body)))));
    }

    vector<datalog::Object> objects;
    for (const Object &o : task.objects) {
        objects.emplace_back(o.get_name());
    }
    return make_unique<datalog::DisjunctiveExistentialProgram>(
        task.predicates, objects, std::move(rules));
}

int parse_goal(Task &task, int goal_size)
{
    int number_mko_atoms = 0;
    vector<AtomicGoal> goals;
    unordered_set<int> positive_nullary_goals, negative_nullary_goals;
    unordered_set<int> positive_nullary_mko_goals, negative_nullary_mko_goals;
    for (int i = 0; i < goal_size; ++i) {
        string name;
        int predicate_index;
        bool negated;
        int number_args;
        cin >> name >> predicate_index >> negated >> number_args;
        vector<int> args;
        copy_next_n_values(number_args, args);
        bool mko;
        cin >> mko;
        number_mko_atoms += mko;
        if (number_args == 0) {
            if (mko)
                (negated ? negative_nullary_mko_goals : positive_nullary_mko_goals)
                    .insert(predicate_index);
            else if (negated)
                negative_nullary_goals.insert(predicate_index);
            else
                positive_nullary_goals.insert(predicate_index);
            continue;
        }
        goals.emplace_back(predicate_index, args, negated, mko);
    }
    task.create_goal_condition(goals,
                               positive_nullary_goals,
                               negative_nullary_goals,
                               positive_nullary_mko_goals,
                               negative_nullary_mko_goals);
    return number_mko_atoms;
}

/*
 * Each complement is a line
 *   complement_name complement_index concept_name concept_index
 * (see print_complements in the translator).
 */
bool parse_complements(Task &task, int number_complements)
{
    auto is_predicate = [&task](const string &name, int index) {
        if (index >= 0 && index < int(task.predicates.size()) &&
            task.predicates[index].get_name() == name) {
            return true;
        }
        cerr << "Lowerbound complements: predicate " << name
             << " doesn't have index " << index << endl;
        return false;
    };
    unordered_map<int, int> complements;
    for (int i = 0; i < number_complements; ++i) {
        string complement_name, concept_name;
        int complement, complemented;
        cin >> complement_name >> complement >> concept_name >> complemented;
        if (!cin) {
            cerr << "Malformed LOWERBOUND-COMPLEMENTS section" << endl;
            return false;
        }
        if (!is_predicate(complement_name, complement) ||
            !is_predicate(concept_name, complemented)) {
            return false;
        }
        complements[complement] = complemented;
    }
    task.set_lowerbound_complements(move(complements));
    return true;
}

bool parse_ontology(Task &task)
{
    TaskOntology ontology;
    // The path is a line of its own, as it may contain spaces.
    cin >> ws;
    getline(cin, ontology.path);
    cin >> ontology.vocabulary.object_iri_prefix;
    string canary;
    int vocabulary_size;
    cin >> canary >> vocabulary_size;
    if (not is_next_section_correct(canary, "VOCABULARY")) {
        return false;
    }
    for (int i = 0; i < vocabulary_size; ++i) {
        string name, iri;
        int index;
        cin >> name >> index >> iri;
        if (index < 0 || index >= int(task.predicates.size()) ||
            task.predicates[index].get_name() != name) {
            cerr << "Ontology vocabulary: predicate " << name << " doesn't have index "
                 << index << endl;
            return false;
        }
        ontology.vocabulary.predicate_iris[name] = iri;
    }
    if (!cin || ontology.path.empty()) {
        cerr << "Malformed ONTOLOGY section" << endl;
        return false;
    }
    task.set_ontology(move(ontology));
    return true;
}

bool parse_konclude_queries(Task &task, int number_queries)
{
    TaskOntology ontology = task.get_ontology();
    for (int i = 0; i < number_queries; ++i) {
        string canary, name;
        KoncludeMkoQuery mko;
        int arity, number_answer_variables, number_cqs;
        cin >> canary >> name >> mko.predicate >> arity;
        bool is_query = canary == "KONCLUDE-QUERY";
        if (!cin || !(is_query || canary == "KONCLUDE-MKO") || mko.predicate < 0 ||
            mko.predicate >= int(task.predicates.size()) ||
            task.predicates[mko.predicate].get_name() != name ||
            task.predicates[mko.predicate].getArity() != arity ||
            (is_query && ontology.query_predicate_queries.count(mko.predicate))) {
            cerr << "Konclude queries: expected KONCLUDE-QUERY or KONCLUDE-MKO and a "
                    "predicate, got "
                 << canary << " " << name << " " << mko.predicate << endl;
            return false;
        }
        // A KONCLUDE-QUERY entry has no atom: it is any QUERY<i> atom's.
        for (int j = 0; !is_query && j < arity; ++j) {
            char kind;
            int index;
            cin >> kind >> index;
            bool constant = kind == 'c';
            if (!cin || (kind != 'c' && kind != 'p') || index < 0 ||
                (constant && index >= int(task.objects.size()))) {
                cerr << "Konclude queries: malformed argument of " << name << endl;
                return false;
            }
            mko.arguments.emplace_back(index, constant, false);
        }
        cin >> number_answer_variables;
        vector<string> answer_variables(max(number_answer_variables, 0));
        for (string &variable : answer_variables) {
            cin >> variable;
        }
        cin >> number_cqs;
        if (!cin || number_cqs <= 0) {
            cerr << "Malformed KONCLUDE-QUERIES section at " << name << endl;
            return false;
        }
        mko.cqs.resize(number_cqs);
        for (KoncludeQuery &cq : mko.cqs) {
            int number_components;
            cin >> number_components;
            if (!cin || number_components <= 0) {
                cerr << "Malformed KONCLUDE-QUERIES section at " << name << endl;
                return false;
            }
            cq.components.resize(number_components);
            // Each SPARQL query is a line of its own.
            for (string &component : cq.components) {
                cin >> ws;
                getline(cin, component);
            }
            cq.answer_variables = answer_variables;
        }
        if (!cin) {
            cerr << "Malformed KONCLUDE-QUERIES section at " << name << endl;
            return false;
        }
        if (is_query) {
            ontology.query_predicate_queries[mko.predicate] = move(mko.cqs);
        } else {
            ontology.mko_queries.push_back(move(mko));
        }
    }
    task.set_ontology(move(ontology));
    return true;
}

void parse_initial_state(Task &task, int initial_state_size)
{
    // StaticInformation static_info(task.predicates.size());
    for (int i = 0; i < initial_state_size; ++i) {
        string name;
        int index;
        int predicate_index;
        bool negated;
        int number_args;
        cin >> name >> index >> predicate_index >> negated >> number_args;
        if (number_args == 0) {
            assert(task.nullary_predicates.find(predicate_index) != task.nullary_predicates.end());
            task.initial_state.set_nullary_atom(predicate_index, true);
        }
        vector<int> args;
        copy_next_n_values(number_args, args);
        if (!task.initial_state.get_nullary_atoms()[predicate_index]) {
            GroundAtom ga(args.begin(), args.end());
            if (!task.predicates[predicate_index].isStaticPredicate())
                task.initial_state.add_tuple(predicate_index, ga);
            else
                task.static_info.add_tuple(predicate_index, ga);
        }
    }
    // task.set_static_info(static_info);
}

void parse_objects(Task &task, int number_objects)
{
    // Set number of objects
    task.initial_state.set_number_objects(number_objects);

    for (int i = 0; i < number_objects; ++i) {
        string name;
        int index;
        int n;
        cin >> name >> index >> n;
        vector<int> types;
        copy_next_n_values(n, types);
        task.add_object(name, index, types);
    }
}

void parse_predicates(Task &task, int number_predicates)
{
    for (int j = 0; j < number_predicates; ++j) {
        string predicate_name;
        int index;
        int number_args;
        bool static_pred;
        cin >> predicate_name >> index >> number_args >> static_pred;
        if (number_args == 0) {
            task.nullary_predicates.insert(index);
        }
        vector<int> types;
        copy_next_n_values(number_args, types);
        task.add_predicate(predicate_name, index, number_args, static_pred, types);
    }
}

void parse_types(Task &task, int number_types)
{
    for (int i = 0; i < number_types; ++i) {
        string type_name;
        int type_index;
        cin >> type_name >> type_index;
        task.add_type(type_name);
    }
}

bool is_sparse_representation(string &canary)
{
    cin >> canary;
    if (canary != "SPARSE-REPRESENTATION") {
        cerr << "Representation is not sparse. Not supported." << endl;
        return false;
    }
    return true;
}

bool is_next_section_correct(string &canary, const string &expected)
{
    if (canary != expected) {
        cerr << "Error while reading " << expected << " section." << endl;
        output_error(canary);
        return false;
    }
    return true;
}

void copy_next_n_values(int n, vector<int> &v)
{
    for (int i = 0; i < n; ++i) {
        int x;
        cin >> x;
        v.push_back(x);
    }
}

void output_error(string &msg)
{
    cerr << "String read was \'" << msg << "\' instead of the respective canary." << endl;
}
