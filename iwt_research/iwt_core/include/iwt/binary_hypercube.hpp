#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace iwt {

/// Result of binary hypercube metrics: exact geometry summary on observed directed graph over {0,1}^n.
struct BinaryHypercubeMetricsResult {
    int dimension{0};
    int64_t full_node_count{0};
    int64_t observed_node_count{0};
    double observed_coverage_fraction{0.0};
    int64_t observed_directed_edge_count{0};
    double zero_hamming_edge_fraction{0.0};
    double one_hamming_edge_fraction{0.0};
    double multi_hamming_edge_fraction{0.0};
    double mean_edge_hamming_distance{0.0};
    int64_t max_edge_hamming_distance{0};
    std::vector<int64_t> axis_flip_counts;
    double axis_flip_balance_l1{0.0};
    std::map<std::string, int64_t> hamming_weight_histogram;
    std::map<std::string, int64_t> edge_hamming_distance_histogram;
};

/// Adjacency entry: one source vertex and its list of target vertices. Each vertex is 0/1 of length dimension.
using BinaryVertex = std::vector<int64_t>;
using AdjacencyEntry = std::pair<BinaryVertex, std::vector<BinaryVertex>>;

/// Compute binary hypercube metrics. Dimension must be positive; domain must be binary (caller checks).
/// adjacency: list of (source_vertex, list of target_vertices); vertices normalized to 0/1, length dimension.
BinaryHypercubeMetricsResult compute_binary_hypercube_metrics(
    int dimension,
    const std::vector<AdjacencyEntry>& adjacency);

} // namespace iwt
