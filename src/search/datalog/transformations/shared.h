#ifndef SEARCH_DATALOG_TRANSFORMATIONS_SHARED_H_
#define SEARCH_DATALOG_TRANSFORMATIONS_SHARED_H_

#include "../datalog_atom.h"
#include "../../utils/collections.h"
#include "../rules/variable_source.h"
#include "../rules/rule_body_base.h"
#include "../../algorithms/priority_queues.h"

#include <set>
#include <vector>

// code shared between the normalization code of Datalog and DisjunctiveExistentialProgram

class Graph {
    std::vector<int> nodes;
    std::vector<std::vector<int>> edges;

    std::vector<int> dfs(int i, std::vector<bool> &visited) {
        visited[i] = true;
        std::vector<int> ret;
        ret.push_back(i);
        for (int j : edges[i]) {
            if (!visited[j]) {
                std::vector<int> tmp = dfs(j, visited);
                ret.insert(ret.end(), tmp.begin(), tmp.end());
            }
        }
        std::sort(ret.begin(), ret.end());
        return ret;
    }

public:

    Graph(int max) {
        // TODO: ???
        edges.resize(max);
        nodes.resize(0);
    }

    void add_node(int i) {
        nodes.push_back(i);
    }

    void add_edge(int i, int j) {
        edges[i].push_back(j);
    }

    std::vector<std::vector<int>> get_connected_components() {
        std::vector<std::vector<int>> components;
        std::vector<bool> visited(nodes.size(), false);
        for (size_t i = 0; i < nodes.size(); i++) {
            if (!visited[i]) {
                components.push_back(dfs(i, visited));
            }
        }
        return components;
    }

    std::vector<int> dijkstra(int start) {
        std::vector<int> dist(nodes.size(), std::numeric_limits<int>::max());
        dist[start] = 0;
        priority_queues::AdaptiveQueue<int> q;
        q.push(0, start);

        while(!q.empty()) {
            auto [d, u] = q.pop();
            if (d > dist[u]) continue;
            for (int v : edges[u]) {
                int nd = d + 1;
                if (nd < dist[v]) {
                    dist[v] = nd;
                    q.push(nd, v);
                }
            }
        }

        return dist;
    }

};


namespace datalog {

bool is_product_body(const std::vector<DatalogAtom> &conditions);

std::vector<DatalogAtom> select_conditions(std::vector<DatalogAtom> conditions, std::vector<int> indices);

Arguments get_relevant_joining_arguments(const Arguments &head_args, const std::vector<DatalogAtom> &selected_conditions,
                                         const std::vector<DatalogAtom> &all_conditions, const std::vector<int> selected_ids,
                                         const bool disconnected);

VariableSource update_source_after_component_split(VariableSource source_original_rule,
                                                   const std::vector<int> &component,
                                                   int component_counter,
                                                   const VariableSource &source_new_split_rule);

std::vector<std::vector<int>> get_components(RuleBodyBase &body);

DatalogAtom update_source_table(RuleBodyBase &body, int atom, int idx);

}

#endif //SEARCH_DATALOG_TRANSFORMATIONS_SHARED_H_
