#pragma once

#include <cstdint>
#include <map>
#include <vector>

namespace iwt {

/// Result of rho-structure decomposition for f: {0..state_count-1} -> {0..state_count-1}.
/// Paper: cycle/tail/in_degree; names match Python and paper (no abbreviations).
struct RhoStructureMetricsResult {
    int64_t state_count{0};
    int64_t image_count{0};
    int64_t collision_count{0};
    int64_t cycle_count{0};
    std::map<int64_t, int64_t> cycle_length_histogram;
    int64_t total_cycle_nodes{0};
    int64_t tail_node_count{0};
    std::map<int64_t, int64_t> tail_length_histogram;
    int64_t max_tail_length{0};
    double mean_tail_length{0.0};
    int64_t max_in_degree{0};
    std::map<int64_t, int64_t> in_degree_histogram;
    int64_t tree_count{0};
};

/// Compute rho-structure metrics from a full successor table.
/// successor_table[i] = image of state i (f(i)); indices in [0, state_count-1] or normalized with % state_count.
RhoStructureMetricsResult compute_rho_structure(
    const std::vector<int64_t>& successor_table,
    int64_t state_count);

} // namespace iwt
