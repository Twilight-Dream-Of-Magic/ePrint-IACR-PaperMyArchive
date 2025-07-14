#include "iwt/winding_trajectory.hpp"
#include <algorithm>
#include <cmath>
#include <cctype>
#include <set>
#include <unordered_map>

namespace iwt {

namespace {

std::string to_lower(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (unsigned char c : s)
        out += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return out;
}

} // namespace

std::string operation_family_from_operation_name(const std::string& operation_name) {
    std::string op = to_lower(operation_name);
    if (op.find("s_box") != std::string::npos || op.find("substitut") != std::string::npos)
        return "substitution";
    if (op.find("p_box") != std::string::npos || op.find("permute_bits") != std::string::npos ||
        op.find("perm_step") != std::string::npos || op.find("permute_values") != std::string::npos)
        return "permutation";
    if (op.find("rotl") != std::string::npos || op.find("rotr") != std::string::npos || op.find("rot") != std::string::npos)
        return "rotation";
    if (op.find("cross_domain") != std::string::npos || op.find("cross_floor") != std::string::npos)
        return "cross_domain";
    if (op.find("xor") != std::string::npos)
        return "xor";
    if (op.find("add") != std::string::npos)
        return "addition";
    if (op.find("sub") != std::string::npos)
        return "subtraction";
    return "other";
}

InformationHeightProfileResult compute_information_height_profile(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots) {

    InformationHeightProfileResult result;

    for (const auto& state : state_snapshots) {
        result.height_time_series.emplace_back(state.time_counter, state.current_building_height);
    }

    std::map<std::string, int64_t> height_by_building;
    std::map<std::string, int64_t> height_by_family;
    int64_t total_delta = 0;

    for (const auto& event : event_snapshots) {
        int64_t delta = event.boundary_quotient_delta;
        result.increment_time_series.emplace_back(event.time_counter, delta);
        height_by_building[event.floor] += delta;
        std::string family = operation_family_from_operation_name(event.operation);
        height_by_family[family] += delta;
        total_delta += delta;
    }

    result.height_by_building = height_by_building;
    result.height_by_operation_family = height_by_family;

    size_t total_steps = event_snapshots.size();
    result.mean_increment_per_step = (total_steps > 0) ? (static_cast<double>(total_delta) / static_cast<double>(total_steps)) : 0.0;

    int64_t burst_threshold = (result.mean_increment_per_step > 0.0)
        ? std::max(int64_t(1), static_cast<int64_t>(result.mean_increment_per_step * 2.0))
        : 1;
    for (const auto& p : result.increment_time_series) {
        if (p.second >= burst_threshold)
            result.burst_steps.push_back(p);
    }
    result.burst_step_count = static_cast<int64_t>(result.burst_steps.size());

    if (!result.height_time_series.empty()) {
        int64_t max_height = result.height_time_series.front().second;
        for (const auto& p : result.height_time_series) {
            if (p.second > max_height) max_height = p.second;
        }
        result.final_height = result.height_time_series.back().second;
        result.max_height = max_height;
    }

    return result;
}

CrossDomainSwitchingPatternResult compute_cross_domain_switching_pattern(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots) {

    CrossDomainSwitchingPatternResult result;

    for (const auto& s : state_snapshots) {
        result.cross_domain_counter_time_series_head.emplace_back(s.time_counter, s.cross_building_event_count);
    }

    for (const auto& ev : event_snapshots) {
        std::string family = operation_family_from_operation_name(ev.operation);
        if (family == "cross_domain")
            result.total_cross_domain_events++;
    }

    if (!state_snapshots.empty())
        result.net_cross_domain_counter = state_snapshots.back().cross_building_event_count;

    std::set<std::string> buildings_seen;
    if (!state_snapshots.empty()) {
        std::string current_building = state_snapshots[0].floor;
        buildings_seen.insert(current_building);
        result.building_visit_sequence.push_back({0, current_building});

        size_t segment_start = 0;
        for (size_t i = 1; i < state_snapshots.size(); ++i) {
            std::string b = state_snapshots[i].floor;
            if (b != current_building) {
                result.building_dwell_times.push_back({
                    current_building,
                    static_cast<int64_t>(segment_start),
                    static_cast<int64_t>(i),
                    static_cast<int64_t>(i - segment_start)
                });
                result.building_visit_sequence.push_back({static_cast<int64_t>(state_snapshots[i].time_counter), b});
                current_building = b;
                buildings_seen.insert(b);
                segment_start = i;
            }
        }
        result.building_dwell_times.push_back({
            current_building,
            static_cast<int64_t>(segment_start),
            static_cast<int64_t>(state_snapshots.size() - 1),
            static_cast<int64_t>(state_snapshots.size() - 1 - segment_start)
        });
    }

    result.unique_buildings_visited = static_cast<int64_t>(buildings_seen.size());

    if (result.building_dwell_times.size() >= 2) {
        double sum = 0.0;
        for (const auto& d : result.building_dwell_times)
            sum += static_cast<double>(d.dwell_steps);
        double mean_dwell = sum / static_cast<double>(result.building_dwell_times.size());
        double variance = 0.0;
        for (const auto& d : result.building_dwell_times) {
            double v = static_cast<double>(d.dwell_steps) - mean_dwell;
            variance += v * v;
        }
        variance /= static_cast<double>(result.building_dwell_times.size());
        result.switching_regularity_stddev = std::sqrt(variance);
    }

    const size_t head_limit = 30;
    if (result.cross_domain_counter_time_series_head.size() > head_limit)
        result.cross_domain_counter_time_series_head.resize(head_limit);

    return result;
}

JointValueHeightAnalysisResult compute_joint_value_height_analysis(
    const std::vector<StateSnapshot>& state_snapshots) {

    JointValueHeightAnalysisResult result;

    std::vector<std::pair<int64_t, int64_t>> pairs;
    for (const auto& s : state_snapshots) {
        pairs.emplace_back(s.value_x, s.current_building_height);
    }

    result.trajectory_length = static_cast<int64_t>(pairs.size());

    std::set<std::pair<int64_t, int64_t>> pair_set;
    int64_t intersection_count = 0;
    for (const auto& p : pairs) {
        if (pair_set.count(p))
            intersection_count++;
        pair_set.insert(p);
    }
    result.distinct_value_height_pairs = static_cast<int64_t>(pair_set.size());
    result.trajectory_self_intersection_count = intersection_count;
    result.trajectory_self_intersection_rate = (result.trajectory_length > 0)
        ? (static_cast<double>(intersection_count) / static_cast<double>(result.trajectory_length))
        : 0.0;

    std::map<int64_t, std::set<int64_t>> height_to_values;
    std::map<int64_t, int64_t> visit_count_at_height;
    for (const auto& p : pairs) {
        height_to_values[p.second].insert(p.first);
        visit_count_at_height[p.second]++;
    }

    for (const auto& kv : height_to_values) {
        result.value_spread_at_height_levels.push_back({
            kv.first,
            static_cast<int64_t>(kv.second.size()),
            visit_count_at_height[kv.first]
        });
    }
    std::sort(result.value_spread_at_height_levels.begin(), result.value_spread_at_height_levels.end(),
              [](const ValueSpreadAtHeightLevel& a, const ValueSpreadAtHeightLevel& b) {
                  return a.information_height_level < b.information_height_level;
              });

    if (result.value_spread_at_height_levels.size() > 30) {
        size_t step = std::max(size_t(1), result.value_spread_at_height_levels.size() / 30);
        std::vector<ValueSpreadAtHeightLevel> sampled;
        for (size_t i = 0; i < result.value_spread_at_height_levels.size(); i += step)
            sampled.push_back(result.value_spread_at_height_levels[i]);
        result.value_spread_at_height_levels = std::move(sampled);
    }

    const size_t sample_head_size = 30;
    for (size_t i = 0; i < pairs.size() && i < sample_head_size; ++i) {
        result.trajectory_sample_head.push_back({
            static_cast<int64_t>(i),
            pairs[i].first,
            pairs[i].second
        });
    }

    return result;
}

} // namespace iwt
