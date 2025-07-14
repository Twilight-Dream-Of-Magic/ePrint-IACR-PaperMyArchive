#pragma once

#include "discrete_domain.hpp"
#include <cstdint>
#include <string>
#include <tuple>

namespace iwt {

/// Preflight reduction: PF_D(z) = (x', delta, wrap, dir). Paper §2.5; Python: preflight_reduce(domain, raw).
/// Returns (representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction).
inline std::tuple<int64_t, int64_t, bool, std::string> preflight_reduce(
    const Domain& domain, int64_t raw)
{
    const int64_t w = domain.representative;
    const int64_t upper = domain.upper_bound();
    if (w <= raw && raw < upper)
        return {raw, 0, false, "none"};
    int64_t boundary_quotient_delta = boundary_quotient(domain, raw);
    int64_t representative_after_reduction = representative_reduction(domain, raw);
    const char* wrap_direction = raw >= upper ? "up" : "down";
    return {representative_after_reduction, boundary_quotient_delta, true, wrap_direction};
}

} // namespace iwt
