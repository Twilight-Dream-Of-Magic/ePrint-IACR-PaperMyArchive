#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace iwt {

/// Sponge absorb then squeeze using a precomputed permutation table: state = perm[(state ^ block) & state_mask].
/// permutation_table[state] = image of state under the cipher permutation (state_space_size elements).
/// Returns final digest = state & rate_mask after absorbing all message_blocks.
int64_t absorb_squeeze_using_table(
    int64_t initial_state,
    const std::vector<int64_t>& message_blocks,
    const std::vector<int64_t>& permutation_table,
    int64_t rate_mask,
    int64_t state_mask);

/// Build full permutation table for toy-sponge when the cipher is scalar toy_spn: for each state in [0, state_space_size)
/// run run_toy_spn(state, ...) and store last state value_x & state_mask. All heavy work in C++; Python can cache the result.
std::vector<int64_t> build_permutation_table_toy_spn(
    int state_space_size,
    int64_t state_mask,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& substitution_table,
    const std::vector<int64_t>& bit_permutation,
    int64_t modulus,
    int64_t representative,
    const std::string& floor_label = "R0");

} // namespace iwt
