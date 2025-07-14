#pragma once

#include "toy_spn_run.hpp"  // StateSnapshot, EventSnapshot, InternalTrace
#include <cstdint>
#include <string>
#include <vector>

namespace iwt {

/// Keystream from ARX in counter or OFB mode. Returns (keystream, internal_traces).
/// internal_traces is empty unless collect_internal_traces; each element is (state_snapshots, event_snapshots) for one block.
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
    const std::string& base_floor_label = "R0",
    const std::string& cross_domain_floor_label = "DomQ");

/// Run full ARX: optional cross_domain, then add(k_i) -> rotate(r_i) -> xor(c_i) per round.
/// rotate_left: true = rotl_bits, false = rotr_bits.
/// cross_domain_modulus: 0 = no cross-domain; otherwise toggle every cross_domain_every_rounds (not at round 0).
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
    const std::string& base_floor_label = "R0",
    const std::string& cross_domain_floor_label = "DomQ");

/// Decrypt from final state back to initial. Same config as run_toy_arx (rounds, round_keys, round_constants, rotation_amounts, rotate_left, cross_domain_modulus, cross_domain_every_rounds).
/// final_state: the StateSnapshot after encryption (last state). final_modulus/final_representative: domain of that state.
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
    const std::string& base_floor_label = "R0",
    const std::string& cross_domain_floor_label = "DomQ");

}  // namespace iwt
