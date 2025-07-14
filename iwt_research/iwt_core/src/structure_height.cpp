#include "iwt/structure_height.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace iwt {

namespace {

int64_t sbox_best_lift(
    int64_t output_t,
    int64_t lifted_prev,
    int64_t modulus_q) {
    if (modulus_q <= 0) return 0;
    int64_t diff = lifted_prev - output_t;
    int64_t candidate_lift = (diff + (modulus_q / 2)) / modulus_q;
    int64_t best_lift = candidate_lift;
    int64_t best_dist = std::abs(output_t + best_lift * modulus_q - lifted_prev);
    for (int64_t delta : {int64_t{-1}, int64_t{1}}) {
        int64_t k = candidate_lift + delta;
        int64_t dist = std::abs(output_t + k * modulus_q - lifted_prev);
        if (dist < best_dist) {
            best_dist = dist;
            best_lift = k;
        } else if (dist == best_dist && std::abs(k) < std::abs(best_lift)) {
            best_lift = k;
        } else if (dist == best_dist && std::abs(k) == std::abs(best_lift) && k < best_lift) {
            best_lift = k;
        }
    }
    return best_lift;
}

} // namespace

std::vector<int64_t> sbox_lifted_sequence(
    const std::vector<int64_t>& output_sequence,
    int64_t modulus_q,
    int64_t window_start) {
    std::vector<int64_t> lifted;
    const size_t length = output_sequence.size();
    if (length != static_cast<size_t>(modulus_q) || modulus_q <= 0)
        return lifted;
    (void)window_start;
    lifted.reserve(length);
    lifted.push_back(output_sequence[0]);
    int64_t lifted_prev = output_sequence[0];
    for (size_t t = 1; t < length; ++t) {
        int64_t output_t = output_sequence[t];
        int64_t k_t = sbox_best_lift(output_t, lifted_prev, modulus_q);
        lifted_prev = output_t + k_t * modulus_q;
        lifted.push_back(lifted_prev);
    }
    return lifted;
}

std::vector<int64_t> per_step_structure_increments_sbox(
    const std::vector<int64_t>& output_sequence,
    int64_t modulus_q,
    int64_t window_start) {
    std::vector<int64_t> result;
    const size_t length = output_sequence.size();
    if (length != static_cast<size_t>(modulus_q) || modulus_q <= 0) {
        result.resize(static_cast<size_t>(std::max(modulus_q, int64_t(1))), 0);
        return result;
    }
    std::vector<int64_t> lift_coefficients;
    lift_coefficients.push_back(0);
    int64_t lifted_prev = output_sequence[0];
    for (size_t t = 1; t < length; ++t) {
        int64_t output_t = output_sequence[t];
        int64_t k_t = sbox_best_lift(output_t, lifted_prev, modulus_q);
        lift_coefficients.push_back(k_t);
        lifted_prev = output_t + k_t * modulus_q;
    }
    result.push_back(lift_coefficients[0]);
    for (size_t t = 1; t < lift_coefficients.size(); ++t)
        result.push_back(lift_coefficients[t] - lift_coefficients[t - 1]);
    return result;
}

int64_t pbox_structure_increment_at(
    int64_t input_index,
    int64_t output_value,
    int64_t modulus_q,
    int64_t /*window_start*/) {
    if (modulus_q <= 0) return 0;
    struct Candidate { int64_t dist; int64_t delta; };
    std::array<Candidate, 3> candidates = {{
        {std::abs(output_value - input_index), 0},
        {std::abs((output_value + modulus_q) - input_index), 1},
        {std::abs((output_value - modulus_q) - input_index), -1},
    }};
    std::sort(candidates.begin(), candidates.end(),
        [](const Candidate& a, const Candidate& b) {
            if (a.dist != b.dist) return a.dist < b.dist;
            if (std::abs(a.delta) != std::abs(b.delta)) return std::abs(a.delta) < std::abs(b.delta);
            return a.delta < b.delta;
        });
    return candidates[0].delta;
}

std::vector<int64_t> per_step_structure_increments_pbox(
    const std::vector<int64_t>& output_sequence,
    int64_t modulus_q,
    int64_t window_start) {
    std::vector<int64_t> result;
    if (static_cast<int64_t>(output_sequence.size()) != modulus_q || modulus_q <= 0) {
        result.resize(static_cast<size_t>(std::max(modulus_q, int64_t(1))), 0);
        return result;
    }
    for (int64_t t = 0; t < modulus_q; ++t) {
        int64_t input_index = window_start + t;
        int64_t output_value = output_sequence[static_cast<size_t>(t)];
        result.push_back(pbox_structure_increment_at(
            input_index, output_value, modulus_q, window_start));
    }
    return result;
}

} // namespace iwt
