#pragma once

#include <cstdint>
#include <vector>

namespace iwt {

/// Inversion count inv(π) = #{(i,j): i < j ∧ π(i) > π(j)}. O(n log n) Fenwick tree.
/// permutation must be 0..size-1 (or will be coordinate-compressed).
int64_t inversion_count_permutation(std::vector<int64_t> permutation);

/// Normalized inversion count in [0,1]: 2*inv / (q*(q-1)). Returns 0.0 if q <= 1.
inline double inversion_norm(int64_t inv_count, int64_t q) noexcept {
    if (q <= 1) return 0.0;
    return 2.0 * static_cast<double>(inv_count) / (static_cast<double>(q) * (q - 1));
}

/// Parity of inversion count: 0 even, 1 odd.
inline int inv_parity(int64_t inv_count) noexcept {
    return static_cast<int>(inv_count % 2);
}

/// Permutation cycle decomposition: permutation[i] = image of i. Returns list of cycles (each cycle = list of indices).
std::vector<std::vector<int64_t>> permutation_cycles(const std::vector<int64_t>& permutation);

/// Cycle stats for P-box: cycle_count, cycle_lengths (descending), max_cycle_length, fixed_point_count.
/// If permutation is invalid (out-of-range element), returns zeros.
struct CycleStatsResult {
    int64_t cycle_count{0};
    std::vector<int64_t> cycle_lengths;
    int64_t max_cycle_length{0};
    int64_t fixed_point_count{0};
};
CycleStatsResult cycle_stats(const std::vector<int64_t>& permutation);

} // namespace iwt
