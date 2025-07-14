#include "iwt/high_dimensional.hpp"
#include "iwt/inversions.hpp"
#include <algorithm>
#include <cmath>
#include <queue>
#include <unordered_map>
#include <unordered_set>

namespace iwt {

namespace {

double p99_from_sorted(std::vector<int64_t>& values) {
    if (values.empty()) return 0.0;
    std::sort(values.begin(), values.end());
    size_t index = (values.size() > 1)
        ? static_cast<size_t>(std::floor(0.99 * (static_cast<double>(values.size()) - 1.0)))
        : 0;
    return static_cast<double>(values[index]);
}

double mean_of_int64(const std::vector<int64_t>& values) {
    if (values.empty()) return 0.0;
    int64_t sum = 0;
    for (int64_t v : values) sum += v;
    return static_cast<double>(sum) / static_cast<double>(values.size());
}

} // namespace

NeighborSeparationMetricsResult compute_neighbor_separation_aggregate(
    const std::vector<std::vector<int64_t>>& bit_hamming_distances_by_time,
    const std::vector<std::vector<int64_t>>& lane_difference_counts_by_time) {

    NeighborSeparationMetricsResult result;
    size_t time_length = bit_hamming_distances_by_time.size();
    if (time_length != lane_difference_counts_by_time.size() || time_length == 0) {
        result.rounds = 0;
        result.pair_count = 0;
        return result;
    }

    result.pair_count = time_length > 0 && !bit_hamming_distances_by_time[0].empty()
        ? static_cast<int64_t>(bit_hamming_distances_by_time[0].size()) : 0;
    result.rounds = static_cast<int64_t>(time_length) - 1;
    if (result.rounds < 0) result.rounds = 0;

    result.mean_bit_hamming_distance_by_time.resize(time_length);
    result.p99_bit_hamming_distance_by_time.resize(time_length);
    result.mean_lane_difference_count_by_time.resize(time_length);
    result.p99_lane_difference_count_by_time.resize(time_length);

    for (size_t t = 0; t < time_length; ++t) {
        std::vector<int64_t> bit_vec = bit_hamming_distances_by_time[t];
        std::vector<int64_t> lane_vec = lane_difference_counts_by_time[t];

        result.mean_bit_hamming_distance_by_time[t] = mean_of_int64(bit_vec);
        result.p99_bit_hamming_distance_by_time[t] = p99_from_sorted(bit_vec);
        result.mean_lane_difference_count_by_time[t] = mean_of_int64(lane_vec);
        result.p99_lane_difference_count_by_time[t] = p99_from_sorted(lane_vec);
    }
    return result;
}

LaneCouplingResult compute_lane_coupling_from_diffs(
    int64_t lane_count,
    const std::vector<std::pair<int64_t, std::vector<int64_t>>>& source_and_differing_targets) {

    LaneCouplingResult result;
    result.lane_count = lane_count;
    if (lane_count <= 0) return result;

    std::vector<std::vector<int64_t>> counts(static_cast<size_t>(lane_count),
        std::vector<int64_t>(static_cast<size_t>(lane_count), 0));
    std::vector<int64_t> totals(static_cast<size_t>(lane_count), 0);

    for (const auto& entry : source_and_differing_targets) {
        int64_t source_lane = entry.first;
        if (source_lane < 0 || source_lane >= lane_count) continue;
        totals[static_cast<size_t>(source_lane)]++;
        for (int64_t target_lane : entry.second) {
            if (target_lane >= 0 && target_lane < lane_count)
                counts[static_cast<size_t>(source_lane)][static_cast<size_t>(target_lane)]++;
        }
    }

    result.samples_per_source_lane_effective = totals;
    result.coupling_probability.resize(static_cast<size_t>(lane_count));
    for (int64_t source = 0; source < lane_count; ++source) {
        int64_t denom = std::max(int64_t(1), totals[static_cast<size_t>(source)]);
        result.coupling_probability[static_cast<size_t>(source)].resize(static_cast<size_t>(lane_count));
        for (int64_t target = 0; target < lane_count; ++target) {
            result.coupling_probability[static_cast<size_t>(source)][static_cast<size_t>(target)] =
                static_cast<double>(counts[static_cast<size_t>(source)][static_cast<size_t>(target)]) / static_cast<double>(denom);
        }
    }
    return result;
}

EmpiricalReachabilityMetricsResult compute_empirical_reachability_metrics(
    const std::vector<std::vector<int64_t>>& adjacency,
    const std::vector<int64_t>& source_indices) {

    EmpiricalReachabilityMetricsResult result;
    size_t node_count = adjacency.size();
    if (node_count == 0) {
        result.source_node_count = static_cast<int64_t>(source_indices.size());
        return result;
    }

    result.node_count = static_cast<int64_t>(node_count);
    result.source_node_count = static_cast<int64_t>(source_indices.size());

    std::vector<int64_t> in_degree(node_count, 0);
    int64_t directed_edge_count = 0;
    for (size_t i = 0; i < adjacency.size(); ++i) {
        for (int64_t target : adjacency[i]) {
            if (target >= 0 && target < static_cast<int64_t>(node_count)) {
                in_degree[static_cast<size_t>(target)]++;
                directed_edge_count++;
            }
        }
    }
    result.directed_edge_count = directed_edge_count;

    int64_t in_degree_zero_count = 0;
    for (size_t i = 0; i < node_count; ++i) {
        if (in_degree[i] == 0) in_degree_zero_count++;
    }
    result.in_degree_zero_node_count = in_degree_zero_count;

    std::vector<int64_t> distance(node_count, -1);
    std::queue<int64_t> frontier;
    for (int64_t src : source_indices) {
        if (src >= 0 && src < static_cast<int64_t>(node_count) && distance[static_cast<size_t>(src)] < 0) {
            distance[static_cast<size_t>(src)] = 0;
            frontier.push(src);
        }
    }

    while (!frontier.empty()) {
        int64_t node = frontier.front();
        frontier.pop();
        int64_t next_dist = distance[static_cast<size_t>(node)] + 1;
        for (int64_t neighbor : adjacency[static_cast<size_t>(node)]) {
            if (neighbor < 0 || neighbor >= static_cast<int64_t>(node_count)) continue;
            if (distance[static_cast<size_t>(neighbor)] >= 0) continue;
            distance[static_cast<size_t>(neighbor)] = next_dist;
            frontier.push(neighbor);
        }
    }

    int64_t reachable_count = 0;
    int64_t max_dist = 0;
    int64_t sum_dist = 0;
    int64_t dist_count = 0;
    for (size_t i = 0; i < node_count; ++i) {
        if (distance[i] >= 0) {
            reachable_count++;
            max_dist = std::max(max_dist, distance[i]);
            sum_dist += distance[i];
            dist_count++;
        }
    }
    result.reachable_node_count = reachable_count;
    result.unreachable_node_count = static_cast<int64_t>(node_count) - reachable_count;
    result.unreachable_fraction = (node_count > 0)
        ? (static_cast<double>(result.unreachable_node_count) / static_cast<double>(node_count))
        : 0.0;
    result.max_shortest_path_distance = max_dist;
    result.mean_shortest_path_distance = (dist_count > 0)
        ? (static_cast<double>(sum_dist) / static_cast<double>(dist_count))
        : 0.0;
    return result;
}

CycleDecompositionMetricsResult compute_cycle_decomposition_metrics_for_bijection(
    const std::vector<int64_t>& successor_table,
    int64_t state_count) {

    CycleDecompositionMetricsResult result;
    if (state_count <= 0 || successor_table.size() < static_cast<size_t>(state_count))
        return result;

    result.state_count = state_count;
    CycleStatsResult stats = cycle_stats(successor_table);
    result.cycle_count = stats.cycle_count;
    result.fixed_point_count = stats.fixed_point_count;
    result.max_cycle_length = stats.max_cycle_length;

    if (stats.cycle_lengths.empty()) {
        result.mean_cycle_length = 0.0;
        return result;
    }
    int64_t sum_len = 0;
    for (int64_t len : stats.cycle_lengths) {
        sum_len += len;
        result.cycle_length_histogram[len]++;
    }
    result.mean_cycle_length = static_cast<double>(sum_len) / static_cast<double>(stats.cycle_lengths.size());
    return result;
}

ReachabilityQueriesResult compute_reachability_queries_on_functional_graph(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t source_index,
    const std::vector<int64_t>& target_indices) {

    ReachabilityQueriesResult result;
    result.state_count = state_count;
    result.source_index = source_index;
    if (state_count <= 0 || source_index < 0 || source_index >= state_count ||
        successor_table.size() < static_cast<size_t>(state_count)) {
        for (int64_t t : target_indices) {
            ReachabilityQueryTargetResult tr;
            tr.target_index = t;
            tr.reachable_by_forward_iteration = false;
            tr.steps_if_reachable = std::nullopt;
            result.targets.push_back(tr);
        }
        return result;
    }

    std::unordered_map<int64_t, int64_t> hits;
    std::unordered_set<int64_t> target_set(target_indices.begin(), target_indices.end());
    int64_t current = source_index;
    for (int64_t step = 0; step <= state_count; ++step) {
        if (target_set.count(current) && !hits.count(current)) {
            hits[current] = step;
            if (hits.size() == target_set.size()) break;
        }
        current = successor_table[static_cast<size_t>(current)];
        if (current < 0 || current >= state_count) break;
        if (current == source_index) break;
    }

    for (int64_t target : target_indices) {
        ReachabilityQueryTargetResult tr;
        tr.target_index = target;
        if (target < 0 || target >= state_count) {
            tr.reachable_by_forward_iteration = false;
            tr.steps_if_reachable = std::nullopt;
        } else {
            auto it = hits.find(target);
            if (it != hits.end()) {
                tr.reachable_by_forward_iteration = true;
                tr.steps_if_reachable = it->second;
            } else {
                tr.reachable_by_forward_iteration = false;
                tr.steps_if_reachable = std::nullopt;
            }
        }
        result.targets.push_back(tr);
    }
    return result;
}

namespace {

std::pair<int64_t, int64_t> cycle_info_for_index(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t index,
    std::unordered_map<int64_t, std::pair<int64_t, int64_t>>& cache) {
    auto it = cache.find(index);
    if (it != cache.end()) return it->second;
    std::unordered_map<int64_t, size_t> seen_at;
    std::vector<int64_t> order;
    int64_t current = index;
    for (;;) {
        if (current < 0 || current >= state_count) break;
        auto jt = seen_at.find(current);
        if (jt != seen_at.end()) {
            size_t start = jt->second;
            std::vector<int64_t> cycle_nodes(order.begin() + static_cast<std::ptrdiff_t>(start), order.end());
            if (cycle_nodes.empty()) cycle_nodes.push_back(current);
            int64_t cycle_id = *std::min_element(cycle_nodes.begin(), cycle_nodes.end());
            int64_t cycle_len = static_cast<int64_t>(cycle_nodes.size());
            for (int64_t node : cycle_nodes) cache[node] = {cycle_id, cycle_len};
            if (!cache.count(index)) cache[index] = {cycle_id, cycle_len};
            return {cycle_id, cycle_len};
        }
        seen_at[current] = order.size();
        order.push_back(current);
        current = successor_table[static_cast<size_t>(current)];
    }
    return {0, 0};
}

std::vector<int64_t> cycle_nodes_from_id(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t cycle_id,
    int64_t cycle_length) {
    std::vector<int64_t> out;
    int64_t current = cycle_id;
    for (int64_t i = 0; i < cycle_length && current >= 0 && current < state_count; ++i) {
        out.push_back(current);
        current = successor_table[static_cast<size_t>(current)];
    }
    return out;
}

} // namespace

std::vector<ReachabilityEvidenceTargetResult> compute_reachability_evidence_core(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t source_index,
    const std::vector<int64_t>& target_indices,
    int64_t max_witness_steps) {

    std::vector<ReachabilityEvidenceTargetResult> out;
    if (state_count <= 0 || source_index < 0 || source_index >= state_count ||
        successor_table.size() < static_cast<size_t>(state_count)) {
        for (int64_t t : target_indices) {
            ReachabilityEvidenceTargetResult r;
            r.target_index = t;
            out.push_back(r);
        }
        return out;
    }

    std::unordered_map<int64_t, std::pair<int64_t, int64_t>> cycle_cache;
    std::pair<int64_t, int64_t> source_cycle = cycle_info_for_index(successor_table, state_count, source_index, cycle_cache);
    int64_t source_cycle_id = source_cycle.first;
    int64_t source_cycle_length = source_cycle.second;
    std::vector<int64_t> source_cycle_nodes = cycle_nodes_from_id(successor_table, state_count, source_cycle_id, source_cycle_length);

    for (int64_t target : target_indices) {
        ReachabilityEvidenceTargetResult r;
        r.target_index = target;
        r.source_cycle_id = source_cycle_id;
        r.source_cycle_length = source_cycle_length;
        r.source_cycle_nodes = source_cycle_nodes;

        if (target < 0 || target >= state_count) {
            r.target_cycle_id = 0;
            r.target_cycle_length = 0;
            out.push_back(r);
            continue;
        }

        std::pair<int64_t, int64_t> target_cycle = cycle_info_for_index(successor_table, state_count, target, cycle_cache);
        r.target_cycle_id = target_cycle.first;
        r.target_cycle_length = target_cycle.second;
        r.target_cycle_nodes = cycle_nodes_from_id(successor_table, state_count, r.target_cycle_id, r.target_cycle_length);

        bool same_cycle = (r.target_cycle_id == source_cycle_id);
        r.reachable_by_forward_iteration = same_cycle;

        if (same_cycle) {
            int64_t current = source_index;
            for (int64_t step = 0; step <= state_count; ++step) {
                if (step <= max_witness_steps)
                    r.path_indices_head.push_back(current);
                if (current == target) {
                    r.steps_if_reachable = step;
                    break;
                }
                current = successor_table[static_cast<size_t>(current)];
                if (current == source_index) break;
            }
        }
        out.push_back(r);
    }
    return out;
}

} // namespace iwt
