#include "iwt/baseline_run.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace iwt {

std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_permutation_baseline(
    int64_t initial_value,
    const std::vector<int64_t>& permutation_table,
    int64_t steps,
    int64_t modulus,
    int64_t representative) {

    std::vector<StateSnapshot> state_snapshots;
    std::vector<EventSnapshot> event_snapshots;
    if (modulus <= 0 || permutation_table.size() < static_cast<size_t>(modulus) || steps < 0)
        return {state_snapshots, event_snapshots};

    int64_t value = ((initial_value - representative) % modulus + modulus) % modulus + representative;
    StateSnapshot snap;
    snap.value_x = value;
    snap.time_counter = 0;
    snap.floor = "B0";
    snap.current_building_side_depth = 0;
    snap.current_building_height = 0;
    snap.cross_building_event_count = 0;
    snap.cross_domain_reencoding_quotient = 0;
    state_snapshots.push_back(snap);

    for (int64_t i = 0; i < steps; ++i) {
        int64_t index = value - representative;
        if (index < 0 || index >= modulus) index = ((index % modulus) + modulus) % modulus;
        int64_t next_value = permutation_table[static_cast<size_t>(index)];
        if (next_value < representative || next_value >= representative + modulus)
            next_value = ((next_value - representative) % modulus + modulus) % modulus + representative;

        EventSnapshot ev;
        ev.time_counter = i;
        ev.operation = "perm_step";
        ev.floor = "B0";
        ev.modulus = modulus;
        ev.representative = representative;
        ev.value_before = value;
        ev.value_after_reduction = next_value;
        ev.raw_value_before_reduction = next_value;
        ev.boundary_quotient_delta = 0;
        ev.wrap_occurred = false;
        event_snapshots.push_back(ev);

        StateSnapshot next_snap;
        next_snap.value_x = next_value;
        next_snap.time_counter = i + 1;
        next_snap.floor = "B0";
        next_snap.current_building_side_depth = 0;
        next_snap.current_building_height = 0;
        next_snap.cross_building_event_count = 0;
        next_snap.cross_domain_reencoding_quotient = 0;
        state_snapshots.push_back(next_snap);
        value = next_value;
    }
    return {state_snapshots, event_snapshots};
}

std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_function_baseline(
    int64_t initial_value,
    const std::vector<int64_t>& function_table,
    int64_t steps,
    int64_t modulus,
    int64_t representative) {

    std::vector<StateSnapshot> state_snapshots;
    std::vector<EventSnapshot> event_snapshots;
    if (modulus <= 0 || function_table.size() < static_cast<size_t>(modulus) || steps < 0)
        return {state_snapshots, event_snapshots};

    int64_t value = ((initial_value - representative) % modulus + modulus) % modulus + representative;
    StateSnapshot snap;
    snap.value_x = value;
    snap.time_counter = 0;
    snap.floor = "B0";
    snap.current_building_side_depth = 0;
    snap.current_building_height = 0;
    snap.cross_building_event_count = 0;
    snap.cross_domain_reencoding_quotient = 0;
    state_snapshots.push_back(snap);

    for (int64_t i = 0; i < steps; ++i) {
        int64_t index = value - representative;
        if (index < 0 || index >= modulus) index = ((index % modulus) + modulus) % modulus;
        int64_t next_value = function_table[static_cast<size_t>(index)];
        if (next_value < representative || next_value >= representative + modulus)
            next_value = ((next_value - representative) % modulus + modulus) % modulus + representative;

        EventSnapshot ev;
        ev.time_counter = i;
        ev.operation = "func_step";
        ev.floor = "B0";
        ev.modulus = modulus;
        ev.representative = representative;
        ev.value_before = value;
        ev.value_after_reduction = next_value;
        ev.raw_value_before_reduction = next_value;
        ev.boundary_quotient_delta = 0;
        ev.wrap_occurred = false;
        event_snapshots.push_back(ev);

        StateSnapshot next_snap;
        next_snap.value_x = next_value;
        next_snap.time_counter = i + 1;
        next_snap.floor = "B0";
        next_snap.current_building_side_depth = 0;
        next_snap.current_building_height = 0;
        next_snap.cross_building_event_count = 0;
        next_snap.cross_domain_reencoding_quotient = 0;
        state_snapshots.push_back(next_snap);
        value = next_value;
    }
    return {state_snapshots, event_snapshots};
}

} // namespace iwt
