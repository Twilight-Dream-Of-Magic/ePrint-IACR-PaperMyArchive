#include "iwt/toy_arx_run.hpp"
#include "iwt/atomic_operations.hpp"
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
}  // namespace

std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_toy_arx(
    int64_t initial_value,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& round_constants,
    const std::vector<int64_t>& rotation_amounts,
    bool rotate_left,
    int64_t modulus,
    int64_t representative,
    int64_t cross_domain_modulus,
    int cross_domain_every_rounds,
    const std::string& base_floor_label,
    const std::string& cross_domain_floor_label) {
    Domain base_domain(modulus, representative);
    int word_bits = word_bits_from_modulus(modulus);
    if (word_bits <= 0)
        throw std::invalid_argument("run_toy_arx: modulus must be a positive power of two");
    if (static_cast<int>(round_keys.size()) < rounds ||
        static_cast<int>(round_constants.size()) < rounds ||
        static_cast<int>(rotation_amounts.size()) < rounds)
        throw std::invalid_argument("run_toy_arx: round_keys/round_constants/rotation_amounts size must be >= rounds");
    if (cross_domain_modulus > 0 && (cross_domain_modulus & (cross_domain_modulus - 1)) != 0)
        throw std::invalid_argument("run_toy_arx: cross_domain_modulus must be 0 or power of two");

    int64_t state_value = (initial_value - representative) % modulus;
    if (state_value < 0) state_value += modulus;
    state_value = representative + state_value;

    int64_t time_counter = 0;
    int64_t side_depth = 0;
    int64_t building_height = 0;
    int64_t cross_count = 0;
    int64_t cross_quotient = 0;

    int64_t current_modulus = modulus;
    int64_t current_representative = representative;
    std::string current_floor = base_floor_label;
    Domain current_domain(current_modulus, current_representative);
    Domain cross_domain(cross_domain_modulus > 0 ? cross_domain_modulus : modulus, 0);

    std::vector<StateSnapshot> states;
    std::vector<EventSnapshot> events;
    states.reserve(static_cast<size_t>(1 + rounds * 4));
    events.reserve(static_cast<size_t>(rounds * 4));

    states.push_back({
        state_value, time_counter, current_floor,
        side_depth, building_height, cross_count, cross_quotient
    });

    for (int round_index = 0; round_index < rounds; ++round_index) {
        int64_t value_before_step = state_value;
        bool perform_cross_step = (cross_domain_modulus > 0 && cross_domain_every_rounds > 0 &&
                         (round_index % cross_domain_every_rounds == 0) && round_index != 0);
        if (perform_cross_step) {
            Domain old_domain(current_modulus, current_representative);
            Domain new_domain = (current_modulus == modulus) ? cross_domain : base_domain;
            int cross_step = (current_modulus == modulus) ? 1 : -1;
            CrossDomainResult cross_domain_result = cross_domain_step(
                old_domain, new_domain, state_value, cross_quotient, cross_count, cross_step);
            value_before_step = state_value;
            state_value = cross_domain_result.value_after_reduction;
            cross_quotient = cross_domain_result.cross_domain_reencoding_quotient_after;
            cross_count = cross_domain_result.cross_building_event_count_after;
            building_height += cross_domain_result.boundary_quotient_delta;
            time_counter += 1;
            std::string new_floor = (current_modulus == modulus) ? cross_domain_floor_label : base_floor_label;
            events.push_back({
                time_counter - 1, "cross_domain[r" + std::to_string(round_index) + "]",
                new_floor, new_domain.modulus, new_domain.representative,
                value_before_step, state_value, value_before_step + cross_quotient * old_domain.modulus,
                cross_domain_result.boundary_quotient_delta, cross_domain_result.wrap_occurred,
                std::nullopt, std::nullopt
            });
            states.push_back({
                state_value, time_counter, new_floor,
                side_depth, building_height, cross_count, cross_quotient
            });
            current_modulus = new_domain.modulus;
            current_representative = new_domain.representative;
            current_floor = new_floor;
            current_domain = new_domain;
        }

        int word_bits_current = word_bits_from_modulus(current_modulus);
        if (word_bits_current <= 0)
            throw std::invalid_argument("run_toy_arx: current domain modulus must be power of two (rot_mode=bits)");

        // add
        AddSubResult add_result = add_step(current_domain, state_value, round_keys[static_cast<size_t>(round_index)]);
        value_before_step = state_value;
        state_value = add_result.value_after_reduction;
        building_height += add_result.boundary_quotient_delta;
        time_counter += 1;
        events.push_back({
            time_counter - 1, "add[r" + std::to_string(round_index) + "]",
            current_floor, current_modulus, current_representative,
            value_before_step, state_value, value_before_step + round_keys[static_cast<size_t>(round_index)],
            add_result.boundary_quotient_delta, add_result.wrap_occurred,
            add_result.carry, add_result.borrow
        });
        states.push_back({
            state_value, time_counter, current_floor,
            side_depth, building_height, cross_count, cross_quotient
        });

        // rotate
        int rotation_amount = static_cast<int>(rotation_amounts[static_cast<size_t>(round_index)]);
        if (rotation_amount <= 0) rotation_amount = 1;
        if (rotation_amount >= word_bits_current) rotation_amount = word_bits_current - 1;
        RotStepResult rotation_result = rotate_left
            ? rotation_left_step(current_domain, state_value, side_depth, building_height, rotation_amount, word_bits_current)
            : rotation_right_step(current_domain, state_value, side_depth, building_height, rotation_amount, word_bits_current);
        value_before_step = state_value;
        state_value = rotation_result.value_after_preflight;
        building_height += rotation_result.boundary_quotient_delta;
        side_depth += rotation_result.side_depth_increment;
        time_counter += 1;
        events.push_back({
            time_counter - 1, rotate_left ? "rotl_bits[r" + std::to_string(round_index) + "]" : "rotr_bits[r" + std::to_string(round_index) + "]",
            current_floor, current_modulus, current_representative,
            value_before_step, state_value, rotation_result.rotated_value,
            rotation_result.boundary_quotient_delta, rotation_result.wrap_occurred,
            std::nullopt, std::nullopt
        });
        states.push_back({
            state_value, time_counter, current_floor,
            side_depth, building_height, cross_count, cross_quotient
        });

        // xor
        XorResult xor_result = xor_step(current_domain, state_value, round_constants[static_cast<size_t>(round_index)]);
        value_before_step = state_value;
        state_value = xor_result.value_after_reduction;
        building_height += xor_result.boundary_quotient_delta;
        time_counter += 1;
        events.push_back({
            time_counter - 1, "xor[r" + std::to_string(round_index) + "]",
            current_floor, current_modulus, current_representative,
            value_before_step, state_value, value_before_step ^ round_constants[static_cast<size_t>(round_index)],
            xor_result.boundary_quotient_delta, xor_result.wrap_occurred,
            std::nullopt, std::nullopt
        });
        states.push_back({
            state_value, time_counter, current_floor,
            side_depth, building_height, cross_count, cross_quotient
        });
    }

    return {std::move(states), std::move(events)};
}

std::pair<std::vector<int64_t>, std::vector<InternalTrace>> generate_keystream_arx(
    const std::string& mode,
    int64_t initial_value,
    int64_t output_length,
    bool collect_internal_traces,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& round_constants,
    const std::vector<int64_t>& rotation_amounts,
    bool rotate_left,
    int64_t modulus,
    int64_t representative,
    int64_t cross_domain_modulus,
    int cross_domain_every_rounds,
    const std::string& base_floor_label,
    const std::string& cross_domain_floor_label) {
    if (output_length <= 0)
        return {{}, {}};
    if (mode != "counter" && mode != "ofb")
        throw std::invalid_argument("generate_keystream_arx: mode must be 'counter' or 'ofb'");

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

        auto [state_snapshots, event_snapshots] = run_toy_arx(
            block_input_value, rounds, round_keys, round_constants, rotation_amounts,
            rotate_left, modulus, representative, cross_domain_modulus, cross_domain_every_rounds,
            base_floor_label, cross_domain_floor_label);
        if (state_snapshots.empty())
            throw std::runtime_error("generate_keystream_arx: run_toy_arx returned no state");
        int64_t output_state_value = state_snapshots.back().value_x;
        keystream.push_back(output_state_value);
        if (mode == "ofb")
            current_state_value = output_state_value;
        if (collect_internal_traces)
            traces.push_back({std::move(state_snapshots), std::move(event_snapshots)});
    }
    return {std::move(keystream), std::move(traces)};
}

std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_toy_arx_decrypt(
    const StateSnapshot& final_state,
    int64_t final_modulus,
    int64_t final_representative,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& round_constants,
    const std::vector<int64_t>& rotation_amounts,
    bool rotate_left,
    int64_t base_modulus,
    int64_t base_representative,
    int64_t cross_domain_modulus,
    int cross_domain_every_rounds,
    const std::string& base_floor_label,
    const std::string& cross_domain_floor_label) {
    if (final_modulus <= 0 || (final_modulus & (final_modulus - 1)) != 0)
        throw std::invalid_argument("run_toy_arx_decrypt: final_modulus must be a positive power of two");
    if (static_cast<int>(round_keys.size()) < rounds ||
        static_cast<int>(round_constants.size()) < rounds ||
        static_cast<int>(rotation_amounts.size()) < rounds)
        throw std::invalid_argument("run_toy_arx_decrypt: round_keys/round_constants/rotation_amounts size must be >= rounds");

    Domain base_domain(base_modulus, base_representative);
    Domain cross_domain(cross_domain_modulus > 0 ? cross_domain_modulus : base_modulus, 0);

    int64_t state_value = final_state.value_x;
    int64_t time_counter = final_state.time_counter;
    int64_t side_depth = final_state.current_building_side_depth;
    int64_t building_height = final_state.current_building_height;
    int64_t cross_count = final_state.cross_building_event_count;
    int64_t cross_quotient = final_state.cross_domain_reencoding_quotient;

    int64_t current_modulus = final_modulus;
    int64_t current_representative = final_representative;
    std::string current_floor = final_state.floor;
    Domain current_domain(current_modulus, current_representative);

    std::vector<StateSnapshot> states;
    std::vector<EventSnapshot> events;
    states.reserve(static_cast<size_t>(1 + rounds * 4));
    events.reserve(static_cast<size_t>(rounds * 4));

    states.push_back({
        state_value, time_counter, current_floor,
        side_depth, building_height, cross_count, cross_quotient
    });

    for (int round_index = rounds - 1; round_index >= 0; --round_index) {
        int word_bits_current = word_bits_from_modulus(current_modulus);
        if (word_bits_current <= 0)
            throw std::invalid_argument("run_toy_arx_decrypt: current domain modulus must be power of two");

        // inverse xor (xor is self-inverse)
        XorResult xor_result = xor_step(current_domain, state_value, round_constants[static_cast<size_t>(round_index)]);
        int64_t value_before_step = state_value;
        state_value = xor_result.value_after_reduction;
        building_height += xor_result.boundary_quotient_delta;
        time_counter -= 1;
        events.push_back({
            time_counter, "xor^{-1}[r" + std::to_string(round_index) + "]",
            current_floor, current_modulus, current_representative,
            value_before_step, state_value, value_before_step ^ round_constants[static_cast<size_t>(round_index)],
            xor_result.boundary_quotient_delta, xor_result.wrap_occurred,
            std::nullopt, std::nullopt
        });
        states.push_back({
            state_value, time_counter, current_floor,
            side_depth, building_height, cross_count, cross_quotient
        });

        // inverse rotation
        int rotation_amount = static_cast<int>(rotation_amounts[static_cast<size_t>(round_index)]);
        if (rotation_amount <= 0) rotation_amount = 1;
        if (rotation_amount >= word_bits_current) rotation_amount = word_bits_current - 1;
        RotStepResult rotation_result = rotate_left
            ? rotation_right_step(current_domain, state_value, side_depth, building_height, rotation_amount, word_bits_current)
            : rotation_left_step(current_domain, state_value, side_depth, building_height, rotation_amount, word_bits_current);
        value_before_step = state_value;
        state_value = rotation_result.value_after_preflight;
        building_height += rotation_result.boundary_quotient_delta;
        side_depth -= rotation_result.side_depth_increment;
        if (side_depth < 0) side_depth = 0;
        events.push_back({
            time_counter - 1, "rot^{-1}[r" + std::to_string(round_index) + "]",
            current_floor, current_modulus, current_representative,
            value_before_step, state_value, rotation_result.rotated_value,
            rotation_result.boundary_quotient_delta, rotation_result.wrap_occurred,
            std::nullopt, std::nullopt
        });
        states.push_back({
            state_value, time_counter - 1, current_floor,
            side_depth, building_height, cross_count, cross_quotient
        });
        time_counter = time_counter - 1;

        // inverse add (sub)
        AddSubResult sub_result = sub_step(current_domain, state_value, round_keys[static_cast<size_t>(round_index)]);
        value_before_step = state_value;
        state_value = sub_result.value_after_reduction;
        building_height += sub_result.boundary_quotient_delta;
        time_counter -= 1;
        events.push_back({
            time_counter, "add^{-1}[r" + std::to_string(round_index) + "]",
            current_floor, current_modulus, current_representative,
            value_before_step, state_value, value_before_step - round_keys[static_cast<size_t>(round_index)],
            sub_result.boundary_quotient_delta, sub_result.wrap_occurred,
            sub_result.carry, sub_result.borrow
        });
        states.push_back({
            state_value, time_counter, current_floor,
            side_depth, building_height, cross_count, cross_quotient
        });

        // inverse cross_domain at start of round (if we had cross at start of this round in encrypt)
        bool had_cross_at_round = (cross_domain_modulus > 0 && cross_domain_every_rounds > 0 &&
                          (round_index % cross_domain_every_rounds == 0) && round_index != 0);
        if (had_cross_at_round) {
            Domain old_domain(current_modulus, current_representative);
            Domain new_domain = (current_modulus == base_modulus) ? cross_domain : base_domain;
            int cross_step = (current_modulus == base_modulus) ? 1 : -1;  // undo: we go back
            CrossDomainResult cross_domain_result = cross_domain_step(
                old_domain, new_domain, state_value, cross_quotient, cross_count, -cross_step);
            int64_t value_before_cross_step = state_value;
            state_value = cross_domain_result.value_after_reduction;
            cross_quotient = cross_domain_result.cross_domain_reencoding_quotient_after;
            cross_count = cross_domain_result.cross_building_event_count_after;
            building_height += cross_domain_result.boundary_quotient_delta;
            time_counter -= 1;
            std::string new_floor = (current_modulus == base_modulus) ? cross_domain_floor_label : base_floor_label;
            events.push_back({
                time_counter, "cross_domain^{-1}[r" + std::to_string(round_index) + "]",
                new_floor, new_domain.modulus, new_domain.representative,
                value_before_cross_step, state_value, value_before_cross_step + cross_quotient * old_domain.modulus,
                cross_domain_result.boundary_quotient_delta, cross_domain_result.wrap_occurred,
                std::nullopt, std::nullopt
            });
            states.push_back({
                state_value, time_counter, new_floor,
                side_depth, building_height, cross_count, cross_quotient
            });
            current_modulus = new_domain.modulus;
            current_representative = new_domain.representative;
            current_floor = new_floor;
            current_domain = new_domain;
        }
    }

    return {std::move(states), std::move(events)};
}

}  // namespace iwt