#pragma once

#include "toy_spn_run.hpp"
#include <cstdint>
#include <utility>
#include <vector>

namespace iwt {

/// Run permutation baseline: state_{i+1} = permutation_table[state_i] for steps. Returns (state_snapshots, event_snapshots).
std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_permutation_baseline(
    int64_t initial_value,
    const std::vector<int64_t>& permutation_table,
    int64_t steps,
    int64_t modulus,
    int64_t representative = 0);

/// Run function baseline: state_{i+1} = function_table[state_i] for steps (no wrap). Returns (state_snapshots, event_snapshots).
std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_function_baseline(
    int64_t initial_value,
    const std::vector<int64_t>& function_table,
    int64_t steps,
    int64_t modulus,
    int64_t representative = 0);

} // namespace iwt
