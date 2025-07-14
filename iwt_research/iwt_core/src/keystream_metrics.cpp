#include "iwt/keystream_metrics.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <random>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace iwt {

PeriodDetectionResult detect_period_brent(const std::vector<int64_t>& keystream) {
    PeriodDetectionResult result;
    result.method = "brent";
    size_t stream_length = keystream.size();
    if (stream_length < 2) {
        result.method = "brent";
        return result;
    }

    size_t power = 1;
    size_t cycle_length = 1;
    size_t tortoise_idx = 0;
    size_t hare_idx = 1;

    while (hare_idx < stream_length && keystream[tortoise_idx] != keystream[hare_idx]) {
        if (power == cycle_length) {
            tortoise_idx = hare_idx;
            power *= 2;
            cycle_length = 0;
        }
        hare_idx += 1;
        cycle_length += 1;
    }

    if (hare_idx >= stream_length) {
        result.period = 0;
        result.tail_length = static_cast<int64_t>(stream_length);
        result.total_rho_length = static_cast<int64_t>(stream_length);
        result.method = "brent_no_cycle_in_window";
        return result;
    }

    int64_t period = static_cast<int64_t>(cycle_length);

    tortoise_idx = 0;
    hare_idx = cycle_length;
    size_t tail_start_index = 0;
    while (hare_idx < stream_length && keystream[tortoise_idx] != keystream[hare_idx]) {
        tortoise_idx += 1;
        hare_idx += 1;
        tail_start_index += 1;
    }

    if (hare_idx >= stream_length) {
        result.period = 0;
        result.tail_length = static_cast<int64_t>(stream_length);
        result.total_rho_length = static_cast<int64_t>(stream_length);
        result.method = "brent_no_cycle_in_window";
        return result;
    }

    size_t verify_limit = std::min(static_cast<size_t>(period), stream_length - tail_start_index - static_cast<size_t>(period));
    bool verified = true;
    for (size_t offset = 0; offset < verify_limit; ++offset) {
        if (keystream[tail_start_index + offset] != keystream[tail_start_index + static_cast<size_t>(period) + offset]) {
            verified = false;
            break;
        }
    }

    if (!verified) {
        result.period = 0;
        result.tail_length = static_cast<int64_t>(stream_length);
        result.total_rho_length = static_cast<int64_t>(stream_length);
        result.method = "brent_verification_failed";
        return result;
    }

    result.period = period;
    result.tail_length = static_cast<int64_t>(tail_start_index);
    result.total_rho_length = static_cast<int64_t>(tail_start_index) + period;
    result.method = "brent";
    return result;
}

AutocorrelationResult compute_autocorrelation(
    const std::vector<int64_t>& keystream,
    int max_lag) {
    AutocorrelationResult result;
    size_t stream_length = keystream.size();
    if (stream_length < 2) {
        result.max_lag = 0;
        return result;
    }
    std::vector<double> float_values;
    float_values.reserve(stream_length);
    for (int64_t value : keystream)
        float_values.push_back(static_cast<double>(value));
    double sum_value = 0;
    for (double value : float_values)
        sum_value += value;
    double mean_value = sum_value / static_cast<double>(stream_length);
    double variance = 0;
    for (double value : float_values)
        variance += (value - mean_value) * (value - mean_value);
    if (variance < 1e-15) {
        result.max_lag = static_cast<int64_t>(max_lag);
        result.values.resize(static_cast<size_t>(max_lag), 0.0);
        return result;
    }
    int actual_max_lag = std::min(max_lag, static_cast<int>(stream_length) - 1);
    result.max_lag = actual_max_lag;
    result.values.reserve(static_cast<size_t>(actual_max_lag));
    for (int lag = 1; lag <= actual_max_lag; ++lag) {
        double covariance = 0;
        for (size_t index = 0; index + static_cast<size_t>(lag) < stream_length; ++index)
            covariance += (float_values[index] - mean_value) * (float_values[index + static_cast<size_t>(lag)] - mean_value);
        result.values.push_back(covariance / variance);
    }
    return result;
}

CoverageResult compute_coverage(
    const std::vector<int64_t>& keystream,
    int64_t state_space_size) {
    CoverageResult result;
    size_t stream_length = keystream.size();
    result.output_length = static_cast<int64_t>(stream_length);
    result.state_space_size = state_space_size;
    if (stream_length == 0 || state_space_size <= 0) {
        result.coverage_fraction = 0.0;
        result.statistical_distance_from_uniform = 0.0;
        return result;
    }
    std::unordered_set<int64_t> distinct_set;
    std::unordered_map<int64_t, int64_t> counts;
    for (int64_t value : keystream) {
        distinct_set.insert(value);
        counts[value] = counts[value] + 1;
    }
    result.distinct_values = static_cast<int64_t>(distinct_set.size());
    result.coverage_fraction = static_cast<double>(result.distinct_values) / static_cast<double>(state_space_size);
    double expected_count = static_cast<double>(stream_length) / static_cast<double>(state_space_size);
    double total_deviation = 0;
    for (int64_t value = 0; value < state_space_size; ++value) {
        int64_t count = 0;
        auto it = counts.find(value);
        if (it != counts.end())
            count = it->second;
        total_deviation += std::abs(static_cast<double>(count) - expected_count);
    }
    result.statistical_distance_from_uniform = total_deviation / (2.0 * static_cast<double>(stream_length));
    return result;
}

BootstrapCIResult bootstrap_ci(
    const std::vector<double>& values,
    int64_t seed,
    int iterations,
    double alpha) {
    BootstrapCIResult result;
    size_t sample_size = values.size();
    if (sample_size == 0) {
        result.mean = std::numeric_limits<double>::quiet_NaN();
        result.lower_bound = std::numeric_limits<double>::quiet_NaN();
        result.upper_bound = std::numeric_limits<double>::quiet_NaN();
        return result;
    }
    std::mt19937 random_generator(static_cast<unsigned>(seed & 0xFFFFFFFFu));
    std::uniform_int_distribution<size_t> index_distribution(0, sample_size - 1);
    std::vector<double> bootstrap_means;
    bootstrap_means.reserve(static_cast<size_t>(iterations));
    for (int bootstrap_index = 0; bootstrap_index < iterations; ++bootstrap_index) {
        double sum = 0;
        for (size_t index = 0; index < sample_size; ++index)
            sum += values[index_distribution(random_generator)];
        bootstrap_means.push_back(sum / static_cast<double>(sample_size));
    }
    std::sort(bootstrap_means.begin(), bootstrap_means.end());
    size_t lower_index = static_cast<size_t>((alpha / 2.0) * iterations);
    size_t upper_index = static_cast<size_t>((1.0 - alpha / 2.0) * iterations);
    if (upper_index > 0) --upper_index;
    if (upper_index >= bootstrap_means.size()) upper_index = bootstrap_means.size() - 1;
    result.lower_bound = bootstrap_means[lower_index];
    result.upper_bound = bootstrap_means[upper_index];
    double mean_sum = 0;
    for (double value : values)
        mean_sum += value;
    result.mean = mean_sum / static_cast<double>(sample_size);
    return result;
}

SeedSensitivityResult compute_seed_sensitivity(
    const std::vector<int64_t>& keystream_base,
    const std::vector<std::vector<int64_t>>& neighbor_keystreams,
    const std::vector<int64_t>& neighbor_seeds) {

    SeedSensitivityResult result;
    size_t base_length = keystream_base.size();
    size_t num_neighbors = std::min(neighbor_keystreams.size(), neighbor_seeds.size());
    result.per_pair.reserve(num_neighbors);

    double sum_first_div = 0;
    double sum_hamming_frac = 0;

    for (size_t p = 0; p < num_neighbors; ++p) {
        const std::vector<int64_t>& neighbor = neighbor_keystreams[p];
        size_t length = std::min(base_length, neighbor.size());
        int64_t first_diff = static_cast<int64_t>(length);
        int64_t diff_count = 0;
        for (size_t i = 0; i < length; ++i) {
            if (keystream_base[i] != neighbor[i]) {
                diff_count++;
                if (first_diff == static_cast<int64_t>(length))
                    first_diff = static_cast<int64_t>(i);
            }
        }
        double hamming_frac = (length > 0) ? (static_cast<double>(diff_count) / static_cast<double>(length)) : 0.0;

        SeedSensitivityPerPairResult pr;
        pr.neighbor_seed = neighbor_seeds[p];
        pr.first_divergence_position = first_diff;
        pr.hamming_distance = diff_count;
        pr.hamming_fraction = hamming_frac;
        pr.length_compared = static_cast<int64_t>(length);
        result.per_pair.push_back(pr);

        sum_first_div += static_cast<double>(first_diff);
        sum_hamming_frac += hamming_frac;
    }

    result.pair_count = static_cast<int64_t>(result.per_pair.size());
    if (result.pair_count > 0) {
        result.mean_first_divergence_position = sum_first_div / static_cast<double>(result.pair_count);
        result.mean_hamming_fraction = sum_hamming_frac / static_cast<double>(result.pair_count);
    }
    return result;
}

} // namespace iwt
