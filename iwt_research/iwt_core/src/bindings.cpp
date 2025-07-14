// IWT core: C++23 bindings for Python. All names match paper and Python; no abbreviations.
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "iwt/discrete_domain.hpp"
#include "iwt/preflight.hpp"
#include "iwt/inversions.hpp"
#include "iwt/atomic_operations.hpp"
#include "iwt/binary_hypercube.hpp"
#include "iwt/structure_height.hpp"
#include "iwt/toy_spn_run.hpp"
#include "iwt/toy_arx_run.hpp"
#include "iwt/keystream_metrics.hpp"
#include "iwt/winding_trajectory.hpp"
#include "iwt/rho_analysis.hpp"
#include "iwt/collision_metrics.hpp"
#include "iwt/winding_metrics.hpp"
#include "iwt/high_dimensional.hpp"
#include "iwt/baseline_run.hpp"
#include "iwt/sponge.hpp"
#include <cstdlib>
#include <iostream>
#include <optional>
#include <string>
#include <tuple>
#include <vector>
// std::print: use only with Clang; GCC MinGW has <print> but lacks __open_terminal/__write_to_terminal.
#if __has_include(<print>) && defined(__clang__)
#include <print>
#endif

PYBIND11_MODULE(iwt_core, m) {
    m.doc() = "IWT core math in C++23. Names match paper and Python; no abbreviations.";

    if (std::getenv("IWT_CPP_DEBUG")) {
#if __has_include(<print>) && defined(__clang__)
        std::print("iwt_core: C++23 module loaded (IWT_CPP_DEBUG=1)\n");
#else
        std::cout << "iwt_core: C++23 module loaded (IWT_CPP_DEBUG=1)\n";
#endif
    }

    // Domain: paper D=(q,w). Expose modulus and representative; Python uses domain.modulus, domain.representative.
    pybind11::class_<iwt::Domain>(m, "Domain")
        .def(pybind11::init<>())
        .def(pybind11::init<int64_t, int64_t>(), pybind11::arg("modulus"), pybind11::arg("representative") = 0)
        .def_readwrite("modulus", &iwt::Domain::modulus)
        .def_readwrite("representative", &iwt::Domain::representative)
        .def_property_readonly("upper_bound", &iwt::Domain::upper_bound)
        .def_property_readonly("is_binary", &iwt::Domain::is_binary);

    m.def("representative_reduction", &iwt::representative_reduction, pybind11::arg("domain"), pybind11::arg("z"),
          "Red_{q,w}(z). Paper §2.3.");
    m.def("boundary_quotient", &iwt::boundary_quotient, pybind11::arg("domain"), pybind11::arg("z"),
          "Delta_{q,w}(z). Paper §2.3.");
    m.def("is_power_of_two", &iwt::is_power_of_two, pybind11::arg("n"));

    m.def("preflight_reduce", [](const iwt::Domain& domain, int64_t raw) {
        auto [representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction] =
            iwt::preflight_reduce(domain, raw);
        return pybind11::make_tuple(representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction);
    }, pybind11::arg("domain"), pybind11::arg("raw"), "Preflight PF_D(raw). Returns (representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction).");

    m.def("inversion_count_permutation", &iwt::inversion_count_permutation,
          pybind11::arg("permutation"), "inv(π): inversion count, O(n log n).");
    m.def("inversion_norm", &iwt::inversion_norm, pybind11::arg("inv_count"), pybind11::arg("modulus"));
    m.def("inv_parity", &iwt::inv_parity, pybind11::arg("inv_count"));
    m.def("permutation_cycles", &iwt::permutation_cycles, pybind11::arg("permutation"),
          "Decompose permutation into disjoint cycles. permutation[i] = image of i.");
    pybind11::class_<iwt::CycleStatsResult>(m, "CycleStatsResult")
        .def_readwrite("cycle_count", &iwt::CycleStatsResult::cycle_count)
        .def_readwrite("cycle_lengths", &iwt::CycleStatsResult::cycle_lengths)
        .def_readwrite("max_cycle_length", &iwt::CycleStatsResult::max_cycle_length)
        .def_readwrite("fixed_point_count", &iwt::CycleStatsResult::fixed_point_count);
    m.def("cycle_stats", &iwt::cycle_stats, pybind11::arg("permutation"),
          "P-box: cycle_count, cycle_lengths (desc), max_cycle_length, fixed_point_count.");

    m.def("sbox_lifted_sequence", &iwt::sbox_lifted_sequence,
          pybind11::arg("output_sequence"), pybind11::arg("modulus_q"), pybind11::arg("window_start") = 0,
          "S-box unwrapping: return lifted sequence (y0, y1, ...) for turn/crossing counts.");
    m.def("per_step_structure_increments_sbox", &iwt::per_step_structure_increments_sbox,
          pybind11::arg("output_sequence"), pybind11::arg("modulus_q"), pybind11::arg("window_start") = 0,
          "S-box structure delta from value-domain unwrapping (paper §5.2).");
    m.def("pbox_structure_increment_at", &iwt::pbox_structure_increment_at,
          pybind11::arg("input_index"), pybind11::arg("output_value"), pybind11::arg("modulus_q"), pybind11::arg("window_start") = 0,
          "P-box single-step structure delta ∈ {-1,0,+1} (paper §5.3).");
    m.def("per_step_structure_increments_pbox", &iwt::per_step_structure_increments_pbox,
          pybind11::arg("output_sequence"), pybind11::arg("modulus_q"), pybind11::arg("window_start") = 0,
          "P-box per-step structure deltas (paper §5.3).");

    pybind11::class_<iwt::SboxStepResult>(m, "SboxStepResult")
        .def_readwrite("value_after", &iwt::SboxStepResult::value_after)
        .def_readwrite("structure_delta", &iwt::SboxStepResult::structure_delta);
    pybind11::class_<iwt::PboxValuesStepResult>(m, "PboxValuesStepResult")
        .def_readwrite("value_after", &iwt::PboxValuesStepResult::value_after)
        .def_readwrite("structure_delta", &iwt::PboxValuesStepResult::structure_delta);
    pybind11::class_<iwt::PermuteBitsStepResult>(m, "PermuteBitsStepResult")
        .def_readwrite("value_after", &iwt::PermuteBitsStepResult::value_after)
        .def_readwrite("structure_delta", &iwt::PermuteBitsStepResult::structure_delta);

    // Atomic step results: expose full names (no x1, delta, wrap_dir abbreviations).
    pybind11::class_<iwt::AddSubResult>(m, "AddSubResult")
        .def_readwrite("value_after_reduction", &iwt::AddSubResult::value_after_reduction)
        .def_readwrite("boundary_quotient_delta", &iwt::AddSubResult::boundary_quotient_delta)
        .def_readwrite("wrap_occurred", &iwt::AddSubResult::wrap_occurred)
        .def_readwrite("wrap_direction", &iwt::AddSubResult::wrap_direction)
        .def_readwrite("carry", &iwt::AddSubResult::carry)
        .def_readwrite("borrow", &iwt::AddSubResult::borrow);
    pybind11::class_<iwt::XorResult>(m, "XorResult")
        .def_readwrite("value_after_reduction", &iwt::XorResult::value_after_reduction)
        .def_readwrite("boundary_quotient_delta", &iwt::XorResult::boundary_quotient_delta)
        .def_readwrite("wrap_occurred", &iwt::XorResult::wrap_occurred)
        .def_readwrite("wrap_direction", &iwt::XorResult::wrap_direction);
    pybind11::class_<iwt::RotStepResult>(m, "RotStepResult")
        .def_readwrite("value_after_preflight", &iwt::RotStepResult::value_after_preflight)
        .def_readwrite("boundary_quotient_delta", &iwt::RotStepResult::boundary_quotient_delta)
        .def_readwrite("wrap_occurred", &iwt::RotStepResult::wrap_occurred)
        .def_readwrite("wrap_direction", &iwt::RotStepResult::wrap_direction)
        .def_readwrite("side_depth_increment", &iwt::RotStepResult::side_depth_increment)
        .def_readwrite("rotated_value", &iwt::RotStepResult::rotated_value);
    pybind11::class_<iwt::CrossDomainResult>(m, "CrossDomainResult")
        .def_readwrite("value_after_reduction", &iwt::CrossDomainResult::value_after_reduction)
        .def_readwrite("boundary_quotient_delta", &iwt::CrossDomainResult::boundary_quotient_delta)
        .def_readwrite("wrap_occurred", &iwt::CrossDomainResult::wrap_occurred)
        .def_readwrite("wrap_direction", &iwt::CrossDomainResult::wrap_direction)
        .def_readwrite("cross_domain_reencoding_quotient_after", &iwt::CrossDomainResult::cross_domain_reencoding_quotient_after)
        .def_readwrite("cross_building_event_count_after", &iwt::CrossDomainResult::cross_building_event_count_after);

    m.def("add_step", &iwt::add_step,
          pybind11::arg("domain"), pybind11::arg("value_before"), pybind11::arg("constant"));
    m.def("sub_step", &iwt::sub_step,
          pybind11::arg("domain"), pybind11::arg("value_before"), pybind11::arg("constant"));
    m.def("xor_step", &iwt::xor_step,
          pybind11::arg("domain"), pybind11::arg("value_before"), pybind11::arg("constant"));
    m.def("rotation_side_depth_increment", &iwt::rotation_side_depth_increment,
          pybind11::arg("word_bits"), pybind11::arg("rotation_amount"), pybind11::arg("left"));
    m.def("rotation_left_step", &iwt::rotation_left_step,
          pybind11::arg("domain"), pybind11::arg("value_before"),
          pybind11::arg("current_building_side_depth"), pybind11::arg("current_building_height"),
          pybind11::arg("rotation_amount"), pybind11::arg("word_bits"));
    m.def("rotation_right_step", &iwt::rotation_right_step,
          pybind11::arg("domain"), pybind11::arg("value_before"),
          pybind11::arg("current_building_side_depth"), pybind11::arg("current_building_height"),
          pybind11::arg("rotation_amount"), pybind11::arg("word_bits"));
    m.def("cross_domain_step", &iwt::cross_domain_step,
          pybind11::arg("old_domain"), pybind11::arg("new_domain"), pybind11::arg("value_before"),
          pybind11::arg("cross_domain_reencoding_quotient"), pybind11::arg("current_cross_building_event_count"),
          pybind11::arg("cross_step"));
    m.def("sbox_step", &iwt::sbox_step,
          pybind11::arg("domain"), pybind11::arg("value_before"), pybind11::arg("substitution_table"),
          "S-box atomic step: (value_after, structure_delta). Paper Def 2.0.2 + §5.2.");
    m.def("validate_bit_permutation", &iwt::validate_bit_permutation,
          pybind11::arg("bit_permutation"), pybind11::arg("word_bits"),
          "Raises if bit_permutation is not a permutation of [0..word_bits-1] or length != word_bits.");
    m.def("apply_bit_permutation", &iwt::apply_bit_permutation,
          pybind11::arg("value"), pybind11::arg("bit_permutation"), pybind11::arg("word_bits"),
          "Bit permutation value only. For full step use permute_bits_step.");
    m.def("permute_bits_step", &iwt::permute_bits_step,
          pybind11::arg("domain"), pybind11::arg("value_before"), pybind11::arg("bit_permutation"), pybind11::arg("word_bits"),
          "P-box (bit) atomic step: (value_after, structure_delta). Paper Def 2.0.3 + §5.3.");
    m.def("validate_value_permutation", &iwt::validate_value_permutation,
          pybind11::arg("permutation_table"), pybind11::arg("modulus"),
          "Raises if permutation_table is not a permutation of [0..modulus-1] or length != modulus.");
    m.def("p_box_values_step", &iwt::p_box_values_step,
          pybind11::arg("domain"), pybind11::arg("value_before"), pybind11::arg("permutation_table"),
          "P-box (value) atomic step: (value_after, structure_delta). Paper Def 2.0.3 + §5.3.");

    // Phase 3: binary hypercube metrics (full names; no abbreviations)
    pybind11::class_<iwt::BinaryHypercubeMetricsResult>(m, "BinaryHypercubeMetricsResult")
        .def_readwrite("dimension", &iwt::BinaryHypercubeMetricsResult::dimension)
        .def_readwrite("full_node_count", &iwt::BinaryHypercubeMetricsResult::full_node_count)
        .def_readwrite("observed_node_count", &iwt::BinaryHypercubeMetricsResult::observed_node_count)
        .def_readwrite("observed_coverage_fraction", &iwt::BinaryHypercubeMetricsResult::observed_coverage_fraction)
        .def_readwrite("observed_directed_edge_count", &iwt::BinaryHypercubeMetricsResult::observed_directed_edge_count)
        .def_readwrite("zero_hamming_edge_fraction", &iwt::BinaryHypercubeMetricsResult::zero_hamming_edge_fraction)
        .def_readwrite("one_hamming_edge_fraction", &iwt::BinaryHypercubeMetricsResult::one_hamming_edge_fraction)
        .def_readwrite("multi_hamming_edge_fraction", &iwt::BinaryHypercubeMetricsResult::multi_hamming_edge_fraction)
        .def_readwrite("mean_edge_hamming_distance", &iwt::BinaryHypercubeMetricsResult::mean_edge_hamming_distance)
        .def_readwrite("max_edge_hamming_distance", &iwt::BinaryHypercubeMetricsResult::max_edge_hamming_distance)
        .def_readwrite("axis_flip_counts", &iwt::BinaryHypercubeMetricsResult::axis_flip_counts)
        .def_readwrite("axis_flip_balance_l1", &iwt::BinaryHypercubeMetricsResult::axis_flip_balance_l1)
        .def_readwrite("hamming_weight_histogram", &iwt::BinaryHypercubeMetricsResult::hamming_weight_histogram)
        .def_readwrite("edge_hamming_distance_histogram", &iwt::BinaryHypercubeMetricsResult::edge_hamming_distance_histogram);
    m.def("compute_binary_hypercube_metrics", &iwt::compute_binary_hypercube_metrics,
          pybind11::arg("dimension"), pybind11::arg("adjacency"),
          "Binary hypercube metrics over observed directed graph. Adjacency: list of (source_vertex, list of target_vertices).");

    pybind11::class_<iwt::StateSnapshot>(m, "StateSnapshot")
        .def(pybind11::init<>())
        .def_readwrite("value_x", &iwt::StateSnapshot::value_x)
        .def_readwrite("time_counter", &iwt::StateSnapshot::time_counter)
        .def_readwrite("floor", &iwt::StateSnapshot::floor)
        .def_readwrite("current_building_side_depth", &iwt::StateSnapshot::current_building_side_depth)
        .def_readwrite("current_building_height", &iwt::StateSnapshot::current_building_height)
        .def_readwrite("cross_building_event_count", &iwt::StateSnapshot::cross_building_event_count)
        .def_readwrite("cross_domain_reencoding_quotient", &iwt::StateSnapshot::cross_domain_reencoding_quotient);
    pybind11::class_<iwt::EventSnapshot>(m, "EventSnapshot")
        .def(pybind11::init<>())
        .def_readwrite("time_counter", &iwt::EventSnapshot::time_counter)
        .def_readwrite("operation", &iwt::EventSnapshot::operation)
        .def_readwrite("floor", &iwt::EventSnapshot::floor)
        .def_readwrite("modulus", &iwt::EventSnapshot::modulus)
        .def_readwrite("representative", &iwt::EventSnapshot::representative)
        .def_readwrite("value_before", &iwt::EventSnapshot::value_before)
        .def_readwrite("value_after_reduction", &iwt::EventSnapshot::value_after_reduction)
        .def_readwrite("raw_value_before_reduction", &iwt::EventSnapshot::raw_value_before_reduction)
        .def_readwrite("boundary_quotient_delta", &iwt::EventSnapshot::boundary_quotient_delta)
        .def_readwrite("wrap_occurred", &iwt::EventSnapshot::wrap_occurred)
        .def_readwrite("carry", &iwt::EventSnapshot::carry)
        .def_readwrite("borrow", &iwt::EventSnapshot::borrow);
    m.def("run_toy_spn", &iwt::run_toy_spn,
          pybind11::arg("initial_value"), pybind11::arg("rounds"), pybind11::arg("round_keys"),
          pybind11::arg("substitution_table"), pybind11::arg("bit_permutation"),
          pybind11::arg("modulus"), pybind11::arg("representative"), pybind11::arg("floor_label") = "R0",
          "Run full SPN: xor -> s_box -> p_box_bits per round. Returns (state_snapshots, event_snapshots).");
    m.def("generate_keystream_spn", &iwt::generate_keystream_spn,
          pybind11::arg("mode"), pybind11::arg("initial_value"), pybind11::arg("output_length"),
          pybind11::arg("collect_internal_traces"), pybind11::arg("rounds"), pybind11::arg("round_keys"),
          pybind11::arg("substitution_table"), pybind11::arg("bit_permutation"),
          pybind11::arg("modulus"), pybind11::arg("representative"), pybind11::arg("floor_label") = "R0",
          "Keystream from SPN in counter or OFB mode. Returns (keystream, internal_traces).");
    m.def("generate_keystream_arx", &iwt::generate_keystream_arx,
          pybind11::arg("mode"), pybind11::arg("initial_value"), pybind11::arg("output_length"),
          pybind11::arg("collect_internal_traces"), pybind11::arg("rounds"), pybind11::arg("round_keys"),
          pybind11::arg("round_constants"), pybind11::arg("rotation_amounts"), pybind11::arg("rotate_left"),
          pybind11::arg("modulus"), pybind11::arg("representative"),
          pybind11::arg("cross_domain_modulus") = 0, pybind11::arg("cross_domain_every_rounds") = 0,
          pybind11::arg("base_floor_label") = "R0", pybind11::arg("cross_domain_floor_label") = "DomQ",
          "Keystream from ARX in counter or OFB mode. Returns (keystream, internal_traces).");

    m.def("run_toy_arx", &iwt::run_toy_arx,
          pybind11::arg("initial_value"), pybind11::arg("rounds"), pybind11::arg("round_keys"),
          pybind11::arg("round_constants"), pybind11::arg("rotation_amounts"), pybind11::arg("rotate_left"),
          pybind11::arg("modulus"), pybind11::arg("representative"),
          pybind11::arg("cross_domain_modulus") = 0, pybind11::arg("cross_domain_every_rounds") = 0,
          pybind11::arg("base_floor_label") = "R0", pybind11::arg("cross_domain_floor_label") = "DomQ",
          "Run full ARX: optional cross_domain, then add -> rotate -> xor per round. Returns (state_snapshots, event_snapshots).");
    m.def("run_toy_arx_decrypt", &iwt::run_toy_arx_decrypt,
          pybind11::arg("final_state"), pybind11::arg("final_modulus"), pybind11::arg("final_representative"),
          pybind11::arg("rounds"), pybind11::arg("round_keys"), pybind11::arg("round_constants"),
          pybind11::arg("rotation_amounts"), pybind11::arg("rotate_left"),
          pybind11::arg("base_modulus"), pybind11::arg("base_representative"),
          pybind11::arg("cross_domain_modulus") = 0, pybind11::arg("cross_domain_every_rounds") = 0,
          pybind11::arg("base_floor_label") = "R0", pybind11::arg("cross_domain_floor_label") = "DomQ",
          "Decrypt ARX from final state. Returns (state_snapshots, event_snapshots).");

    pybind11::class_<iwt::PeriodDetectionResult>(m, "PeriodDetectionResult")
        .def_readwrite("period", &iwt::PeriodDetectionResult::period)
        .def_readwrite("tail_length", &iwt::PeriodDetectionResult::tail_length)
        .def_readwrite("total_rho_length", &iwt::PeriodDetectionResult::total_rho_length)
        .def_readwrite("method", &iwt::PeriodDetectionResult::method);
    m.def("detect_period_brent", &iwt::detect_period_brent, pybind11::arg("keystream"),
          "Brent cycle detection on keystream. Returns PeriodDetectionResult.");

    pybind11::class_<iwt::AutocorrelationResult>(m, "AutocorrelationResult")
        .def_readwrite("max_lag", &iwt::AutocorrelationResult::max_lag)
        .def_readwrite("values", &iwt::AutocorrelationResult::values);
    m.def("compute_autocorrelation", &iwt::compute_autocorrelation,
          pybind11::arg("keystream"), pybind11::arg("max_lag") = 32,
          "Normalized autocorrelation at lags 1..max_lag.");
    pybind11::class_<iwt::CoverageResult>(m, "CoverageResult")
        .def_readwrite("output_length", &iwt::CoverageResult::output_length)
        .def_readwrite("distinct_values", &iwt::CoverageResult::distinct_values)
        .def_readwrite("state_space_size", &iwt::CoverageResult::state_space_size)
        .def_readwrite("coverage_fraction", &iwt::CoverageResult::coverage_fraction)
        .def_readwrite("statistical_distance_from_uniform", &iwt::CoverageResult::statistical_distance_from_uniform);
    m.def("compute_coverage", &iwt::compute_coverage,
          pybind11::arg("keystream"), pybind11::arg("state_space_size"),
          "Coverage and statistical distance from uniform.");
    pybind11::class_<iwt::BootstrapCIResult>(m, "BootstrapCIResult")
        .def_readwrite("mean", &iwt::BootstrapCIResult::mean)
        .def_readwrite("lower_bound", &iwt::BootstrapCIResult::lower_bound)
        .def_readwrite("upper_bound", &iwt::BootstrapCIResult::upper_bound);
    m.def("bootstrap_ci", &iwt::bootstrap_ci,
          pybind11::arg("values"), pybind11::arg("seed"),
          pybind11::arg("iterations") = 2000, pybind11::arg("alpha") = 0.05,
          "Bootstrap CI with default stat=mean. Returns (mean, lower_bound, upper_bound).");

    // Winding trajectory profile (paper: information height / cross-domain / joint value-height).
    pybind11::class_<iwt::InformationHeightProfileResult>(m, "InformationHeightProfileResult")
        .def_readwrite("final_height", &iwt::InformationHeightProfileResult::final_height)
        .def_readwrite("max_height", &iwt::InformationHeightProfileResult::max_height)
        .def_readwrite("height_time_series", &iwt::InformationHeightProfileResult::height_time_series)
        .def_readwrite("increment_time_series", &iwt::InformationHeightProfileResult::increment_time_series)
        .def_readwrite("mean_increment_per_step", &iwt::InformationHeightProfileResult::mean_increment_per_step)
        .def_readwrite("burst_step_count", &iwt::InformationHeightProfileResult::burst_step_count)
        .def_readwrite("burst_steps", &iwt::InformationHeightProfileResult::burst_steps)
        .def_readwrite("height_by_building", &iwt::InformationHeightProfileResult::height_by_building)
        .def_readwrite("height_by_operation_family", &iwt::InformationHeightProfileResult::height_by_operation_family);
    pybind11::class_<iwt::BuildingVisitEntry>(m, "BuildingVisitEntry")
        .def_readwrite("time_step", &iwt::BuildingVisitEntry::time_step)
        .def_readwrite("building_label", &iwt::BuildingVisitEntry::building_label);
    pybind11::class_<iwt::BuildingDwellTimeEntry>(m, "BuildingDwellTimeEntry")
        .def_readwrite("building_label", &iwt::BuildingDwellTimeEntry::building_label)
        .def_readwrite("enter_time_step", &iwt::BuildingDwellTimeEntry::enter_time_step)
        .def_readwrite("leave_time_step", &iwt::BuildingDwellTimeEntry::leave_time_step)
        .def_readwrite("dwell_steps", &iwt::BuildingDwellTimeEntry::dwell_steps);
    pybind11::class_<iwt::CrossDomainSwitchingPatternResult>(m, "CrossDomainSwitchingPatternResult")
        .def_readwrite("total_cross_domain_events", &iwt::CrossDomainSwitchingPatternResult::total_cross_domain_events)
        .def_readwrite("net_cross_domain_counter", &iwt::CrossDomainSwitchingPatternResult::net_cross_domain_counter)
        .def_readwrite("building_visit_sequence", &iwt::CrossDomainSwitchingPatternResult::building_visit_sequence)
        .def_readwrite("building_dwell_times", &iwt::CrossDomainSwitchingPatternResult::building_dwell_times)
        .def_readwrite("unique_buildings_visited", &iwt::CrossDomainSwitchingPatternResult::unique_buildings_visited)
        .def_readwrite("switching_regularity_stddev", &iwt::CrossDomainSwitchingPatternResult::switching_regularity_stddev)
        .def_readwrite("cross_domain_counter_time_series_head", &iwt::CrossDomainSwitchingPatternResult::cross_domain_counter_time_series_head);
    pybind11::class_<iwt::ValueSpreadAtHeightLevel>(m, "ValueSpreadAtHeightLevel")
        .def_readwrite("information_height_level", &iwt::ValueSpreadAtHeightLevel::information_height_level)
        .def_readwrite("distinct_values_visited", &iwt::ValueSpreadAtHeightLevel::distinct_values_visited)
        .def_readwrite("visit_count", &iwt::ValueSpreadAtHeightLevel::visit_count);
    pybind11::class_<iwt::TrajectorySampleEntry>(m, "TrajectorySampleEntry")
        .def_readwrite("time_step", &iwt::TrajectorySampleEntry::time_step)
        .def_readwrite("value", &iwt::TrajectorySampleEntry::value)
        .def_readwrite("information_height", &iwt::TrajectorySampleEntry::information_height);
    pybind11::class_<iwt::JointValueHeightAnalysisResult>(m, "JointValueHeightAnalysisResult")
        .def_readwrite("trajectory_length", &iwt::JointValueHeightAnalysisResult::trajectory_length)
        .def_readwrite("distinct_value_height_pairs", &iwt::JointValueHeightAnalysisResult::distinct_value_height_pairs)
        .def_readwrite("trajectory_self_intersection_count", &iwt::JointValueHeightAnalysisResult::trajectory_self_intersection_count)
        .def_readwrite("trajectory_self_intersection_rate", &iwt::JointValueHeightAnalysisResult::trajectory_self_intersection_rate)
        .def_readwrite("value_spread_at_height_levels", &iwt::JointValueHeightAnalysisResult::value_spread_at_height_levels)
        .def_readwrite("trajectory_sample_head", &iwt::JointValueHeightAnalysisResult::trajectory_sample_head);
    m.def("compute_information_height_profile", &iwt::compute_information_height_profile,
          pybind11::arg("state_snapshots"), pybind11::arg("event_snapshots"),
          "Information height profile from trajectory (paper: current_building_height time series).");
    m.def("compute_cross_domain_switching_pattern", &iwt::compute_cross_domain_switching_pattern,
          pybind11::arg("state_snapshots"), pybind11::arg("event_snapshots"),
          "Cross-domain switching pattern (paper: building transitions, cross_building_event_count).");
    m.def("compute_joint_value_height_analysis", &iwt::compute_joint_value_height_analysis,
          pybind11::arg("state_snapshots"),
          "Joint (value, information_height) trajectory analysis (paper: 2D spiral).");

    // Rho-structure (paper: cycle/tail/in_degree for compression).
    pybind11::class_<iwt::RhoStructureMetricsResult>(m, "RhoStructureMetricsResult")
        .def_readwrite("state_count", &iwt::RhoStructureMetricsResult::state_count)
        .def_readwrite("image_count", &iwt::RhoStructureMetricsResult::image_count)
        .def_readwrite("collision_count", &iwt::RhoStructureMetricsResult::collision_count)
        .def_readwrite("cycle_count", &iwt::RhoStructureMetricsResult::cycle_count)
        .def_readwrite("cycle_length_histogram", &iwt::RhoStructureMetricsResult::cycle_length_histogram)
        .def_readwrite("total_cycle_nodes", &iwt::RhoStructureMetricsResult::total_cycle_nodes)
        .def_readwrite("tail_node_count", &iwt::RhoStructureMetricsResult::tail_node_count)
        .def_readwrite("tail_length_histogram", &iwt::RhoStructureMetricsResult::tail_length_histogram)
        .def_readwrite("max_tail_length", &iwt::RhoStructureMetricsResult::max_tail_length)
        .def_readwrite("mean_tail_length", &iwt::RhoStructureMetricsResult::mean_tail_length)
        .def_readwrite("max_in_degree", &iwt::RhoStructureMetricsResult::max_in_degree)
        .def_readwrite("in_degree_histogram", &iwt::RhoStructureMetricsResult::in_degree_histogram)
        .def_readwrite("tree_count", &iwt::RhoStructureMetricsResult::tree_count);
    m.def("compute_rho_structure", &iwt::compute_rho_structure,
          pybind11::arg("successor_table"), pybind11::arg("state_count"),
          "Rho-structure decomposition from successor table (paper: cycle/tail/in_degree).");

    // Collision and merge-depth metrics (paper: collision_count, mean_merge_depth, preimage).
    pybind11::class_<iwt::CollisionMetricsResult>(m, "CollisionMetricsResult")
        .def_readwrite("state_count", &iwt::CollisionMetricsResult::state_count)
        .def_readwrite("image_count", &iwt::CollisionMetricsResult::image_count)
        .def_readwrite("collision_pair_count", &iwt::CollisionMetricsResult::collision_pair_count)
        .def_readwrite("max_preimage_size", &iwt::CollisionMetricsResult::max_preimage_size)
        .def_readwrite("mean_preimage_size", &iwt::CollisionMetricsResult::mean_preimage_size)
        .def_readwrite("preimage_size_histogram", &iwt::CollisionMetricsResult::preimage_size_histogram)
        .def_readwrite("multi_collision_counts", &iwt::CollisionMetricsResult::multi_collision_counts);
    m.def("compute_collision_metrics", &iwt::compute_collision_metrics,
          pybind11::arg("successor_table"), pybind11::arg("state_count"),
          "Collision metrics from successor table (paper: collision_count, preimage distribution).");

    pybind11::class_<iwt::MergeDepthMetricsResult>(m, "MergeDepthMetricsResult")
        .def_readwrite("pair_count", &iwt::MergeDepthMetricsResult::pair_count)
        .def_readwrite("mean_merge_depth", &iwt::MergeDepthMetricsResult::mean_merge_depth)
        .def_readwrite("max_merge_depth", &iwt::MergeDepthMetricsResult::max_merge_depth)
        .def_readwrite("merged_fraction", &iwt::MergeDepthMetricsResult::merged_fraction)
        .def_readwrite("merge_depth_histogram", &iwt::MergeDepthMetricsResult::merge_depth_histogram);
    m.def("compute_merge_depth", &iwt::compute_merge_depth,
          pybind11::arg("successor_table"), pybind11::arg("state_count"),
          pybind11::arg("initial_pairs"), pybind11::arg("max_steps"),
          "Merge depth: iterate successor on each pair until they meet (paper: mean_merge_depth).");

    pybind11::class_<iwt::AvalancheMetricsResult>(m, "AvalancheMetricsResult")
        .def_readwrite("bit_width", &iwt::AvalancheMetricsResult::bit_width)
        .def_readwrite("pair_count", &iwt::AvalancheMetricsResult::pair_count)
        .def_readwrite("mean_hamming_distance", &iwt::AvalancheMetricsResult::mean_hamming_distance)
        .def_readwrite("mean_hamming_fraction", &iwt::AvalancheMetricsResult::mean_hamming_fraction)
        .def_readwrite("min_hamming_distance", &iwt::AvalancheMetricsResult::min_hamming_distance)
        .def_readwrite("max_hamming_distance", &iwt::AvalancheMetricsResult::max_hamming_distance);
    m.def("compute_avalanche", &iwt::compute_avalanche,
          pybind11::arg("successor_table"), pybind11::arg("state_count"),
          pybind11::arg("bit_width"), pybind11::arg("input_sample"),
          "Avalanche: 1-bit flip -> output Hamming distance over input_sample.");

    // Winding metrics (paper: projection, slice-shadow, atomic/mechanism/pattern-side).
    pybind11::class_<iwt::ProjectionMetricsResult>(m, "ProjectionMetricsResult")
        .def_readwrite("steps", &iwt::ProjectionMetricsResult::steps)
        .def_readwrite("unique_nodes", &iwt::ProjectionMetricsResult::unique_nodes)
        .def_readwrite("node_occupancy_ratio", &iwt::ProjectionMetricsResult::node_occupancy_ratio)
        .def_readwrite("collision_rate", &iwt::ProjectionMetricsResult::collision_rate)
        .def_readwrite("first_return_times", &iwt::ProjectionMetricsResult::first_return_times);
    m.def("compute_projection_metrics", &iwt::compute_projection_metrics,
          pybind11::arg("projection_values"),
          pybind11::arg("observed_space_size") = pybind11::none(),
          "Projection metrics: unique nodes, collision rate, first return times (paper: observed trace).");

    pybind11::class_<iwt::SliceShadowMetricsResult>(m, "SliceShadowMetricsResult")
        .def_readwrite("trajectory_length_T", &iwt::SliceShadowMetricsResult::trajectory_length_T)
        .def_readwrite("number_of_traces", &iwt::SliceShadowMetricsResult::number_of_traces)
        .def_readwrite("average_max_multiplicity", &iwt::SliceShadowMetricsResult::average_max_multiplicity)
        .def_readwrite("p99_max_multiplicity", &iwt::SliceShadowMetricsResult::p99_max_multiplicity)
        .def_readwrite("average_pair_collision_probability", &iwt::SliceShadowMetricsResult::average_pair_collision_probability);
    m.def("compute_slice_shadow_metrics", &iwt::compute_slice_shadow_metrics,
          pybind11::arg("traces"),
          "Slice-shadow metrics over multiple traces (per-time multiplicity, pair collision prob).");

    pybind11::class_<iwt::AtomicMetricsResult>(m, "AtomicMetricsResult")
        .def_readwrite("total_steps", &iwt::AtomicMetricsResult::total_steps)
        .def_readwrite("per_operation_counts", &iwt::AtomicMetricsResult::per_operation_counts)
        .def_readwrite("wrap_total", &iwt::AtomicMetricsResult::wrap_total)
        .def_readwrite("wrap_by_operation", &iwt::AtomicMetricsResult::wrap_by_operation)
        .def_readwrite("trivial_self_loop_total", &iwt::AtomicMetricsResult::trivial_self_loop_total)
        .def_readwrite("trivial_self_loop_by_operation", &iwt::AtomicMetricsResult::trivial_self_loop_by_operation)
        .def_readwrite("nontrivial_self_loop_total", &iwt::AtomicMetricsResult::nontrivial_self_loop_total)
        .def_readwrite("nontrivial_self_loop_by_operation", &iwt::AtomicMetricsResult::nontrivial_self_loop_by_operation);
    m.def("compute_atomic_metrics", &iwt::compute_atomic_metrics,
          pybind11::arg("state_snapshots"), pybind11::arg("event_snapshots"),
          pybind11::arg("projection_values"),
          "Atomic metrics: trivial/nontrivial self-loop by projection (paper: SL/NSL).");

    pybind11::class_<iwt::MechanismSideMetricsResult>(m, "MechanismSideMetricsResult")
        .def_readwrite("total_atomic_steps", &iwt::MechanismSideMetricsResult::total_atomic_steps)
        .def_readwrite("operation_counts", &iwt::MechanismSideMetricsResult::operation_counts)
        .def_readwrite("operation_family_counts", &iwt::MechanismSideMetricsResult::operation_family_counts)
        .def_readwrite("wrap_event_count", &iwt::MechanismSideMetricsResult::wrap_event_count)
        .def_readwrite("wrap_event_rate", &iwt::MechanismSideMetricsResult::wrap_event_rate)
        .def_readwrite("wrap_event_count_by_operation_family", &iwt::MechanismSideMetricsResult::wrap_event_count_by_operation_family)
        .def_readwrite("wrap_direction_counts", &iwt::MechanismSideMetricsResult::wrap_direction_counts)
        .def_readwrite("delta_sum", &iwt::MechanismSideMetricsResult::delta_sum)
        .def_readwrite("carry_event_count", &iwt::MechanismSideMetricsResult::carry_event_count)
        .def_readwrite("borrow_event_count", &iwt::MechanismSideMetricsResult::borrow_event_count)
        .def_readwrite("cross_domain_event_count", &iwt::MechanismSideMetricsResult::cross_domain_event_count)
        .def_readwrite("information_height_in_building_final", &iwt::MechanismSideMetricsResult::information_height_in_building_final)
        .def_readwrite("information_height_in_building_max", &iwt::MechanismSideMetricsResult::information_height_in_building_max)
        .def_readwrite("information_height_cross_final", &iwt::MechanismSideMetricsResult::information_height_cross_final);
    m.def("compute_mechanism_side_metrics", &iwt::compute_mechanism_side_metrics,
          pybind11::arg("state_snapshots"), pybind11::arg("event_snapshots"),
          pybind11::arg("wrap_directions"),
          "Mechanism-side metrics: wrap, delta, carry, borrow, cross_domain, information height (paper: mechanism-side).");

    pybind11::class_<iwt::PatternSideSelfLoopResult>(m, "PatternSideSelfLoopResult")
        .def_readwrite("trivial_self_loop_event_count", &iwt::PatternSideSelfLoopResult::trivial_self_loop_event_count)
        .def_readwrite("trivial_self_loop_event_rate", &iwt::PatternSideSelfLoopResult::trivial_self_loop_event_rate)
        .def_readwrite("trivial_self_loop_event_count_by_operation_family", &iwt::PatternSideSelfLoopResult::trivial_self_loop_event_count_by_operation_family)
        .def_readwrite("nontrivial_self_loop_event_count", &iwt::PatternSideSelfLoopResult::nontrivial_self_loop_event_count)
        .def_readwrite("nontrivial_self_loop_event_rate", &iwt::PatternSideSelfLoopResult::nontrivial_self_loop_event_rate)
        .def_readwrite("nontrivial_self_loop_event_count_by_operation_family", &iwt::PatternSideSelfLoopResult::nontrivial_self_loop_event_count_by_operation_family)
        .def_readwrite("self_intersection_rate", &iwt::PatternSideSelfLoopResult::self_intersection_rate);
    pybind11::class_<iwt::PatternSideMetricsResult>(m, "PatternSideMetricsResult")
        .def_readwrite("projection", &iwt::PatternSideMetricsResult::projection)
        .def_readwrite("observed_space_size", &iwt::PatternSideMetricsResult::observed_space_size)
        .def_readwrite("self_loop", &iwt::PatternSideMetricsResult::self_loop);
    m.def("compute_pattern_side_metrics", &iwt::compute_pattern_side_metrics,
          pybind11::arg("state_snapshots"), pybind11::arg("event_snapshots"),
          pybind11::arg("projection_values"),
          pybind11::arg("observed_space_size") = pybind11::none(),
          "Pattern-side metrics: projection + self-loop + self-intersection (paper: pattern-side).");

    // High-dimensional metrics (paper: neighbor separation, lane coupling, reachability, cycle decomposition).
    pybind11::class_<iwt::NeighborSeparationMetricsResult>(m, "NeighborSeparationMetricsResult")
        .def_readwrite("rounds", &iwt::NeighborSeparationMetricsResult::rounds)
        .def_readwrite("pair_count", &iwt::NeighborSeparationMetricsResult::pair_count)
        .def_readwrite("mean_bit_hamming_distance_by_time", &iwt::NeighborSeparationMetricsResult::mean_bit_hamming_distance_by_time)
        .def_readwrite("p99_bit_hamming_distance_by_time", &iwt::NeighborSeparationMetricsResult::p99_bit_hamming_distance_by_time)
        .def_readwrite("mean_lane_difference_count_by_time", &iwt::NeighborSeparationMetricsResult::mean_lane_difference_count_by_time)
        .def_readwrite("p99_lane_difference_count_by_time", &iwt::NeighborSeparationMetricsResult::p99_lane_difference_count_by_time);
    m.def("compute_neighbor_separation_aggregate", &iwt::compute_neighbor_separation_aggregate,
          pybind11::arg("bit_hamming_distances_by_time"), pybind11::arg("lane_difference_counts_by_time"),
          "Aggregate per-time bit Hamming and lane-diff lists into mean/p99 (paper: high-dim signature).");

    pybind11::class_<iwt::LaneCouplingResult>(m, "LaneCouplingResult")
        .def_readwrite("lane_count", &iwt::LaneCouplingResult::lane_count)
        .def_readwrite("samples_per_source_lane_effective", &iwt::LaneCouplingResult::samples_per_source_lane_effective)
        .def_readwrite("coupling_probability", &iwt::LaneCouplingResult::coupling_probability);
    m.def("compute_lane_coupling_from_diffs", &iwt::compute_lane_coupling_from_diffs,
          pybind11::arg("lane_count"), pybind11::arg("source_and_differing_targets"),
          "Build coupling matrix from (source_lane, list of target_lanes where output differed).");

    pybind11::class_<iwt::EmpiricalReachabilityMetricsResult>(m, "EmpiricalReachabilityMetricsResult")
        .def_readwrite("node_count", &iwt::EmpiricalReachabilityMetricsResult::node_count)
        .def_readwrite("directed_edge_count", &iwt::EmpiricalReachabilityMetricsResult::directed_edge_count)
        .def_readwrite("source_node_count", &iwt::EmpiricalReachabilityMetricsResult::source_node_count)
        .def_readwrite("reachable_node_count", &iwt::EmpiricalReachabilityMetricsResult::reachable_node_count)
        .def_readwrite("unreachable_node_count", &iwt::EmpiricalReachabilityMetricsResult::unreachable_node_count)
        .def_readwrite("unreachable_fraction", &iwt::EmpiricalReachabilityMetricsResult::unreachable_fraction)
        .def_readwrite("in_degree_zero_node_count", &iwt::EmpiricalReachabilityMetricsResult::in_degree_zero_node_count)
        .def_readwrite("max_shortest_path_distance", &iwt::EmpiricalReachabilityMetricsResult::max_shortest_path_distance)
        .def_readwrite("mean_shortest_path_distance", &iwt::EmpiricalReachabilityMetricsResult::mean_shortest_path_distance);
    m.def("compute_empirical_reachability_metrics", &iwt::compute_empirical_reachability_metrics,
          pybind11::arg("adjacency"), pybind11::arg("source_indices"),
          "BFS reachability on directed graph (adjacency = list of out-neighbor lists).");

    pybind11::class_<iwt::CycleDecompositionMetricsResult>(m, "CycleDecompositionMetricsResult")
        .def_readwrite("state_count", &iwt::CycleDecompositionMetricsResult::state_count)
        .def_readwrite("cycle_count", &iwt::CycleDecompositionMetricsResult::cycle_count)
        .def_readwrite("fixed_point_count", &iwt::CycleDecompositionMetricsResult::fixed_point_count)
        .def_readwrite("max_cycle_length", &iwt::CycleDecompositionMetricsResult::max_cycle_length)
        .def_readwrite("mean_cycle_length", &iwt::CycleDecompositionMetricsResult::mean_cycle_length)
        .def_readwrite("cycle_length_histogram", &iwt::CycleDecompositionMetricsResult::cycle_length_histogram);
    m.def("compute_cycle_decomposition_metrics_for_bijection", &iwt::compute_cycle_decomposition_metrics_for_bijection,
          pybind11::arg("successor_table"), pybind11::arg("state_count"),
          "Cycle decomposition of bijection (successor_table[i] = image of i).");

    pybind11::class_<iwt::ReachabilityQueryTargetResult>(m, "ReachabilityQueryTargetResult")
        .def_readwrite("target_index", &iwt::ReachabilityQueryTargetResult::target_index)
        .def_readwrite("reachable_by_forward_iteration", &iwt::ReachabilityQueryTargetResult::reachable_by_forward_iteration)
        .def_readwrite("steps_if_reachable", &iwt::ReachabilityQueryTargetResult::steps_if_reachable);
    pybind11::class_<iwt::ReachabilityQueriesResult>(m, "ReachabilityQueriesResult")
        .def_readwrite("state_count", &iwt::ReachabilityQueriesResult::state_count)
        .def_readwrite("source_index", &iwt::ReachabilityQueriesResult::source_index)
        .def_readwrite("targets", &iwt::ReachabilityQueriesResult::targets);
    m.def("compute_reachability_queries_on_functional_graph", &iwt::compute_reachability_queries_on_functional_graph,
          pybind11::arg("successor_table"), pybind11::arg("state_count"),
          pybind11::arg("source_index"), pybind11::arg("target_indices"),
          "Reachability from source to each target by forward iteration (functional graph).");

    pybind11::class_<iwt::ReachabilityEvidenceTargetResult>(m, "ReachabilityEvidenceTargetResult")
        .def_readwrite("target_index", &iwt::ReachabilityEvidenceTargetResult::target_index)
        .def_readwrite("reachable_by_forward_iteration", &iwt::ReachabilityEvidenceTargetResult::reachable_by_forward_iteration)
        .def_readwrite("steps_if_reachable", &iwt::ReachabilityEvidenceTargetResult::steps_if_reachable)
        .def_readwrite("source_cycle_id", &iwt::ReachabilityEvidenceTargetResult::source_cycle_id)
        .def_readwrite("source_cycle_length", &iwt::ReachabilityEvidenceTargetResult::source_cycle_length)
        .def_readwrite("target_cycle_id", &iwt::ReachabilityEvidenceTargetResult::target_cycle_id)
        .def_readwrite("target_cycle_length", &iwt::ReachabilityEvidenceTargetResult::target_cycle_length)
        .def_readwrite("path_indices_head", &iwt::ReachabilityEvidenceTargetResult::path_indices_head)
        .def_readwrite("source_cycle_nodes", &iwt::ReachabilityEvidenceTargetResult::source_cycle_nodes)
        .def_readwrite("target_cycle_nodes", &iwt::ReachabilityEvidenceTargetResult::target_cycle_nodes);
    m.def("compute_reachability_evidence_core", &iwt::compute_reachability_evidence_core,
          pybind11::arg("successor_table"), pybind11::arg("state_count"),
          pybind11::arg("source_index"), pybind11::arg("target_indices"),
          pybind11::arg("max_witness_steps") = 256,
          "Reachability evidence core: cycle info + path/cycle nodes for Python to build SHA commitments.");

    // Keystream: seed sensitivity.
    pybind11::class_<iwt::SeedSensitivityPerPairResult>(m, "SeedSensitivityPerPairResult")
        .def_readwrite("neighbor_seed", &iwt::SeedSensitivityPerPairResult::neighbor_seed)
        .def_readwrite("first_divergence_position", &iwt::SeedSensitivityPerPairResult::first_divergence_position)
        .def_readwrite("hamming_distance", &iwt::SeedSensitivityPerPairResult::hamming_distance)
        .def_readwrite("hamming_fraction", &iwt::SeedSensitivityPerPairResult::hamming_fraction)
        .def_readwrite("length_compared", &iwt::SeedSensitivityPerPairResult::length_compared);
    pybind11::class_<iwt::SeedSensitivityResult>(m, "SeedSensitivityResult")
        .def_readwrite("pair_count", &iwt::SeedSensitivityResult::pair_count)
        .def_readwrite("mean_first_divergence_position", &iwt::SeedSensitivityResult::mean_first_divergence_position)
        .def_readwrite("mean_hamming_fraction", &iwt::SeedSensitivityResult::mean_hamming_fraction)
        .def_readwrite("per_pair", &iwt::SeedSensitivityResult::per_pair);
    m.def("compute_seed_sensitivity", &iwt::compute_seed_sensitivity,
          pybind11::arg("keystream_base"), pybind11::arg("neighbor_keystreams"), pybind11::arg("neighbor_seeds"),
          "Seed sensitivity: first divergence position and Hamming fraction per neighbor.");

    // Baseline runs (permutation / function).
    m.def("run_permutation_baseline", &iwt::run_permutation_baseline,
          pybind11::arg("initial_value"), pybind11::arg("permutation_table"),
          pybind11::arg("steps"), pybind11::arg("modulus"), pybind11::arg("representative") = 0,
          "Run permutation baseline: state = perm[state] per step. Returns (state_snapshots, event_snapshots).");
    m.def("run_function_baseline", &iwt::run_function_baseline,
          pybind11::arg("initial_value"), pybind11::arg("function_table"),
          pybind11::arg("steps"), pybind11::arg("modulus"), pybind11::arg("representative") = 0,
          "Run function baseline: state = function_table[state] per step. Returns (state_snapshots, event_snapshots).");

    // Sponge: absorb + squeeze using precomputed permutation table; build table from toy_spn in C++.
    m.def("absorb_squeeze_using_table", &iwt::absorb_squeeze_using_table,
          pybind11::arg("initial_state"), pybind11::arg("message_blocks"),
          pybind11::arg("permutation_table"), pybind11::arg("rate_mask"), pybind11::arg("state_mask"),
          "Sponge absorb (XOR block, permute) then squeeze (output state & rate_mask).");
    m.def("build_permutation_table_toy_spn", &iwt::build_permutation_table_toy_spn,
          pybind11::arg("state_space_size"), pybind11::arg("state_mask"), pybind11::arg("rounds"),
          pybind11::arg("round_keys"), pybind11::arg("substitution_table"), pybind11::arg("bit_permutation"),
          pybind11::arg("modulus"), pybind11::arg("representative"), pybind11::arg("floor_label") = "R0",
          "Build full permutation table by running toy SPN for each state; for use with absorb_squeeze_using_table.");
}
