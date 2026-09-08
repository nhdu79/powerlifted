#ifndef GROUNDER_RULE_BASE_H
#define GROUNDER_RULE_BASE_H

#include "rule_body.h"
#include "map_variable_position.h"

namespace datalog {

class RuleBase {
protected:
    DatalogAtom effect;
    RuleBody body;
    int weight;
    int index;
    bool ground_effect;
    std::unique_ptr<Annotation> annotation;

    MapVariablePosition variable_position;

    static int next_index;

public:
    RuleBase(int weight,
             DatalogAtom eff,
             RuleBody b,
             std::unique_ptr<Annotation> annotation)
        : effect(std::move(eff)),
          body(std::move(b)),
          weight(weight),
          index(next_index++),
          annotation(std::move(annotation))
    {
        variable_position.create_map(effect);
        ground_effect = true;
        for (const auto &e : effect.get_arguments()) {
            if (!e.is_object()) {
                ground_effect = false;
            }
        }
    };

    bool head_is_ground() const { return ground_effect; }

    void update_index(int i) { index = i; }

    void recreate_map_variable_position(const DatalogAtom &effect)
    {
        variable_position.create_map(effect);
    }

    const DatalogAtom &get_effect() const { return effect; }

    template <typename F>
    decltype(auto) visit_body(F&& f) {
        return std::visit(std::forward<F>(f), body);
    }

    template <typename F>
    decltype(auto) visit_body(F&& f) const {
        return std::visit(std::forward<F>(f), body);
    }

    // needed to "convert" from the std::variant RuleBody to the abstract base class RuleBodyBase
    RuleBodyBase &get_body() {
      return visit_body([](RuleBodyBase &c) -> RuleBodyBase& { return c; });
    }
    const RuleBodyBase &get_body() const {
      return visit_body([](const RuleBodyBase &c) -> const RuleBodyBase& { return c; });
    }

    const std::vector<DatalogAtom> &get_conditions() const {
      return get_body().get_conditions();
    }

    int get_index() const { return index; }

    int get_weight() const { return weight; }

    const Arguments &get_effect_arguments() const { return effect.get_arguments(); }

    std::unique_ptr<Annotation> get_annotation() { return std::move(annotation); }

    MapVariablePosition get_variable_position_map() const { return variable_position; }

    bool has_annotation() const { return annotation != nullptr; }

    void execute(int head, const Datalog &datalog) const
    {
        if (annotation) {
            annotation->execute(head, datalog);
        }
    }

    bool is_equivalent(const RuleBase &other) const
    {
        return (weight == other.get_weight()) &&
               (get_effect_arguments() == other.get_effect_arguments()) &&
               (get_conditions() == other.get_conditions());
    }

    void update_effect_arguments(std::vector<Term> &terms) { effect.update_arguments(terms); }

};

}  // namespace datalog


#endif  // GROUNDER_RULE_BASE_H
