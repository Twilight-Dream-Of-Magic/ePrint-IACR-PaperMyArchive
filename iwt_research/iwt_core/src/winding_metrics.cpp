#include "iwt/winding_metrics.hpp"
#include <algorithm>
#include <cmath>
#include <set>
#include <unordered_map>

namespace iwt {

namespace {

double safe_divide(double numerator, double denominator) {
    return (denominator != 0.0) ? (numerator / denominator) : 0.0;
}

} // namespace

ProjectionMetricsResult compute_projection_metrics(
    const std::vector<int64_t>& projection_values,
    std::optional<int64_t> observed_space_size) {

    ProjectionMetricsResult result;
    if (projection_values.empty()) {
        result.steps = 0;
        result.unique_nodes = 0;
        result.collision_rate = 0.0;
        return result;
    }

    std::unordered_map<int64_t, int64_t> first_seen_at;
    int64_t unique_count = 0;
    int64_t revisits = 0;

    for (size_t t = 0; t < projection_values.size(); ++t) {
        int64_t y = projection_values[t];
        auto it = first_seen_at.find(y);
        if (it == first_seen_at.end()) {
            ++unique_count;
            first_seen_at[y] = static_cast<int64_t>(t);
        } else {
            ++revisits;
            result.first_return_times.push_back(static_cast<int64_t>(t) - it->second);
        }
    }

    result.steps = static_cast<int64_t>(projection_values.size()) - 1;
    result.unique_nodes = unique_count;
    result.collision_rate = safe_divide(
        static_cast<double>(revisits),
        static_cast<double>(projection_values.size()));
    if (observed_space_size && *observed_space_size > 0) {
        result.node_occupancy_ratio = safe_divide(
            static_cast<double>(unique_count),
            static_cast<double>(*observed_space_size));
    }
    return result;
}

SliceShadowMetricsResult compute_slice_shadow_metrics(
    const std::vector<std::vector<int64_t>>& traces) {

    SliceShadowMetricsResult result;
    if (traces.empty()) {
        result.number_of_traces = 0;
        return result;
    }

    result.number_of_traces = static_cast<int64_t>(traces.size());
    size_t length = traces[0].size();
    for (const auto& tr : traces) {
        if (tr.size() != length)
            return result;  // invalid; return zeros
    }
    if (length == 0) {
        result.trajectory_length_T = 0;
        return result;
    }

    result.trajectory_length_T = static_cast<int64_t>(length) - 1;
    std::vector<int64_t> max_multiplicities;
    std::vector<double> pair_collision_probs;
    const double denom_pairs = (result.number_of_traces * (result.number_of_traces - 1)) / 2.0;

    for (size_t t = 0; t < length; ++t) {
        std::unordered_map<int64_t, int64_t> counts;
        for (const auto& tr : traces)
            ++counts[tr[t]];

        int64_t max_mul = 0;
        for (const auto& kv : counts) {
            if (kv.second > max_mul)
                max_mul = kv.second;
        }
        max_multiplicities.push_back(max_mul);

        if (denom_pairs > 0) {
            double coll_pairs = 0.0;
            for (const auto& kv : counts)
                coll_pairs += (kv.second * (kv.second - 1)) / 2.0;
            pair_collision_probs.push_back(coll_pairs / denom_pairs);
        } else {
            pair_collision_probs.push_back(0.0);
        }
    }

    int64_t sum_max = 0;
    for (int64_t m : max_multiplicities)
        sum_max += m;
    result.average_max_multiplicity = safe_divide(
        static_cast<double>(sum_max),
        static_cast<double>(max_multiplicities.size()));

    std::vector<int64_t> sorted_max(max_multiplicities.begin(), max_multiplicities.end());
    std::sort(sorted_max.begin(), sorted_max.end());
    size_t p99_index = (sorted_max.size() >= 2)
        ? static_cast<size_t>(std::floor(0.99 * (static_cast<double>(sorted_max.size()) - 1.0)))
        : 0;
    result.p99_max_multiplicity = static_cast<double>(sorted_max[p99_index]);

    double sum_pc = 0.0;
    for (double p : pair_collision_probs)
        sum_pc += p;
    result.average_pair_collision_probability = safe_divide(
        sum_pc,
        static_cast<double>(pair_collision_probs.size()));

    return result;
}

AtomicMetricsResult compute_atomic_metrics(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots,
    const std::vector<int64_t>& projection_values) {

    AtomicMetricsResult result;
    if (event_snapshots.empty() || state_snapshots.size() != event_snapshots.size() + 1 ||
        projection_values.size() != state_snapshots.size()) {
        return result;
    }

    result.total_steps = static_cast<int64_t>(event_snapshots.size());

    for (size_t i = 0; i < event_snapshots.size(); ++i) {
        const EventSnapshot& ev = event_snapshots[i];
        result.per_operation_counts[ev.operation]++;

        if (ev.wrap_occurred)
            result.wrap_total++, result.wrap_by_operation[ev.operation]++;

        int64_t y0 = projection_values[i];
        int64_t y1 = projection_values[i + 1];
        if (y1 == y0) {
            if (state_snapshots[i + 1].value_x == state_snapshots[i].value_x) {
                result.trivial_self_loop_total++;
                result.trivial_self_loop_by_operation[ev.operation]++;
            } else {
                result.nontrivial_self_loop_total++;
                result.nontrivial_self_loop_by_operation[ev.operation]++;
            }
        }
    }
    return result;
}

MechanismSideMetricsResult compute_mechanism_side_metrics(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots,
    const std::vector<std::string>& wrap_directions) {

    MechanismSideMetricsResult result;
    if (state_snapshots.empty() || state_snapshots.size() != event_snapshots.size() + 1)
        return result;

    result.total_atomic_steps = static_cast<int64_t>(event_snapshots.size());
    bool use_wrap_dirs = (wrap_directions.size() == event_snapshots.size());

    for (size_t i = 0; i < event_snapshots.size(); ++i) {
        const EventSnapshot& ev = event_snapshots[i];
        result.operation_counts[ev.operation]++;
        std::string family = operation_family_from_operation_name(ev.operation);
        result.operation_family_counts[family]++;

        if (ev.wrap_occurred) {
            result.wrap_event_count++;
            result.wrap_event_count_by_operation_family[family]++;
        }
        if (use_wrap_dirs) {
            const std::string& wd = wrap_directions[i];
            if (wd == "up" || wd == "down" || wd == "none")
                result.wrap_direction_counts[wd]++;
        }

        result.delta_sum += ev.boundary_quotient_delta;
        if (ev.carry && *ev.carry != 0)
            result.carry_event_count += static_cast<int64_t>(*ev.carry);
        if (ev.borrow && *ev.borrow != 0)
            result.borrow_event_count += static_cast<int64_t>(*ev.borrow);
        if (family == "cross_domain")
            result.cross_domain_event_count++;
    }

    result.wrap_event_rate = safe_divide(
        static_cast<double>(result.wrap_event_count),
        static_cast<double>(result.total_atomic_steps));

    if (!state_snapshots.empty()) {
        result.information_height_in_building_final = state_snapshots.back().current_building_height;
        result.information_height_cross_final = state_snapshots.back().cross_building_event_count;
        int64_t max_ih = 0;
        for (const auto& s : state_snapshots) {
            if (s.current_building_height > max_ih)
                max_ih = s.current_building_height;
        }
        result.information_height_in_building_max = max_ih;
    }
    return result;
}

PatternSideMetricsResult compute_pattern_side_metrics(
    const std::vector<StateSnapshot>& state_snapshots,
    const std::vector<EventSnapshot>& event_snapshots,
    const std::vector<int64_t>& projection_values,
    std::optional<int64_t> observed_space_size) {

    PatternSideMetricsResult result;
    if (projection_values.size() != state_snapshots.size() ||
        state_snapshots.size() != event_snapshots.size() + 1) {
        return result;
    }

    result.projection = compute_projection_metrics(projection_values, observed_space_size);
    result.observed_space_size = observed_space_size;

    double total_steps = static_cast<double>(event_snapshots.size());
    for (size_t i = 0; i < event_snapshots.size(); ++i) {
        int64_t y0 = projection_values[i];
        int64_t y1 = projection_values[i + 1];
        std::string family = operation_family_from_operation_name(event_snapshots[i].operation);
        if (y1 == y0) {
            if (state_snapshots[i + 1].value_x == state_snapshots[i].value_x) {
                result.self_loop.trivial_self_loop_event_count++;
                result.self_loop.trivial_self_loop_event_count_by_operation_family[family]++;
            } else {
                result.self_loop.nontrivial_self_loop_event_count++;
                result.self_loop.nontrivial_self_loop_event_count_by_operation_family[family]++;
            }
        }
    }
    result.self_loop.trivial_self_loop_event_rate = safe_divide(
        static_cast<double>(result.self_loop.trivial_self_loop_event_count), total_steps);
    result.self_loop.nontrivial_self_loop_event_rate = safe_divide(
        static_cast<double>(result.self_loop.nontrivial_self_loop_event_count), total_steps);

    std::set<int64_t> seen;
    int64_t hits = 0;
    for (size_t t = 0; t < projection_values.size(); ++t) {
        int64_t y = projection_values[t];
        if (t > 0 && seen.count(y))
            hits++;
        seen.insert(y);
    }
    result.self_loop.self_intersection_rate = safe_divide(
        static_cast<double>(hits),
        static_cast<double>(projection_values.size() > 1 ? projection_values.size() - 1 : 1));

    return result;
}

} // namespace iwt
