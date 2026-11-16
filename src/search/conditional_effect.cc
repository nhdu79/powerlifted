#include "conditional_effect.h"

ConditionalEffect::ConditionalEffect(std::vector<Atom> condition,
                                     std::vector<Atom> equality_condition,
                                     std::vector<bool> positive_nullary_cond,
                                     std::vector<bool> negative_nullary_cond,
                                     std::vector<bool> positive_nullary_mko_cond,
                                     std::vector<bool> negative_nullary_mko_cond,
                                     Atom effect) :
        condition(std::move(condition)),
        equality_condition(std::move(equality_condition)),
        positive_nullary_cond(std::move(positive_nullary_cond)),
        negative_nullary_cond(std::move(negative_nullary_cond)),
        positive_nullary_mko_cond(std::move(positive_nullary_mko_cond)),
        negative_nullary_mko_cond(std::move(negative_nullary_mko_cond)),
        effect(std::move(effect)) {}
