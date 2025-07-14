#pragma once

#include <cstdint>
#include <map>
#include <vector>

namespace iwt {

/// Result of collision metrics. Paper: collision_count, preimage distribution.
struct CollisionMetricsResult {
    int64_t state_count{0};
    int64_t image_count{0};
    int64_t collision_pair_count{0};
    int64_t max_preimage_size{0};
    double mean_preimage_size{0.0};
    std::map<int64_t, int64_t> preimage_size_histogram;
    std::map<int64_t, int64_t> multi_collision_counts;
};

/// Result of merge depth metrics. Paper: mean_merge_depth.
struct MergeDepthMetricsResult {
    int64_t pair_count{0};
    double mean_merge_depth{0.0};
    int64_t max_merge_depth{0};
    double merged_fraction{0.0};
    std::map<int64_t, int64_t> merge_depth_histogram;
};

/// Result of avalanche metrics.
struct AvalancheMetricsResult {
    int64_t bit_width{0};
    int64_t pair_count{0};
    double mean_hamming_distance{0.0};
    double mean_hamming_fraction{0.0};
    int64_t min_hamming_distance{0};
    int64_t max_hamming_distance{0};
};

/// Compute collision metrics from successor table. Paper: collision_count, preimage.
CollisionMetricsResult compute_collision_metrics(
    const std::vector<int64_t>& successor_table,
    int64_t state_count);

/// Compute merge depth: initial_pairs are (a, b); iterate successor until they meet.
MergeDepthMetricsResult compute_merge_depth(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    const std::vector<std::pair<int64_t, int64_t>>& initial_pairs,
    int64_t max_steps);

/// Compute avalanche: for each input in input_sample, flip each bit, Hamming distance of outputs.
AvalancheMetricsResult compute_avalanche(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t bit_width,
    const std::vector<int64_t>& input_sample);

} // namespace iwt
