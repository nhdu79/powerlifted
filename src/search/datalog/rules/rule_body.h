#ifndef GROUNDER_RULE_BODY_H
#define GROUNDER_RULE_BODY_H

#include "join.h"
#include "product.h"
#include "project.h"
#include "generic_body.h"

#include <variant>

namespace datalog {

using RuleBody = std::variant<GenericBody, JoinBody, ProductBody, ProjectBody>;

}  // namespace datalog

#endif  // GROUNDER_RULE_BODY_H