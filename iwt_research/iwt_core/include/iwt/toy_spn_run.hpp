#pragma once

#include "atomic_operations.hpp"
#include "discrete_domain.hpp"
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace iwt {

/// Minimal state snapshot for Python to reconstruct DiscreteHighdimensionalSpaceTrackTrajectoryState.
/// Paper §2.4–2.5: value_x (state), time_counter, current_building_height, cross_domain_reencoding_quotient, etc.
struct StateSnapshot {
    int64_t value_x{0};                    ///< state value (paper x_t)
    int64_t time_counter{0};               ///< step index
    std::string floor;
    int64_t current_building_side_depth{0}; ///< paper ih^side
    int64_t current_building_height{0};     ///< paper ih^in
    int64_t cross_building_event_count{0};  ///< paper ih^cross
    int64_t cross_domain_reencoding_quotient{0}; ///< paper dq_t
};

/// Minimal event snapshot for Python to reconstruct AtomicEvent.
/// Paper §2.5: value_before/value_after_reduction, raw_value_before_reduction, boundary_quotient_delta, wrap_occurred.
struct EventSnapshot {
    int64_t time_counter{0};
    std::string operation;                  ///< op label
    std::string floor;
    int64_t modulus{0};                     ///< paper q (domain modulus)
    int64_t representative{0};              ///< paper w (domain representative)
    int64_t value_before{0};                ///< paper x_t
    int64_t value_after_reduction{0};       ///< paper x_{t+1} = Red(raw)
    int64_t raw_value_before_reduction{0};  ///< paper raw_t
    int64_t boundary_quotient_delta{0};      ///< paper delta_t = Delta(raw)
    bool wrap_occurred{false};               ///< paper wrap_t
    std::optional<int64_t> carry;
    std::optional<int64_t> borrow;
};

/// Run full SPN: xor(round_key) -> s_box -> p_box_bits per round.
/// Returns (state_snapshots, event_snapshots). Initial state is first element of state_snapshots.
std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>> run_toy_spn(
    int64_t initial_value,
    int rounds,
    const std::vector<int64_t>& round_keys,
    const std::vector<int64_t>& substitution_table,
    const std::vector<int64_t>& bit_permutation,
    int64_t modulus,
    int64_t representative,
    const std::string& floor_label = "R0");

/// Keystream from SPN in counter or OFB mode. Returns (keystream, internal_traces).
/// internal_traces is empty unless collect_internal_traces; each element is (state_snapshots, event_snapshots) for one block.
using InternalTrace = std::pair<std::vector<StateSnapshot>, std::vector<EventSnapshot>>;
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
    const std::string& floor_label = "R0");

} // namespace iwt
