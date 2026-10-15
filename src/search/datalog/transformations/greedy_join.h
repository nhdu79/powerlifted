#ifndef SEARCH_DATALOG_TRANSFORMATIONS_GREEDY_JOIN_H_
#define SEARCH_DATALOG_TRANSFORMATIONS_GREEDY_JOIN_H_

#include "../../utils/system.h"
#include "../datalog_atom.h"

#include <limits>
#include <set>

namespace datalog {

enum { FAST_DOWNWARD, HELMERT_2009 };

class JoinCost {
    /*
     * This is not according to Helmert (2009), but according to the implementation of
     * Fast Downward.
     */
    int first_parameter;
    int second_parameter;
    int third_parameter;

public:
    JoinCost(int n, int max, int min, int mode = FAST_DOWNWARD)
    {
        if (mode == FAST_DOWNWARD) {
            first_parameter = min - n;
            second_parameter = max - n;
            third_parameter = -1 * n;
        }
        else if (mode == HELMERT_2009) {
            first_parameter = n - max;
            second_parameter = n - min;
            third_parameter = n;
        }
        else {
            std::cerr << "Using undefined JoinCost." << std::endl;
            utils::exit_with(utils::ExitCode::SEARCH_CRITICAL_ERROR);
        }
    }

    JoinCost()
        : first_parameter(std::numeric_limits<int>::max()),
          second_parameter(std::numeric_limits<int>::max()),
          third_parameter(std::numeric_limits<int>::max())
    {
    }


    friend bool operator<(const JoinCost &lhs, const JoinCost &rhs)
    {
        if (lhs.first_parameter != rhs.first_parameter) {
            return (lhs.first_parameter < rhs.first_parameter);
        }
        if (lhs.second_parameter != rhs.second_parameter) {
            return (lhs.second_parameter < rhs.second_parameter);
        }
        return (lhs.third_parameter < rhs.third_parameter);
    }

    friend bool operator==(const JoinCost &lhs, const JoinCost &rhs)
    {
        return (lhs.first_parameter == rhs.first_parameter) and
               (lhs.second_parameter == rhs.second_parameter) and
               (lhs.third_parameter == rhs.third_parameter);
    }

    friend bool operator<=(const JoinCost &lhs, const JoinCost &rhs)
    {
        return lhs < rhs or lhs == rhs;
    }
};

Arguments compute_joining_variables(const Arguments &head_args,
                                    const std::vector<DatalogAtom> &conditions,
                                    const DatalogAtom &atom1,
                                    const DatalogAtom &atom2);

JoinCost compute_join_cost_helmert2009(const Arguments &head_args,
                                       const std::vector<DatalogAtom> &conditions,
                                       const DatalogAtom &atom1,
                                       const DatalogAtom &atom2);

JoinCost compute_join_cost_fast_downward(const DatalogAtom &atom1,
                                         const DatalogAtom &atom2);

}  // namespace datalog

#endif  // SEARCH_DATALOG_TRANSFORMATIONS_GREEDY_JOIN_H_
