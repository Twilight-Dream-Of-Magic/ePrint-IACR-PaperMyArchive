#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace iwt {

/// Result of Brent's cycle detection on a keystream. Matches Python PeriodDetectionResult.
struct PeriodDetectionResult {
    int64_t period{0};
    int64_t tail_length{0};
    int64_t total_rho_length{0};
    std::string method;
};

/// Brent's cycle detection: find period and tail length such that
/// keystream[tail_length] == keystream[tail_length + period].
PeriodDetectionResult detect_period_brent(const std::vector<int64_t>& keystream);

/// Autocorrelation result. Matches Python AutocorrelationResult.
struct AutocorrelationResult {
    int64_t max_lag{0};
    std::vector<double> values;
};

/// Normalized autocorrelation at lags 1..max_lag.
AutocorrelationResult compute_autocorrelation(
    const std::vector<int64_t>& keystream,
    int max_lag = 32);

/// Coverage result. Matches Python CoverageResult.
struct CoverageResult {
    int64_t output_length{0};
    int64_t distinct_values{0};
    int64_t state_space_size{0};
    double coverage_fraction{0.0};
    double statistical_distance_from_uniform{0.0};
};

/// Coverage and statistical distance from uniform.
CoverageResult compute_coverage(
    const std::vector<int64_t>& keystream,
    int64_t state_space_size);

/// Bootstrap CI result (mean, lower_bound, upper_bound). Default stat = mean.
struct BootstrapCIResult {
    double mean{0.0};
    double lower_bound{0.0};
    double upper_bound{0.0};
};

/// Bootstrap confidence interval with default stat = mean.
BootstrapCIResult bootstrap_ci(
    const std::vector<double>& values,
    int64_t seed,
    int iterations = 2000,
    double alpha = 0.05);

/// One pair in seed sensitivity: base vs neighbor keystream.
struct SeedSensitivityPerPairResult {
    int64_t neighbor_seed{0};
    int64_t first_divergence_position{0};
    int64_t hamming_distance{0};
    double hamming_fraction{0.0};
    int64_t length_compared{0};
};

/// Result of seed sensitivity (how quickly neighbor seeds diverge).
struct SeedSensitivityResult {
    int64_t pair_count{0};
    double mean_first_divergence_position{0.0};
    double mean_hamming_fraction{0.0};
    std::vector<SeedSensitivityPerPairResult> per_pair;
};

/// Compare base keystream to each neighbor; first divergence position and Hamming fraction.
SeedSensitivityResult compute_seed_sensitivity(
    const std::vector<int64_t>& keystream_base,
    const std::vector<std::vector<int64_t>>& neighbor_keystreams,
    const std::vector<int64_t>& neighbor_seeds);

} // namespace iwt
