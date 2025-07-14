#include "iwt/rho_analysis.hpp"
#include <algorithm>
#include <set>
#include <unordered_map>
#include <vector>

namespace iwt {

namespace {

RhoStructureMetricsResult empty_metrics() {
    return RhoStructureMetricsResult{};
}

} // namespace

RhoStructureMetricsResult compute_rho_structure(
    const std::vector<int64_t>& successor_table,
    int64_t state_count) {

    const int64_t n = state_count;
    if (n <= 0 || successor_table.size() < static_cast<size_t>(n))
        return empty_metrics();

    std::vector<int64_t> succ(static_cast<size_t>(n));
    std::vector<int64_t> in_deg(static_cast<size_t>(n), 0);
    std::set<int64_t> image_set;

    for (int64_t x = 0; x < n; ++x) {
        int64_t y = successor_table[static_cast<size_t>(x)];
        if (y < 0 || y >= n)
            y = ((y % n) + n) % n;
        succ[static_cast<size_t>(x)] = y;
        in_deg[static_cast<size_t>(y)]++;
        image_set.insert(y);
    }

    RhoStructureMetricsResult result;
    result.state_count = n;
    result.image_count = static_cast<int64_t>(image_set.size());
    result.collision_count = n - result.image_count;

    std::vector<bool> on_cycle(static_cast<size_t>(n), false);
    std::vector<int> visited(static_cast<size_t>(n), 0); // 0=unvisited, 1=in-progress, 2=done

    for (int64_t start = 0; start < n; ++start) {
        if (visited[static_cast<size_t>(start)] == 2)
            continue;

        std::vector<int64_t> path;
        std::unordered_map<int64_t, size_t> path_set;
        int64_t node = start;

        while (visited[static_cast<size_t>(node)] == 0 && path_set.count(node) == 0) {
            path_set[node] = path.size();
            path.push_back(node);
            visited[static_cast<size_t>(node)] = 1;
            node = succ[static_cast<size_t>(node)];
        }

        if (visited[static_cast<size_t>(node)] == 1 && path_set.count(node) != 0) {
            size_t cycle_start_idx = path_set[node];
            for (size_t i = cycle_start_idx; i < path.size(); ++i)
                on_cycle[static_cast<size_t>(path[i])] = true;
        }

        for (int64_t p : path)
            visited[static_cast<size_t>(p)] = 2;
    }

    int64_t total_cycle_nodes = 0;
    for (int64_t i = 0; i < n; ++i) {
        if (on_cycle[static_cast<size_t>(i)])
            total_cycle_nodes++;
    }
    result.total_cycle_nodes = total_cycle_nodes;
    result.tail_node_count = n - total_cycle_nodes;

    std::vector<bool> cycle_visited(static_cast<size_t>(n), false);
    std::vector<int64_t> cycle_lengths;
    for (int64_t node = 0; node < n; ++node) {
        if (!on_cycle[static_cast<size_t>(node)] || cycle_visited[static_cast<size_t>(node)])
            continue;
        int64_t length = 0;
        int64_t cur = node;
        while (!cycle_visited[static_cast<size_t>(cur)]) {
            cycle_visited[static_cast<size_t>(cur)] = true;
            length++;
            cur = succ[static_cast<size_t>(cur)];
        }
        cycle_lengths.push_back(length);
    }

    result.cycle_count = static_cast<int64_t>(cycle_lengths.size());
    for (int64_t cl : cycle_lengths)
        result.cycle_length_histogram[cl]++;

    std::vector<int64_t> tail_length(static_cast<size_t>(n), -1);
    for (int64_t i = 0; i < n; ++i) {
        if (on_cycle[static_cast<size_t>(i)])
            tail_length[static_cast<size_t>(i)] = 0;
    }

    bool changed = true;
    while (changed) {
        changed = false;
        for (int64_t i = 0; i < n; ++i) {
            if (tail_length[static_cast<size_t>(i)] >= 0)
                continue;
            int64_t s = succ[static_cast<size_t>(i)];
            if (tail_length[static_cast<size_t>(s)] >= 0) {
                tail_length[static_cast<size_t>(i)] = tail_length[static_cast<size_t>(s)] + 1;
                changed = true;
            }
        }
    }

    for (int64_t i = 0; i < n; ++i) {
        if (tail_length[static_cast<size_t>(i)] < 0)
            tail_length[static_cast<size_t>(i)] = n;
    }

    for (int64_t i = 0; i < n; ++i) {
        if (!on_cycle[static_cast<size_t>(i)])
            result.tail_length_histogram[tail_length[static_cast<size_t>(i)]]++;
    }

    result.max_tail_length = 0;
    int64_t sum_tail = 0;
    for (int64_t i = 0; i < n; ++i) {
        if (!on_cycle[static_cast<size_t>(i)]) {
            int64_t tl = tail_length[static_cast<size_t>(i)];
            if (tl > result.max_tail_length)
                result.max_tail_length = tl;
            sum_tail += tl;
        }
    }
    result.mean_tail_length = (result.tail_node_count > 0)
        ? (static_cast<double>(sum_tail) / static_cast<double>(result.tail_node_count))
        : 0.0;

    result.max_in_degree = 0;
    for (int64_t i = 0; i < n; ++i) {
        int64_t d = in_deg[static_cast<size_t>(i)];
        result.in_degree_histogram[d]++;
        if (d > result.max_in_degree)
            result.max_in_degree = d;
    }

    std::set<int64_t> tree_roots;
    for (int64_t i = 0; i < n; ++i) {
        if (on_cycle[static_cast<size_t>(i)] && in_deg[static_cast<size_t>(i)] > 1) {
            tree_roots.insert(i);
        } else if (on_cycle[static_cast<size_t>(i)]) {
            bool has_tail_child = false;
            for (int64_t j = 0; j < n; ++j) {
                if (succ[static_cast<size_t>(j)] == i && !on_cycle[static_cast<size_t>(j)]) {
                    has_tail_child = true;
                    break;
                }
            }
            if (has_tail_child)
                tree_roots.insert(i);
        }
    }
    result.tree_count = static_cast<int64_t>(tree_roots.size());

    return result;
}

} // namespace iwt
