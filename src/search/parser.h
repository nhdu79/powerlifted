#ifndef SEARCH_PARSER_H
#define SEARCH_PARSER_H

#include <fstream>
#include <memory>
#include <string>
#include <vector>

class Task;
namespace datalog {
class DisjunctiveExistentialProgram;
}

bool parse(Task &task, const std::ifstream &in);
void output_error(std::string &msg);

bool is_sparse_representation(std::string &canary);
bool is_next_section_correct(std::string &canary, const std::string &expected);
/*
 * Read next n values from stdin and copy to v
 */
void copy_next_n_values(int n, std::vector<int> &v);

void parse_types(Task &task, int number_types);
void parse_predicates(Task &task, int number_predicates);
void parse_objects(Task &task, int number_objects);
void parse_initial_state(Task &task, int initial_state_size);
// Both return the number of mko atoms they read.
int parse_goal(Task &task, int goal_size);
int parse_action_schemas(Task &task, int number_action_schemas);
// Reads number_complements lines of the LOWERBOUND-COMPLEMENTS section
// (after its canary).
bool parse_complements(Task &task, int number_complements);
// Reads the ONTOLOGY section after its canary and "1" (see print_ontology
// in the translator).
bool parse_ontology(Task &task);
// Reads number_rules rules (after the section's canary) into a program over
// the task's predicates and objects.
std::unique_ptr<datalog::DisjunctiveExistentialProgram>
parse_rules(Task &task, const std::string &section, int number_rules);

#endif  // SEARCH_PARSER_H
