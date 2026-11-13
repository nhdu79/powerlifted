#ifndef SEARCH_CONDITIONAL_EFFECT_H
#define SEARCH_CONDITIONAL_EFFECT_H

#include "atom.h"
#include "structures.h"

#include <string>
#include <utility>
#include <vector>

class ConditionalEffect{

    std::vector<Atom> condition;
    std::vector<Atom> equality_condition;

    /*
     * Nullary predicates are represented as boolean vectors to simplify
     * other parts of the code (e.g., successor generation and action
     * applicability)
     */
    std::vector<bool> positive_nullary_cond;
    std::vector<bool> negative_nullary_cond;
    Atom effect;

public:
    explicit ConditionalEffect(std::vector<Atom> condition,
                               std::vector<Atom> equality_condition,
                               std::vector<bool> positive_nullary_cond,
                               std::vector<bool> negative_nullary_cond,
                               Atom effect);


    const std::vector<Atom> &get_condition() const {
        return condition;
    }

    const Atom &get_effect() const {
        return effect;
    }

    const std::vector<Atom> &get_equality_condition() const {
        return equality_condition;
    }

    const std::vector<bool> &get_positive_nullary_cond() const {
        return positive_nullary_cond;
    }

    const std::vector<bool> &get_negative_nullary_cond() const {
        return negative_nullary_cond;
    }
};

#endif //SEARCH_CONDITIONAL_EFFECT_H
