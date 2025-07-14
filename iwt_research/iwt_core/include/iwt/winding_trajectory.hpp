#pragma once

#include "toy_spn_run.hpp"
#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace iwt {

/// Result of information height profile: time series of in-building information height.
/// Paper: trajectory profile of current_building_height; names match Python and paper (no abbreviations).
struct InformationHeightProfileResult {
    int64_t final_height{0};
    int64_t max_height{0};
    std::vector<std::pair<int64_t, int64_t>> height_time_series;
    std::vector<std::pair<int64_t, int64_t>> increment_time_series;
    double mean_increment_per_step{0.0};
    int64_t burst_step_count{0};
    std::vector<std::pair<int64_t, int64_t>> burst_steps;
    std::map<std::string, int64_t> height_by_building;
    std::map<std::string, int64_t> height_by_operation_family;
};

/// One entry for building visit: (time_step, building_label).
struct BuildingVisitEntry {
    int64_t time_step{0};
    std::string building_label;
};

/// One entry for dwell time in a building.
struct BuildingDwellTimeEntry {
    std::string building_label;
    int64_t enter_time_step{0};
    int64_t leave_time_step{0};
    int64_t dwell_steps{0};
};

/// Result of cross-domain switching pattern: building/floor transitions and cross_domain counter.
struct CrossDomainSwitchingPatternResult {
    int64_t total_cross_domain_events{0};
    int64_t net_cross_domain_counter{0};
    std::vector<BuildingVisitEntry> building_visit_sequence;
    std::vector<BuildingDwellTimeEntry> building_dwell_times;
    int64_t unique_buildings_visited{0};
    double switching_regularity_stddev{0.0};
    std::vector<std::pair<int64_t, int64_t>> cross_domain_counter_time_series_head;
};

/// One level in value-spread-at-height: at one information_height level, distinct values and visit count.
struct ValueSpreadAtHeightLevel {
    int64_t information_height_level{0};
    int64_t distinct_values_visited{0};
    int64_t visit_count{0};
};

/// One sample point in (value, information_height) trajectory.
struct TrajectorySampleEntry {
    int64_t time_step{0};
    int64_t value{0};
    int64_t information_height{0};
};

/// Result of joint (value, information_height) trajectory analysis.
struct JointValueHeightAnalysisResult {
    int64_t trajectory_length{0};
    int64_t distinct_value_height_pairs{0};
    int64_t trajectory_self_intersection_count{0};
    double trajectory_self_intersection_rate{0.0};
    std::vector<ValueSpreadAtHeightLevel> value_spread_at_height_levels;
    std::vector<TrajectorySampleEntry> trajectory_sample_head;
};

/// Classify operation name into family string (substitution, permutation, rotation, cross_domain, xor, addition, subtraction, other).
std::string operation_family_from_operation_name(const std::string& operation_name);

/// Compute information height profile from state and event snapshots. Paper: trajectory of current_building_height.
InformationHeightProfileResult compute_information_height_profile(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots);

/// Compute cross-domain switching pattern. Paper: building transitions and cross_building_event_count.
CrossDomainSwitchingPatternResult compute_cross_domain_switching_pattern(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots);

/// Compute joint (value, information_height) analysis. Paper: 2D trajectory spiral.
JointValueHeightAnalysisResult compute_joint_value_height_analysis(
    const std::vector<StateSnapshot>& state_snapshots);

} // namespace iwt
