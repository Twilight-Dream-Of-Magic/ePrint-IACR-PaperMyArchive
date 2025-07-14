from __future__ import annotations

import math
import random
from typing import Any, List


def is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def mean(values: List[float]) -> float:
    return (sum(float(x) for x in values) / float(len(values))) if values else float("nan")


def stddev(values: List[float]) -> float:
    if not values or len(values) < 2:
        return float("nan")
    mu = mean(values)
    var = sum((float(x) - float(mu)) ** 2 for x in values) / float(len(values) - 1)
    return float(var**0.5)


def z_score(x: float, mu: float, sigma: float, eps: float = 1e-12) -> float | None:
    if (not is_finite_number(x)) or (not is_finite_number(mu)) or (not is_finite_number(sigma)):
        return None
    if float(sigma) <= float(eps):
        return None
    return (float(x) - float(mu)) / float(sigma)


def quantile(sorted_values: List[float], q: float) -> float:
    """
    Nearest-rank-like quantile used throughout the toy code.
    Input is expected to be a list already sorted in ascending order.
    """
    if not sorted_values:
        return float("nan")
    q = min(1.0, max(0.0, float(q)))
    idx = int(round(q * (len(sorted_values) - 1)))
    return float(sorted_values[idx])


def empirical_p_ge(samples: List[float], x: float) -> float:
    """
    Empirical upper-tail p-value with +1 smoothing:
      p = (1 + #{s >= x}) / (n + 1)
    """
    if not samples:
        return float("nan")
    n = int(len(samples))
    k = sum(1 for s in samples if float(s) >= float(x))
    return (1.0 + float(k)) / (float(n) + 1.0)


def empirical_p_le(samples: List[float], x: float) -> float:
    if not samples:
        return float("nan")
    n = int(len(samples))
    k = sum(1 for s in samples if float(s) <= float(x))
    return (1.0 + float(k)) / (float(n) + 1.0)


def empirical_quantile_pos(samples: List[float], x: float) -> float:
    """
    Fraction of samples <= x (no smoothing).
    """
    if not samples:
        return float("nan")
    n = int(len(samples))
    k = sum(1 for s in samples if float(s) <= float(x))
    return float(k) / float(n) if n else float("nan")


def two_sided_from_one_sided(p_le: float, p_ge: float) -> float:
    if p_le != p_le or p_ge != p_ge:
        return float("nan")
    return min(1.0, 2.0 * min(float(p_le), float(p_ge)))


def deterministic_seed_pool(seed: int, n: int) -> List[int]:
    """
    Deterministic integer seed pool for trace selection / reproducible planning.
    """
    rng = random.Random(int(seed))
    return [int(rng.randrange(2**31 - 1)) for _ in range(int(n))]
