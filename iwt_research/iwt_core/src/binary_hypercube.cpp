#include "iwt/binary_hypercube.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace iwt {

namespace {

using Vertex = BinaryVertex;

Vertex normalize_binary_vertex(const Vertex& vertex, int dimension) {
    if (static_cast<int>(vertex.size()) != dimension)
        return {};
    Vertex out;
    out.reserve(static_cast<size_t>(dimension));
    for (int i = 0; i < dimension; ++i) {
        int64_t v = vertex[static_cast<size_t>(i)];
        out.push_back((v != 0) ? 1 : 0);
    }
    return out;
}

int64_t hamming_distance(const Vertex& a, const Vertex& b) {
    if (a.size() != b.size()) return -1;
    int64_t d = 0;
    for (size_t i = 0; i < a.size(); ++i)
        if (a[i] != b[i]) ++d;
    return d;
}

int64_t hamming_weight(const Vertex& v) {
    int64_t w = 0;
    for (int64_t x : v) w += x;
    return w;
}

bool vertex_less(const Vertex& a, const Vertex& b) {
    if (a.size() != b.size()) return a.size() < b.size();
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) return a[i] < b[i];
    }
    return false;
}

} // namespace

BinaryHypercubeMetricsResult compute_binary_hypercube_metrics(
    int dimension,
    const std::vector<AdjacencyEntry>& adjacency) {
    BinaryHypercubeMetricsResult result;
    result.dimension = dimension;
    result.full_node_count = (dimension <= 0) ? 0 : (int64_t{1} << dimension);

    if (dimension <= 0)
        return result;

    std::map<Vertex, std::vector<Vertex>, bool (*)(const Vertex&, const Vertex&)> normalized_adjacency(vertex_less);
    std::set<Vertex, bool (*)(const Vertex&, const Vertex&)> nodes(vertex_less);

    for (const auto& entry : adjacency) {
        const Vertex& source_raw = entry.first;
        const std::vector<Vertex>& targets_raw = entry.second;
        Vertex source_n = normalize_binary_vertex(source_raw, dimension);
        if (source_n.empty()) continue;
        nodes.insert(source_n);
        std::vector<Vertex> normalized_targets;
        for (const auto& t : targets_raw) {
            Vertex t_n = normalize_binary_vertex(t, dimension);
            if (t_n.empty()) continue;
            nodes.insert(t_n);
            normalized_targets.push_back(std::move(t_n));
        }
        normalized_adjacency[source_n] = std::move(normalized_targets);
    }

    int64_t edge_count = 0;
    int64_t zero_hamming_edges = 0;
    int64_t one_hamming_edges = 0;
    int64_t multi_hamming_edges = 0;
    int64_t hamming_sum = 0;
    int64_t hamming_max = 0;
    std::vector<int64_t> axis_flip_counts(static_cast<size_t>(dimension), 0);
    std::map<std::string, int64_t> edge_hamming_histogram;

    for (const auto& [source, targets] : normalized_adjacency) {
        for (const auto& target : targets) {
            int64_t d = hamming_distance(source, target);
            if (d < 0) continue;
            ++edge_count;
            hamming_sum += d;
            if (d > hamming_max) hamming_max = d;
            std::string d_key = std::to_string(d);
            edge_hamming_histogram[d_key] = edge_hamming_histogram[d_key] + 1;
            if (d == 0) {
                ++zero_hamming_edges;
                continue;
            }
            if (d == 1) {
                ++one_hamming_edges;
                for (int axis = 0; axis < dimension; ++axis) {
                    if (source[static_cast<size_t>(axis)] != target[static_cast<size_t>(axis)]) {
                        axis_flip_counts[static_cast<size_t>(axis)] += 1;
                        break;
                    }
                }
                continue;
            }
            ++multi_hamming_edges;
        }
    }

    std::map<std::string, int64_t> hamming_weight_histogram;
    for (const auto& node : nodes) {
        int64_t w = hamming_weight(node);
        std::string w_key = std::to_string(w);
        hamming_weight_histogram[w_key] = hamming_weight_histogram[w_key] + 1;
    }

    result.observed_node_count = static_cast<int64_t>(nodes.size());
    result.observed_coverage_fraction = (result.full_node_count > 0)
        ? static_cast<double>(result.observed_node_count) / static_cast<double>(result.full_node_count)
        : 0.0;
    result.observed_directed_edge_count = edge_count;
    result.edge_hamming_distance_histogram = std::move(edge_hamming_histogram);
    result.hamming_weight_histogram = std::move(hamming_weight_histogram);
    result.axis_flip_counts = std::move(axis_flip_counts);
    result.max_edge_hamming_distance = hamming_max;

    if (edge_count > 0) {
        result.mean_edge_hamming_distance = static_cast<double>(hamming_sum) / static_cast<double>(edge_count);
        result.zero_hamming_edge_fraction = static_cast<double>(zero_hamming_edges) / static_cast<double>(edge_count);
        result.one_hamming_edge_fraction = static_cast<double>(one_hamming_edges) / static_cast<double>(edge_count);
        result.multi_hamming_edge_fraction = static_cast<double>(multi_hamming_edges) / static_cast<double>(edge_count);
    }
    if (one_hamming_edges > 0) {
        double expected = static_cast<double>(one_hamming_edges) / static_cast<double>(dimension);
        double l1_sum = 0;
        for (int64_t count : result.axis_flip_counts)
            l1_sum += std::abs(static_cast<double>(count) - expected);
        result.axis_flip_balance_l1 = l1_sum / static_cast<double>(one_hamming_edges);
    }

    return result;
}

} // namespace iwt
