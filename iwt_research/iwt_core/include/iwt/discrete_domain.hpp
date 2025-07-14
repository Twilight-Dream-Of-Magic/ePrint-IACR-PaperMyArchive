#pragma once

#include <cstdint>

namespace iwt {

/// Discrete domain: representative interval [representative, representative + modulus).
/// Paper: D=(q,w), Omega_D = {w, w+1, ..., w+q-1}. Full names only: modulus, representative.
struct Domain {
    int64_t modulus{2};
    int64_t representative{0};

    constexpr Domain() = default;
    constexpr Domain(int64_t modulus_, int64_t representative_ = 0)
        : modulus(modulus_), representative(representative_) {}

    constexpr int64_t upper_bound() const noexcept { return representative + modulus; }
    constexpr bool is_binary() const noexcept { return modulus == 2 && representative == 0; }
};

/// Representative reduction: Red(z) = representative + ((z - representative) mod modulus). Paper §2.3.
inline int64_t representative_reduction(const Domain& domain, int64_t z) noexcept {
    int64_t remainder = (z - domain.representative) % domain.modulus;
    if (remainder < 0) remainder += domain.modulus;
    return domain.representative + remainder;
}

/// Boundary quotient: Delta(z) = floor((z - representative) / modulus). Paper §2.3.
inline int64_t boundary_quotient(const Domain& domain, int64_t z) noexcept {
    return (z - domain.representative) / domain.modulus;
}

inline bool is_power_of_two(int64_t n) noexcept {
    return n > 0 && (n & (n - 1)) == 0;
}

} // namespace iwt
