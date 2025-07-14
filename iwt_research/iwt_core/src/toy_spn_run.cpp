#include "iwt/toy_spn_run.hpp"
#include <stdexcept>
#include <utility>

namespace iwt {

namespace {
int word_bits_from_modulus(int64_t modulus) {
    if (modulus <= 0 || (modulus & (modulus - 1)) != 0)
        return 0;
    int word_bits_count = 0;
    int64_t modulus_copy = modulus;
    while (modulus_copy > 1) {
        modulus_copy >>= 1;
        ++word_bits_count;
    }
    return word_bits_count;
}
} // namespace

std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_toy_spn(
    int64_t initial_value,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& substitution_table,
    const std::vector<int64_t>& bit_permutation,
    int64_t modulus,
    int64_t representative,
    const std::string& floor_label) {
    Domain domain(modulus, representative);
    int word_bits = word_bits_from_modulus(modulus);
    if (word_bits <= 0)
        throw std::invalid_argument("run_toy_spn: modulus must be a positive power of two");
    if (static_cast<int>(round_keys.size()) < rounds)
        throw std::invalid_argument("run_toy_spn: round_keys size must be >= rounds");
    if (static_cast<int64_t>(substitution_table.size()) != modulus)
        throw std::invalid_argument("run_toy_spn: substitution_table length must equal modulus");
    if (static_cast<int>(bit_permutation.size()) != word_bits)
        throw std::invalid_argument("run_toy_spn: bit_permutation length must equal word_bits");

    int64_t state_value = (initial_value - representative) % modulus;
    if (state_value < 0) state_value += modulus;
    state_value = representative + state_value;

    int64_t time_counter = 0;
    int64_t side_depth = 0;
    int64_t building_height = 0;
    int64_t cross_count = 0;
    int64_t cross_quotient = 0;

    std::vector<StateSnapshot> states;
    std::vector<EventSnapshot> events;
    states.reserve(static_cast<size_t>(1 + rounds * 3));
    events.reserve(static_cast<size_t>(rounds * 3));

    states.push_back({
        state_value, time_counter, floor_label,
        side_depth, building_height, cross_count, cross_quotient
    });

    for (int round_index = 0; round_index < rounds; ++round_index) {
        int64_t round_key = round_keys[static_cast<size_t>(round_index)];

        // xor_round_key
        XorResult xor_result = xor_step(domain, state_value, round_key);
        int64_t value_before_step = state_value;
        state_value = xor_result.value_after_reduction;
        building_height += xor_result.boundary_quotient_delta;
        time_counter += 1;
        events.push_back({
            time_counter - 1, "xor_round_key[r" + std::to_string(round_index) + "]",
            floor_label, modulus, representative,
            value_before_step, state_value, value_before_step ^ round_key,
            xor_result.boundary_quotient_delta, xor_result.wrap_occurred,
            std::nullopt, std::nullopt
        });
        states.push_back({ state_value, time_counter, floor_label, side_depth, building_height, cross_count, cross_quotient });

        // s_box
        SboxStepResult sbox_result = sbox_step(domain, state_value, substitution_table);
        value_before_step = state_value;
        state_value = sbox_result.value_after;
        building_height += sbox_result.structure_delta;
        time_counter += 1;
        events.push_back({
            time_counter - 1, "s_box[r" + std::to_string(round_index) + "]",
            floor_label, modulus, representative,
            value_before_step, state_value, state_value,
            sbox_result.structure_delta, false,
            std::nullopt, std::nullopt
        });
        states.push_back({ state_value, time_counter, floor_label, side_depth, building_height, cross_count, cross_quotient });

        // p_box_bits
        PermuteBitsStepResult permute_result = permute_bits_step(domain, state_value, bit_permutation, word_bits);
        value_before_step = state_value;
        state_value = permute_result.value_after;
        building_height += permute_result.structure_delta;
        time_counter += 1;
        events.push_back({
            time_counter - 1, "p_box_bits[r" + std::to_string(round_index) + "]",
            floor_label, modulus, representative,
            value_before_step, state_value, state_value,
            permute_result.structure_delta, false,
            std::nullopt, std::nullopt
        });
        states.push_back({ state_value, time_counter, floor_label, side_depth, building_height, cross_count, cross_quotient });
    }

    return {std::move(states), std::move(events)};
}

std::pair<std::vector<int64_t>, std::vector<InternalTrace>> generate_keystream_spn(
    const std::string& mode,
    int64_t initial_value,
    int64_t output_length,
    bool collect_internal_traces,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& substitution_table,
    const std::vector<int64_t>& bit_permutation,
    int64_t modulus,
    int64_t representative,
    const std::string& floor_label) {
    if (output_length <= 0)
        return {{}, {}};
    if (mode != "counter" && mode != "ofb")
        throw std::invalid_argument("generate_keystream_spn: mode must be 'counter' or 'ofb'");

    int64_t modulus_q = modulus;
    int64_t initial_value_in_domain = (initial_value % modulus_q);
    if (initial_value_in_domain < 0) initial_value_in_domain += modulus_q;
    initial_value_in_domain = representative + (initial_value_in_domain - representative) % modulus_q;
    if (initial_value_in_domain < representative) initial_value_in_domain += modulus_q;

    std::vector<int64_t> keystream;
    keystream.reserve(static_cast<size_t>(output_length));
    std::vector<InternalTrace> traces;
    if (collect_internal_traces)
        traces.reserve(static_cast<size_t>(output_length));

    int64_t current_state_value = initial_value_in_domain;
    for (int64_t block_index = 0; block_index < output_length; ++block_index) {
        int64_t block_input_value;
        if (mode == "counter") {
            int64_t index_in_domain = (initial_value_in_domain - representative + block_index) % modulus_q;
            if (index_in_domain < 0) index_in_domain += modulus_q;
            block_input_value = representative + index_in_domain;
        } else {
            block_input_value = current_state_value;
        }

        auto [state_snapshots, event_snapshots] = run_toy_spn(
            block_input_value, rounds, round_keys, substitution_table, bit_permutation,
            modulus, representative, floor_label);
        if (state_snapshots.empty())
            throw std::runtime_error("generate_keystream_spn: run_toy_spn returned no state");
        int64_t output_state_value = state_snapshots.back().value_x;
        keystream.push_back(output_state_value);
        if (mode == "ofb")
            current_state_value = output_state_value;
        if (collect_internal_traces)
            traces.push_back({std::move(state_snapshots), std::move(event_snapshots)});
    }
    return {std::move(keystream), std::move(traces)};
}

} // namespace iwt
