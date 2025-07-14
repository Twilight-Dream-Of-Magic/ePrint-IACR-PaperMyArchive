#include "iwt/sponge.hpp"
#include "iwt/toy_spn_run.hpp"
#include <cstdint>
#include <vector>

namespace iwt {

int64_t absorb_squeeze_using_table(
    int64_t initial_state,
    const std::vector<int64_t>& message_blocks,
    const std::vector<int64_t>& permutation_table,
    int64_t rate_mask,
    int64_t state_mask) {

    int64_t state = initial_state & state_mask;
    size_t table_size = permutation_table.size();

    for (int64_t block : message_blocks) {
        int64_t rate_part = block & rate_mask;
        state = (state ^ rate_part) & state_mask;
        if (state >= 0 && static_cast<size_t>(state) < table_size)
            state = permutation_table[static_cast<size_t>(state)] & state_mask;
    }
    return state & rate_mask;
}

std::vector<int64_t> build_permutation_table_toy_spn(
    int state_space_size,
    int64_t state_mask,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& substitution_table,
    const std::vector<int64_t>& bit_permutation,
    int64_t modulus,
    int64_t representative,
    const std::string& floor_label) {

    std::vector<int64_t> table;
    table.reserve(static_cast<size_t>(state_space_size));

    for (int s = 0; s < state_space_size; ++s) {
        auto [state_snapshots, event_snapshots] = run_toy_spn(
            static_cast<int64_t>(s),
            rounds,
            round_keys,
            substitution_table,
            bit_permutation,
            modulus,
            representative,
            floor_label);
        int64_t last_value = state_snapshots.empty()
            ? (static_cast<int64_t>(s) & state_mask)
            : (state_snapshots.back().value_x & state_mask);
        table.push_back(last_value);
    }
    return table;
}

} // namespace iwt
