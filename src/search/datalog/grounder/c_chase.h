#ifndef GROUNDER_C_CHASE_H_
#define GROUNDER_C_CHASE_H_

#include "../disjunctive_existential_program.h"
#include "../rule_matcher.h"

#include "../../algorithms/priority_queues.h"


namespace datalog {

enum CChaseMode { SPLIT, CHOICE }; // SPLIT = U_2, CHOICE = U_3

class CChase {

    DisjunctiveExistentialProgram &program;

    std::queue<int> q;

    // The state facts are the first facts created each grounding, so they
    // occupy the contiguous fact-index range [0, num_initial_facts). Testing
    // "is this an initial fact" is therefore a single comparison — no need for a
    // per-evaluation hash set of their indices.
    int num_initial_facts;

    // This is a member instead of a chase() local so its capacity survives across
    // calls (state facts + derived (semi-instantiated) atoms only).
    // We use the Fact class here instead of DatalogAtom since Facts don't
    // increase the Fact::next_fact_index by default (and don't check their argument
    // list for variables).
    phmap::flat_hash_set<Fact> reached_atoms;

    int queue_pushes;
    int atoms_produced;
    // Sums over all ground() calls of the search. Unlike the per-call
    // counters, nothing resets these, so the planner can report one total at
    // the end of the search.
    unsigned long long cumulative_atoms_produced;
    unsigned long long cumulative_queue_pushes;
    int total_number_of_facts;

    void add_fact(const DisjunctiveExistentialRule &rule, Fact& fact);

    void check_and_add_atom(const DisjunctiveExistentialRule &rule, int head_index, const Arguments &instantiation, bool ground);

    int choice_function(const std::vector<DatalogAtom> &effect, const std::vector<Fact> &instantiated_facts, std::vector<Fact> &negated_lower_bound);

    template<typename A>
    void check_and_add_disjunction(const DisjunctiveExistentialRule &rule, const A &instantiation, CChaseMode mode, std::vector<Fact> &negated_lower_bound);

protected:

    RuleMatcher rule_matcher;

    void create_rule_matcher();

public:
    CChase(DisjunctiveExistentialProgram &p) :
        program(p)
    {
        create_rule_matcher();
        queue_pushes = 0;
        atoms_produced = 0;
        cumulative_atoms_produced = 0;
        cumulative_queue_pushes = 0;
        total_number_of_facts = 0;
    }

    ~CChase() = default;

    bool chase(std::vector<Fact> &lower_bound, std::vector<Fact> &negated_lower_bound, CChaseMode mode, bool stop_on_bot);
    
    const std::vector<Fact> upper_bound_query(std::vector<Fact> &lower_bound, std::vector<Fact> &negated_lower_bound);

    bool upper_bound_bottom_query(std::vector<Fact> &lower_bound, std::vector<Fact> &negated_lower_bound);

    void print_statistics() {
        std::cout << program.get_number_of_facts() << " final number of facts" << std::endl;
        std::cout << atoms_produced << " total atoms produced" << std::endl;
        std::cout << queue_pushes << " total queue pushes" << std::endl;
    }

    unsigned long long get_cumulative_atoms_produced() const {
        return cumulative_atoms_produced;
    }

    unsigned long long get_cumulative_queue_pushes() const {
        return cumulative_queue_pushes;
    }

};

}

#endif //GROUNDER_GROUNDERS_FAST_DOWNWARD_GROUNDER_H_
