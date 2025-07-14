#include "iwt/inversions.hpp"
#include <algorithm>
#include <cstdint>
#include <set>
#include <unordered_map>
#include <vector>

namespace iwt {

int64_t inversion_count_permutation(std::vector<int64_t> permutation) {
    const size_t permutation_size = permutation.size();
    if (permutation_size <= 1) return 0;

    // Coordinate compression to 0..size-1 if needed
    std::set<int64_t> values(permutation.begin(), permutation.end());
    if (values.size() != permutation_size
        || *values.begin() < 0
        || *values.rbegin() >= static_cast<int64_t>(permutation_size)) {
        std::vector<int64_t> sorted(values.begin(), values.end());
        std::unordered_map<int64_t, size_t> rank;
        for (size_t index = 0; index < sorted.size(); ++index) rank[sorted[index]] = index;
        for (size_t index = 0; index < permutation_size; ++index)
            permutation[index] = static_cast<int64_t>(rank[permutation[index]]);
    }

    std::vector<int64_t> fenwick_tree(permutation_size + 1, 0);
    auto fenwick_add = [&](size_t index, int64_t delta) {
        index++;
        while (index <= permutation_size) {
            fenwick_tree[index] += delta;
            index += index & (~index + 1);  // lowbit
        }
    };
    auto fenwick_prefix_sum = [&](size_t up_to) {
        int64_t total = 0;
        while (up_to) {
            total += fenwick_tree[up_to];
            up_to -= up_to & (~up_to + 1);  // lowbit
        }
        return total;
    };

    int64_t total_inversions = 0;
    for (size_t index = permutation_size; index-- > 0;) {
        size_t element = static_cast<size_t>(permutation[index]);
        total_inversions += fenwick_prefix_sum(element);
        fenwick_add(element, 1);
    }
    return total_inversions;
}

std::vector<std::vector<int64_t>> permutation_cycles(const std::vector<int64_t>& permutation) {
    const size_t size = permutation.size();
    std::vector<bool> seen(size, false);
    std::vector<std::vector<int64_t>> cycles;
    for (size_t start = 0; start < size; ++start) {
        if (seen[start]) continue;
        std::vector<int64_t> cycle;
        size_t pos = start;
        while (!seen[pos]) {
            seen[pos] = true;
            cycle.push_back(static_cast<int64_t>(pos));
            int64_t next = permutation[pos];
            if (next < 0 || next >= static_cast<int64_t>(size)) break;
            pos = static_cast<size_t>(next);
        }
        if (!cycle.empty())
            cycles.push_back(std::move(cycle));
    }
    return cycles;
}

CycleStatsResult cycle_stats(const std::vector<int64_t>& permutation) {
    CycleStatsResult result;
    const size_t size = permutation.size();
    if (size == 0) return result;
    for (int64_t elem : permutation) {
        if (elem < 0 || elem >= static_cast<int64_t>(size))
            return result;
    }
    std::vector<std::vector<int64_t>> cycles = permutation_cycles(permutation);
    result.cycle_count = static_cast<int64_t>(cycles.size());
    result.cycle_lengths.reserve(cycles.size());
    for (const auto& c : cycles)
        result.cycle_lengths.push_back(static_cast<int64_t>(c.size()));
    std::sort(result.cycle_lengths.begin(), result.cycle_lengths.end(), std::greater<int64_t>{});
    result.max_cycle_length = result.cycle_lengths.empty() ? 0 : result.cycle_lengths[0];
    result.fixed_point_count = 0;
    for (const auto& c : cycles)
        if (c.size() == 1) result.fixed_point_count++;
    return result;
}

} // namespace iwt
