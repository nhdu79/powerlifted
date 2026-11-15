#include "axiom_schema.h"

AxiomSchema::AxiomSchema(int index,
                         int layer,
                         std::vector<Parameter> parameters,
                         std::vector<Atom> body,
                         std::vector<Atom> equality_condition,
                         Atom head) :
        index(index), layer(layer),
        parameters(std::move(parameters)),
        body(std::move(body)),
        equality_condition(std::move(equality_condition)),
        head(std::move(head)) {}
