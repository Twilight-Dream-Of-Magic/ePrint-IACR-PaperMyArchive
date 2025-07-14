#pragma once

#include "discrete_domain.hpp"
#include "preflight.hpp"
#include "inversions.hpp"
#include <cstdint>
#include <optional>
#include <string>
#include <tuple>
#include <vector>

namespace iwt {

/// Result of add/sub atomic step. Paper: (x_{t+1}, delta_t, wrap_t, dir_t); Python builds State + AtomicEvent.
struct AddSubResult {
    int64_t value_after_reduction{0};   ///< x_{t+1} = Red(raw); Python .x1
    int64_t boundary_quotient_delta{0}; ///< delta_t; Python .delta
    bool wrap_occurred{false};           ///< wrap_t; Python .wrap
    std::string wrap_direction;         ///< dir_t: "none"/"up"/"down"; Python .wrap_dir
    std::optional<int64_t> carry;       ///< add only, when modulus is power-of-two
    std::optional<int64_t> borrow;      ///< sub only, when modulus is power-of-two
};

AddSubResult add_step(const Domain& domain, int64_t value_before, int64_t constant);
AddSubResult sub_step(const Domain& domain, int64_t value_before, int64_t constant);

struct XorResult {
    int64_t value_after_reduction{0};
    int64_t boundary_quotient_delta{0};
    bool wrap_occurred{false};
    std::string wrap_direction;
};
XorResult xor_step(const Domain& domain, int64_t value_before, int64_t constant);

/// Rotation: side depth increment Delta h^side = inv(pi)+1 (paper); Python: _rotation_side_depth_increment.
int64_t rotation_side_depth_increment(int word_bits, int rotation_amount, bool left);

/// Result of rotl/rotr atomic step. Paper: (x_{t+1}, delta_t, wrap_t, dir_t, Delta h^side, y_rot).
struct RotStepResult {
    int64_t value_after_preflight{0};   ///< x_{t+1}; Python .x_out
    int64_t boundary_quotient_delta{0}; ///< delta_t; Python .height_delta
    bool wrap_occurred{false};
    std::string wrap_direction;
    int64_t side_depth_increment{0};    ///< Delta h^side = inv(pi)+1
    int64_t rotated_value{0};           ///< y_rot before lift; Python .y_rot
};

RotStepResult rotation_left_step(const Domain& domain, int64_t value_before,
                                  int64_t current_building_side_depth, int64_t current_building_height,
                                  int rotation_amount, int word_bits);
RotStepResult rotation_right_step(const Domain& domain, int64_t value_before,
                                   int64_t current_building_side_depth, int64_t current_building_height,
                                   int rotation_amount, int word_bits);

/// Cross-domain (cross-building) step. Paper: z = x0 + quotient*old_modulus; preflight on new domain.
struct CrossDomainResult {
    int64_t value_after_reduction{0};   ///< x_{t+1} in new domain; Python .x1
    int64_t boundary_quotient_delta{0}; ///< delta_t; Python .delta
    bool wrap_occurred{false};
    std::string wrap_direction;
    int64_t cross_domain_reencoding_quotient_after{0}; ///< dq_{t+1}; Python .new_quotient
    int64_t cross_building_event_count_after{0};      ///| c^{cross}_{t+1}; Python .new_cross_count
};

CrossDomainResult cross_domain_step(const Domain& old_domain, const Domain& new_domain,
                                    int64_t value_before, int64_t cross_domain_reencoding_quotient,
                                    int64_t current_cross_building_event_count, int cross_step);

/// S-box atomic step. Paper Def 2.0.2 + §5.2: value_after + δ^struct in one call (楼内 wrap=0).
struct SboxStepResult {
    int64_t value_after{0};
    int64_t structure_delta{0};
};
SboxStepResult sbox_step(const Domain& domain, int64_t value_before,
                         const std::vector<int64_t>& substitution_table);

/// Throws std::invalid_argument if bit_permutation is not a permutation of [0..word_bits-1] or length != word_bits.
void validate_bit_permutation(const std::vector<int64_t>& bit_permutation, int word_bits);

/// Bit permutation (value only). For full atomic step use permute_bits_step.
int64_t apply_bit_permutation(int64_t value, const std::vector<int64_t>& bit_permutation, int word_bits);

/// P-box (bit) atomic step. Paper Def 2.0.3 + §5.3: value_after + δ^struct in one call.
struct PermuteBitsStepResult {
    int64_t value_after{0};
    int64_t structure_delta{0};
};
PermuteBitsStepResult permute_bits_step(const Domain& domain, int64_t value_before,
                                        const std::vector<int64_t>& bit_permutation, int word_bits);

/// Integer P-box (value permutation): permutation_table must be a permutation of [0..modulus-1]. Throws if not.
void validate_value_permutation(const std::vector<int64_t>& permutation_table, int64_t modulus);

/// P-box (value permutation) atomic step. Paper Def 2.0.3 + §5.3: value_after + δ^struct in one call.
struct PboxValuesStepResult {
    int64_t value_after{0};
    int64_t structure_delta{0};
};
PboxValuesStepResult p_box_values_step(const Domain& domain, int64_t value_before,
                                        const std::vector<int64_t>& permutation_table);

} // namespace iwt
