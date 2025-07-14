#include "iwt/collision_metrics.hpp"
#include <algorithm>
#include <cmath>
#include <map>
#include <unordered_map>
#include <vector>

namespace iwt {

namespace {

int64_t popcount(uint64_t v) {
    int64_t c = 0;
    while (v) { c += (v & 1); v >>= 1; }
    return c;
}

} // namespace

CollisionMetricsResult compute_collision_metrics(
    const std::vector<int64_t>& successor_table,
    int64_t state_count) {

    CollisionMetricsResult result;
    const int64_t n = state_count;
    if (n <= 0 || successor_table.size() < static_cast<size_t>(n))
        return result;

    result.state_count = n;
    std::unordered_map<int64_t, std::vector<int64_t>> preimage_lists;

    for (int64_t x = 0; x < n; ++x) {
        int64_t y = successor_table[static_cast<size_t>(x)];
        if (y < 0 || y >= n)
            y = ((y % n) + n) % n;
        preimage_lists[y].push_back(x);
    }

    result.image_count = static_cast<int64_t>(preimage_lists.size());

    int64_t collision_pair_count = 0;
    std::vector<int64_t> preimage_sizes;
    for (const auto& kv : preimage_lists) {
        int64_t k = static_cast<int64_t>(kv.second.size());
        preimage_sizes.push_back(k);
        if (k >= 2)
            collision_pair_count += k * (k - 1) / 2;
    }
    result.collision_pair_count = collision_pair_count;

    if (preimage_sizes.empty()) {
        result.max_preimage_size = 0;
        result.mean_preimage_size = 0.0;
        return result;
    }

    result.max_preimage_size = *std::max_element(preimage_sizes.begin(), preimage_sizes.end());
    int64_t sum_preimage = 0;
    for (int64_t s : preimage_sizes)
        sum_preimage += s;
    result.mean_preimage_size = static_cast<double>(sum_preimage) / static_cast<double>(preimage_sizes.size());

    for (int64_t s : preimage_sizes)
        result.preimage_size_histogram[s]++;

    const std::vector<int64_t> thresholds = {2, 3, 4, 5, 8, 16};
    for (int64_t k_threshold : thresholds) {
        int64_t count = 0;
        for (int64_t s : preimage_sizes) {
            if (s >= k_threshold) count++;
        }
        if (count > 0)
            result.multi_collision_counts[k_threshold] = count;
    }

    return result;
}

MergeDepthMetricsResult compute_merge_depth(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    const std::vector<std::pair<int64_t, int64_t>>& initial_pairs,
    int64_t max_steps) {

    MergeDepthMetricsResult result;
    const int64_t n = state_count;
    if (n <= 0 || successor_table.size() < static_cast<size_t>(n) || max_steps <= 0)
        return result;

    result.pair_count = static_cast<int64_t>(initial_pairs.size());
    if (result.pair_count == 0) return result;

    std::vector<int64_t> depths;
    int64_t merged_count = 0;

    for (const auto& p : initial_pairs) {
        int64_t ca = p.first;
        int64_t cb = p.second;
        if (ca < 0 || ca >= n) ca = ((ca % n) + n) % n;
        if (cb < 0 || cb >= n) cb = ((cb % n) + n) % n;

        int64_t depth = 0;
        bool found = false;
        for (int64_t step = 0; step < max_steps; ++step) {
            if (ca == cb) { found = true; break; }
            ca = successor_table[static_cast<size_t>(ca)];
            cb = successor_table[static_cast<size_t>(cb)];
            if (ca < 0 || ca >= n) ca = ((ca % n) + n) % n;
            if (cb < 0 || cb >= n) cb = ((cb % n) + n) % n;
            depth++;
        }
        if (found) {
            depths.push_back(depth);
            merged_count++;
        }
    }

    result.merged_fraction = static_cast<double>(merged_count) / static_cast<double>(result.pair_count);
    if (depths.empty()) {
        result.mean_merge_depth = 0.0;
        result.max_merge_depth = 0;
        return result;
    }
    int64_t sum_d = 0;
    for (int64_t d : depths) {
        sum_d += d;
        result.merge_depth_histogram[d]++;
    }
    result.mean_merge_depth = static_cast<double>(sum_d) / static_cast<double>(depths.size());
    result.max_merge_depth = *std::max_element(depths.begin(), depths.end());
    return result;
}

AvalancheMetricsResult compute_avalanche(
    const std::vector<int64_t>& successor_table,
    int64_t state_count,
    int64_t bit_width,
    const std::vector<int64_t>& input_sample) {

    AvalancheMetricsResult result;
    result.bit_width = bit_width;
    const int64_t n = state_count;
    if (n <= 0 || successor_table.size() < static_cast<size_t>(n) || bit_width <= 0)
        return result;

    std::vector<int64_t> distances;
    for (int64_t x : input_sample) {
        if (x < 0 || x >= n) continue;
        int64_t y = successor_table[static_cast<size_t>(x)];
        if (y < 0 || y >= n) y = ((y % n) + n) % n;
        for (int64_t bit = 0; bit < bit_width; ++bit) {
            int64_t x_flipped = x ^ (1LL << bit);
            if (x_flipped < 0 || x_flipped >= n) continue;
            int64_t y_flipped = successor_table[static_cast<size_t>(x_flipped)];
            if (y_flipped < 0 || y_flipped >= n) y_flipped = ((y_flipped % n) + n) % n;
            uint64_t xor_val = static_cast<uint64_t>(y ^ y_flipped);
            distances.push_back(popcount(xor_val));
        }
    }

    result.pair_count = static_cast<int64_t>(distances.size());
    if (distances.empty()) {
        result.mean_hamming_distance = 0.0;
        result.mean_hamming_fraction = 0.0;
        result.min_hamming_distance = 0;
        result.max_hamming_distance = 0;
        return result;
    }
    int64_t sum_hd = 0;
    for (int64_t d : distances) sum_hd += d;
    result.mean_hamming_distance = static_cast<double>(sum_hd) / static_cast<double>(distances.size());
    result.mean_hamming_fraction = (bit_width > 0) ? (result.mean_hamming_distance / static_cast<double>(bit_width)) : 0.0;
    result.min_hamming_distance = *std::min_element(distances.begin(), distances.end());
    result.max_hamming_distance = *std::max_element(distances.begin(), distances.end());
    return result;
}

} // namespace iwt
