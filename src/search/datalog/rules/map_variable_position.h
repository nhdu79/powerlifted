#ifndef GROUNDER_VAR_POS_H
#define GROUNDER_VAR_POS_H

namespace datalog {


class MapVariablePosition {
    // Class mapping free variables to positions of the head/effect.
    // This class is used only for the join/product/projection operation, and not to retrieve
    // the full instantiation of action by "unsplitting" it.
    //
    // Heads carry only a handful of arguments, so a flat vector scanned
    // linearly beats hashing on both speed and cache behaviour. Duplicate
    // variables keep the *last* position (as an unordered_map would), so the
    // single-pass lookup below is behaviour-identical to the old map.
    std::vector<std::pair<Term, int>> mapping;

public:
    MapVariablePosition() = default;

    void create_map(const DatalogAtom &effect)
    {
        mapping.clear();
        int position_counter = 0;
        for (const auto &eff : effect.get_arguments()) {
            if (!eff.is_object()) {
                // Free variable: overwrite an earlier occurrence so the last
                // position wins, matching the previous map semantics.
                bool found = false;
                for (auto &p : mapping) {
                    if (p.first == eff) {
                        p.second = position_counter;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    mapping.emplace_back(eff, position_counter);
                }
            }
            ++position_counter;
        }
    }

    void clear()
    { 
        mapping.clear();
    }

    size_t size() {
      return mapping.size();
    }

    // Position of the head argument equal to t, or -1 if t does not occur as a
    // free variable in the head. Single scan; replaces has_variable()+at().
    int position_of(const Term &t) const
    {
        for (const auto &p : mapping) {
            if (p.first == t) return p.second;
        }
        return -1;
    }
};

}  // namespace datalog

#endif  // GROUNDER_VAR_POS_H