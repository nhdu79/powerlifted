#ifndef SEARCH_AXIOM_SCHEMA_H
#define SEARCH_AXIOM_SCHEMA_H

#include "atom.h"
#include <vector>

class AxiomSchema {
    int index;
    int layer;
    std::vector<Parameter> parameters;
    std::vector<Atom> body;
    std::vector<Atom> equality_condition;
    Atom head;

public:
    explicit AxiomSchema(int index,
                         int layer,
                         std::vector<Parameter> parameters,
                         std::vector<Atom> body,
                         std::vector<Atom> equality_condition,
                         Atom head);
    
    int get_index() const {
        return index;
    }

    const std::vector<Parameter> &get_parameters() const {
        return parameters;
    }

    const std::vector<Atom> &get_body() const {
        return body;
    }
    
    const std::vector<Atom> &get_equality_condition() const {
        return equality_condition;
    }

    const Atom &get_head() const {
        return head;
    }

    bool is_ground() const {
        return parameters.empty();
    }

    bool operator<(const AxiomSchema& other) const {
        return index < other.index;
    }

    bool operator==(const AxiomSchema& other) const {
        return index == other.index;
    }

    bool operator!=(const AxiomSchema& other) const {
        return index != other.index;
    }
};
#endif //SEARCH_AXIOM_SCHEMA_H
