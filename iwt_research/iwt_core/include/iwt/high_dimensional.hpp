#pragma once

#include <cstdint>
#include <map>
#include <optional>
#include <vector>

namespace iwt {

/// Result of neighbor separation aggregation: mean and p99 per time step (paper: high-dimensional signature).
struct NeighborSeparationMetricsResult {
    int64_t rounds{0};
    int64_t pair_count{0};
    std::vector<double> mean_bit_hamming_distance_by_time;
    std::vector<double> p99_bit_hamming_distance_by_time;
    std::vector<double> mean_lane_difference_count_by_time;
    std::vector<double> p99_lane_difference_count_by_time;
};

/// Aggregate per-time-step lists into mean and p99. Used after Python collects bit_hamming and lane_difference per pair per time.
NeighborSeparationMetricsResult compute_neighbor_separation_aggregate(
    const std::vector<std::vector<int64_t>>& bit_hamming_distances_by_time,
    const std::vector<std::vector<int64_t>>& lane_difference_counts_by_time);

/// Result of lane coupling: per-source effective samples and coupling probability matrix.
struct LaneCouplingResult {
    int64_t lane_count{0};
    std::vector<int64_t> samples_per_source_lane_effective;
    std::vector<std::vector<double>> coupling_probability;
};

/// Build coupling matrix from list of (source_lane_index, list of target_lane indices where outputs differed).
LaneCouplingResult compute_lane_coupling_from_diffs(
    int64_t lane_count,
    const std::vector<std::pair<int64_t, std::vector<int64_t>>>& source_and_differing_targets);

/// Result of empirical reachability on a directed graph (BFS from sources).
struct EmpiricalReachabilityMetricsResult {
    int64_t node_count{0};
    int64_t directed_edge_count{0};
    int64_t source_node_count{0};
    int64_t reachable_node_count{0};
    int64_t unreachable_node_count{0};
    double unreachable_fraction{0.0};
    int64_t in_degree_zero_node_count{0};
    int64_t max_shortest_path_distance{0};
    double mean_shortest_path_distance{0.0};
};

/// Compute reachability from source indices on graph given as adjacency list (node index -> list of out-neighbor indices).
EmpiricalReachabilityMetricsResult compute_empirical_reachability_metrics(
    const std::vector<std::vector<int64_t>>& adjacency,
    const std::vector<int64_t>& source_indices);

/// Result of cycle decomposition for a bijection (permutation) functional graph.
struct CycleDecompositionMetricsResult {
    int64_t state_count{0};
    int64_t cycle_count{0};
    int64_t fixed_point_count{0};
    int64_t max_cycle_length{0};
    double mean_cycle_length{0.0};
    std::map<int64_t, int64_t> cycle_length_histogram;
};

/// Exact cycle decomposition of bijection on {0..state_count-1} via successor_table[i] = image of i.
CycleDecompositionMetricsResult compute_cycle_decomposition_metrics_for_bijection(
    const std::vector<int64_t>& successor_table,
    int64_t state_count);

/// One target result for reachability query: reachable and steps to first hit (if reachable).
struct ReachabilityQueryTargetResult {
    int64_t target_index{0};
    bool reachable_by_forward_iteration{false};
    std::optional<int64_t> steps_if_reachable;
};

/// Result of reachability queries on functional graph (one source, multiple targets).
struct ReachabilityQueriesResult {
    int64_t state_count{0};
    int64_t source_index{0};
    std::vector<ReachabilityQueryTargetResult> targets;
};

/// Exact reachability from source to each target by forward iteration (at most state_count steps).
ReachabilityQueriesResult compute_reachability_queries_on_functional_graph(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t source_index,
    const std::vector<int64_t>& target_indices);

/// Per-target result for reachability evidence (cycle info + path + cycle nodes for Python to hash).
struct ReachabilityEvidenceTargetResult {
    int64_t target_index{0};
    bool reachable_by_forward_iteration{false};
    std::optional<int64_t> steps_if_reachable;
    int64_t source_cycle_id{0};
    int64_t source_cycle_length{0};
    int64_t target_cycle_id{0};
    int64_t target_cycle_length{0};
    std::vector<int64_t> path_indices_head;
    std::vector<int64_t> source_cycle_nodes;
    std::vector<int64_t> target_cycle_nodes;
};

/// Core iteration and cycle/path data for evidence; Python builds SHA commitments and final dict.
std::vector<ReachabilityEvidenceTargetResult> compute_reachability_evidence_core(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t source_index,
    const std::vector<int64_t>& target_indices,
    int64_t max_witness_steps);

} // namespace iwt
