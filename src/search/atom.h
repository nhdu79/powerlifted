#ifndef SEARCH__ATOM_H_
#define SEARCH__ATOM_H_

#include "structures.h"

class Atom {

    std::vector<Argument> arguments;
    std::string name;
    int predicate_symbol : 30;
    bool negated : 1;
    // The atom stands for an mko: it is to be evaluated w.r.t. the
    // lowerbound rules, not on the state.
    bool mko : 1;

public:
    Atom(std::vector<Argument> &&tuples,
         std::string &&name,
         int predicate_symbol,
         bool negated,
         bool mko = false) :
        arguments(std::move(tuples)),
        name(std::move(name)),
        predicate_symbol(predicate_symbol),
        negated(negated),
        mko(mko) {}

    const std::string &get_name() const {
        return name;
    }

    int get_predicate_symbol_idx() const {
        return predicate_symbol;
    }

    const std::vector<Argument> &get_arguments() const {
        return arguments;
    }

    bool is_negated() const {
        return negated;
    }

    bool is_mko() const {
        return mko;
    }

    bool is_ground() const {
        return arguments.empty();
    }

};
#endif //SEARCH__ATOM_H_
