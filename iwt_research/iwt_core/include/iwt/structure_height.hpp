#pragma once

#include "discrete_domain.hpp"
#include <cstdint>
#include <vector>

namespace iwt {

/// S-box lifted sequence (paper §5.2): ỹ_0 = y_0; ỹ_t = y_t + k_t*q with k_t chosen so ỹ_t is closest to ỹ_{t-1}.
/// Returns the sequence (ỹ_0, ỹ_1, ...). Empty if output_sequence.size() != modulus_q or modulus_q <= 0.
std::vector<int64_t> sbox_lifted_sequence(
    const std::vector<int64_t>& output_sequence,
    int64_t modulus_q,
    int64_t window_start = 0);

/// S-box structure increment (paper §5.2): value-domain unwrapping. Used by atomic_operations::sbox_step.
/// ỹ_0 = y_0; ỹ_t = y_t + k_t*q with k_t minimizing |(y_t + k*q) - ỹ_{t-1}|; δ^struct_t = k_t - k_{t-1}.
/// Returns per-step structure deltas (length = output_sequence.size(); 0-filled if size != modulus_q).
std::vector<int64_t> per_step_structure_increments_sbox(
    const std::vector<int64_t>& output_sequence,
    int64_t modulus_q,
    int64_t window_start = 0);

/// P-box single-step structure increment (paper §5.3): δ ∈ {-1,0,+1} minimizing |(y_t + δ*q) - x_t|.
/// input_index = window_start + t, output_value = output_sequence[t]. Tie-break: distance → |δ| → δ.
int64_t pbox_structure_increment_at(
    int64_t input_index,
    int64_t output_value,
    int64_t modulus_q,
    int64_t window_start = 0);

/// P-box full sequence: per-step structure deltas ∈ {-1,0,+1} (paper §5.3).
std::vector<int64_t> per_step_structure_increments_pbox(
    const std::vector<int64_t>& output_sequence,
    int64_t modulus_q,
    int64_t window_start = 0);

} // namespace iwt
