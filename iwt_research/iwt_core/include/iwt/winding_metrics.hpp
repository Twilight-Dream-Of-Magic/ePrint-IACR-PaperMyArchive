#pragma once

#include "winding_trajectory.hpp"
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace iwt {

/// Result of projection metrics. Paper: observed trace y_t, unique nodes, collision rate, first return times.
struct ProjectionMetricsResult {
    int64_t steps{0};
    int64_t unique_nodes{0};
    std::optional<double> node_occupancy_ratio;
    double collision_rate{0.0};
    std::vector<int64_t> first_return_times;
};

/// Result of slice-shadow metrics over multiple traces (per-time-step multiplicity).
struct SliceShadowMetricsResult {
    int64_t trajectory_length_T{0};
    int64_t number_of_traces{0};
    double average_max_multiplicity{0.0};
    double p99_max_multiplicity{0.0};
    double average_pair_collision_probability{0.0};
};

/// Result of atomic metrics: trivial self-loop (SL) and non-trivial self-loop (NSL) by projection.
struct AtomicMetricsResult {
    int64_t total_steps{0};
    std::map<std::string, int64_t> per_operation_counts;
    int64_t wrap_total{0};
    std::map<std::string, int64_t> wrap_by_operation;
    int64_t trivial_self_loop_total{0};
    std::map<std::string, int64_t> trivial_self_loop_by_operation;
    int64_t nontrivial_self_loop_total{0};
    std::map<std::string, int64_t> nontrivial_self_loop_by_operation;
};

/// Result of mechanism-side metrics (wrap, delta, carry, borrow, cross_domain, information height).
struct MechanismSideMetricsResult {
    int64_t total_atomic_steps{0};
    std::map<std::string, int64_t> operation_counts;
    std::map<std::string, int64_t> operation_family_counts;
    int64_t wrap_event_count{0};
    double wrap_event_rate{0.0};
    std::map<std::string, int64_t> wrap_event_count_by_operation_family;
    std::map<std::string, int64_t> wrap_direction_counts;
    int64_t delta_sum{0};
    int64_t carry_event_count{0};
    int64_t borrow_event_count{0};
    int64_t cross_domain_event_count{0};
    int64_t information_height_in_building_final{0};
    int64_t information_height_in_building_max{0};
    int64_t information_height_cross_final{0};
};

/// Self-loop and self-intersection part of pattern-side metrics.
struct PatternSideSelfLoopResult {
    int64_t trivial_self_loop_event_count{0};
    double trivial_self_loop_event_rate{0.0};
    std::map<std::string, int64_t> trivial_self_loop_event_count_by_operation_family;
    int64_t nontrivial_self_loop_event_count{0};
    double nontrivial_self_loop_event_rate{0.0};
    std::map<std::string, int64_t> nontrivial_self_loop_event_count_by_operation_family;
    double self_intersection_rate{0.0};
};

/// Result of pattern-side metrics (projection + self-loop + self-intersection).
struct PatternSideMetricsResult {
    ProjectionMetricsResult projection;
    std::optional<int64_t> observed_space_size;
    PatternSideSelfLoopResult self_loop;
};

/// Compute projection metrics from observed trajectory ys. Paper: unique nodes, collision rate, first return times.
ProjectionMetricsResult compute_projection_metrics(
    const std::vector<int64_t>& projection_values,
    std::optional<int64_t> observed_space_size);

/// Compute slice-shadow metrics over multiple traces (same length). Paper: per-time multiplicity, pair collision prob.
SliceShadowMetricsResult compute_slice_shadow_metrics(
    const std::vector<std::vector<int64_t>>& traces);

/// Compute atomic metrics: SL/NSL from state_snapshots, event_snapshots, and projection_values.
/// projection_values[i] = project(state_snapshots[i]); length must be state_snapshots.size() == events.size() + 1.
AtomicMetricsResult compute_atomic_metrics(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots,
    const std::vector<int64_t>& projection_values);

/// Compute mechanism-side metrics. wrap_directions[i] = "up" | "down" | "none" for each event (same size as event_snapshots).
MechanismSideMetricsResult compute_mechanism_side_metrics(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots,
    const std::vector<std::string>& wrap_directions);

/// Compute pattern-side metrics (projection + self-loop + self-intersection).
PatternSideMetricsResult compute_pattern_side_metrics(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots,
    const std::vector<int64_t>& projection_values,
    std::optional<int64_t> observed_space_size);

} // namespace iwt
