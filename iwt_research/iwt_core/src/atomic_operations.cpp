#include "iwt/atomic_operations.hpp"
#include "iwt/structure_height.hpp"
#include <algorithm>
#include <stdexcept>
#include <vector>

namespace iwt {

namespace {
int64_t mask_for_modulus(int64_t modulus) { return modulus - 1; }
int64_t carry_out_add_power_of_two(int64_t x, int64_t y, int64_t modulus) {
    int64_t m = mask_for_modulus(modulus);
    return ((x & m) + (y & m)) >= modulus ? 1 : 0;
}
int64_t borrow_out_sub_power_of_two(int64_t x, int64_t y, int64_t modulus) {
    int64_t m = mask_for_modulus(modulus);
    return (x & m) < (y & m) ? 1 : 0;
}
} // namespace

AddSubResult add_step(const Domain& domain, int64_t value_before, int64_t constant) {
    int64_t raw = value_before + constant;
    auto [representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction] =
        preflight_reduce(domain, raw);
    AddSubResult result;
    result.value_after_reduction = representative_after_reduction;
    result.boundary_quotient_delta = boundary_quotient_delta;
    result.wrap_occurred = wrap_occurred;
    result.wrap_direction = wrap_direction;
    if (domain.representative == 0 && is_power_of_two(domain.modulus))
        result.carry = carry_out_add_power_of_two(value_before, constant, domain.modulus);
    return result;
}

AddSubResult sub_step(const Domain& domain, int64_t value_before, int64_t constant) {
    int64_t raw = value_before - constant;
    auto [representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction] =
        preflight_reduce(domain, raw);
    AddSubResult result;
    result.value_after_reduction = representative_after_reduction;
    result.boundary_quotient_delta = boundary_quotient_delta;
    result.wrap_occurred = wrap_occurred;
    result.wrap_direction = wrap_direction;
    if (domain.representative == 0 && is_power_of_two(domain.modulus))
        result.borrow = borrow_out_sub_power_of_two(value_before, constant, domain.modulus);
    return result;
}

XorResult xor_step(const Domain& domain, int64_t value_before, int64_t constant) {
    int64_t raw = value_before ^ constant;
    auto [representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction] =
        preflight_reduce(domain, raw);
    return {representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction};
}

int64_t rotation_side_depth_increment(int word_bits, int rotation_amount, bool left) {
    int width = word_bits;
    int shift = rotation_amount % width;
    if (shift == 0) return 0;
    std::vector<int64_t> permutation(static_cast<size_t>(width));
    for (int index = 0; index < width; ++index)
        permutation[static_cast<size_t>(index)] = left
            ? static_cast<int64_t>((index - shift + width) % width)
            : static_cast<int64_t>((index + shift) % width);
    return inversion_count_permutation(permutation) + 1;
}

RotStepResult rotation_left_step(const Domain& domain, int64_t value_before,
                                  int64_t /*current_building_side_depth*/, int64_t /*current_building_height*/,
                                  int rotation_amount, int word_bits) {
    RotStepResult result;
    int64_t mask = domain.modulus - 1;
    int64_t value_in = value_before & mask;
    int shift = rotation_amount % word_bits;
    int64_t rotated_value;
    if (shift == 0) {
        rotated_value = value_in;
    } else {
        rotated_value = ((value_in << shift) | (value_in >> (word_bits - shift))) & mask;
    }
    result.rotated_value = rotated_value;
    int64_t raw_lift = rotated_value;
    if (shift != 0 && rotated_value > value_in)
        raw_lift = rotated_value - domain.modulus;
    auto [value_after_preflight, boundary_quotient_delta, wrap_occurred, wrap_direction] =
        preflight_reduce(domain, raw_lift);
    result.value_after_preflight = value_after_preflight;
    result.boundary_quotient_delta = boundary_quotient_delta;
    result.wrap_occurred = wrap_occurred;
    result.wrap_direction = wrap_direction;
    if (boundary_quotient_delta == 0 && value_in != rotated_value)
        result.side_depth_increment = rotation_side_depth_increment(word_bits, shift, true);
    return result;
}

RotStepResult rotation_right_step(const Domain& domain, int64_t value_before,
                                   int64_t /*current_building_side_depth*/, int64_t /*current_building_height*/,
                                   int rotation_amount, int word_bits) {
    RotStepResult result;
    int64_t mask = domain.modulus - 1;
    int64_t value_in = value_before & mask;
    int shift = rotation_amount % word_bits;
    int64_t rotated_value;
    if (shift == 0) {
        rotated_value = value_in;
    } else {
        rotated_value = ((value_in >> shift) | (value_in << (word_bits - shift))) & mask;
    }
    result.rotated_value = rotated_value;
    int64_t raw_lift = rotated_value;
    if (shift != 0 && rotated_value < value_in)
        raw_lift = rotated_value + domain.modulus;
    auto [value_after_preflight, boundary_quotient_delta, wrap_occurred, wrap_direction] =
        preflight_reduce(domain, raw_lift);
    result.value_after_preflight = value_after_preflight;
    result.boundary_quotient_delta = boundary_quotient_delta;
    result.wrap_occurred = wrap_occurred;
    result.wrap_direction = wrap_direction;
    if (boundary_quotient_delta == 0 && value_in != rotated_value)
        result.side_depth_increment = rotation_side_depth_increment(word_bits, shift, false);
    return result;
}

CrossDomainResult cross_domain_step(const Domain& old_domain, const Domain& new_domain,
                                    int64_t value_before, int64_t cross_domain_reencoding_quotient,
                                    int64_t current_cross_building_event_count, int cross_step) {
    int64_t raw = value_before + cross_domain_reencoding_quotient * old_domain.modulus;
    auto [value_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction] =
        preflight_reduce(new_domain, raw);
    CrossDomainResult result;
    result.value_after_reduction = value_after_reduction;
    result.boundary_quotient_delta = boundary_quotient_delta;
    result.wrap_occurred = wrap_occurred;
    result.wrap_direction = wrap_direction;
    result.cross_domain_reencoding_quotient_after = boundary_quotient_delta;
    result.cross_building_event_count_after = current_cross_building_event_count + cross_step;
    return result;
}

// S-box atomic step: value + δ^struct (paper Def 2.0.2 + §5.2). One call for state update.
SboxStepResult sbox_step(const Domain& domain, int64_t value_before,
                         const std::vector<int64_t>& substitution_table) {
    SboxStepResult out;
    if (static_cast<int64_t>(substitution_table.size()) != domain.modulus)
        throw std::invalid_argument("sbox_step: substitution_table length must equal domain.modulus");
    int64_t index = value_before - domain.representative;
    if (index < 0 || index >= domain.modulus)
        throw std::invalid_argument("sbox_step: value_before not in representative interval");
    int64_t mapped = substitution_table[static_cast<size_t>(index)];
    if (mapped < 0 || mapped >= domain.modulus)
        throw std::invalid_argument("sbox_step: substitution_table entries must be in [0, modulus)");
    out.value_after = domain.representative + mapped;
    std::vector<int64_t> output_sequence;
    output_sequence.reserve(static_cast<size_t>(domain.modulus));
    for (int64_t t = 0; t < domain.modulus; ++t)
        output_sequence.push_back(domain.representative + substitution_table[static_cast<size_t>(t)]);
    std::vector<int64_t> deltas = per_step_structure_increments_sbox(
        output_sequence, domain.modulus, domain.representative);
    out.structure_delta = (index >= 0 && index < domain.modulus && static_cast<size_t>(index) < deltas.size())
        ? deltas[static_cast<size_t>(index)] : 0;
    return out;
}

void validate_bit_permutation(const std::vector<int64_t>& bit_permutation, int word_bits) {
    if (static_cast<int>(bit_permutation.size()) != word_bits)
        throw std::invalid_argument("validate_bit_permutation: length must equal word_bits");
    std::vector<int64_t> sorted(bit_permutation.begin(), bit_permutation.end());
    std::sort(sorted.begin(), sorted.end());
    for (int i = 0; i < word_bits; ++i) {
        if (sorted[static_cast<size_t>(i)] != i)
            throw std::invalid_argument("validate_bit_permutation: must be a permutation of [0..word_bits-1]");
    }
}

// Bit P-box: paper Def 2.0.3. wrap_t=0; δ^struct from bounded lift, see structure_height.cpp.
int64_t apply_bit_permutation(int64_t value, const std::vector<int64_t>& bit_permutation, int word_bits) {
    validate_bit_permutation(bit_permutation, word_bits);
    int64_t mask = (word_bits >= 64) ? -1 : ((int64_t{1} << word_bits) - 1);
    value &= mask;
    int64_t out = 0;
    for (size_t output_bit_index = 0; output_bit_index < bit_permutation.size(); ++output_bit_index) {
        int input_bit_index = static_cast<int>(bit_permutation[output_bit_index]);
        int64_t bit_value = (value >> input_bit_index) & 1;
        out |= bit_value << static_cast<int>(output_bit_index);
    }
    return out;
}

void validate_value_permutation(const std::vector<int64_t>& permutation_table, int64_t modulus) {
    if (static_cast<int64_t>(permutation_table.size()) != modulus)
        throw std::invalid_argument("validate_value_permutation: permutation_table length must equal modulus");
    std::vector<int64_t> sorted(permutation_table.begin(), permutation_table.end());
    std::sort(sorted.begin(), sorted.end());
    for (int64_t i = 0; i < modulus; ++i) {
        if (sorted[static_cast<size_t>(i)] != i)
            throw std::invalid_argument("validate_value_permutation: must be a permutation of [0..modulus-1]");
    }
}

// P-box (value) atomic step: value + δ^struct (paper Def 2.0.3 + §5.3). One call for state update.
PboxValuesStepResult p_box_values_step(const Domain& domain, int64_t value_before,
                                        const std::vector<int64_t>& permutation_table) {
    PboxValuesStepResult out;
    validate_value_permutation(permutation_table, domain.modulus);
    int64_t index = value_before - domain.representative;
    if (index < 0 || index >= domain.modulus)
        throw std::invalid_argument("p_box_values_step: value_before not in representative interval");
    out.value_after = domain.representative + permutation_table[static_cast<size_t>(index)];
    out.structure_delta = pbox_structure_increment_at(
        value_before, out.value_after, domain.modulus, domain.representative);
    return out;
}

// P-box (bit) atomic step: value + δ^struct (paper Def 2.0.3 + §5.3). One call for state update.
PermuteBitsStepResult permute_bits_step(const Domain& domain, int64_t value_before,
                                         const std::vector<int64_t>& bit_permutation, int word_bits) {
    PermuteBitsStepResult out;
    out.value_after = apply_bit_permutation(value_before, bit_permutation, word_bits);
    std::vector<int64_t> output_sequence;
    int64_t modulus_q = domain.modulus;
    output_sequence.reserve(static_cast<size_t>(modulus_q));
    for (int64_t t = 0; t < modulus_q; ++t)
        output_sequence.push_back(apply_bit_permutation(t, bit_permutation, word_bits));
    std::vector<int64_t> deltas = per_step_structure_increments_pbox(
        output_sequence, modulus_q, domain.representative);
    int64_t index = value_before - domain.representative;
    out.structure_delta = (index >= 0 && index < modulus_q && static_cast<size_t>(index) < deltas.size())
        ? deltas[static_cast<size_t>(index)] : 0;
    return out;
}

} // namespace iwt
