"""
Keystream metrics for stream cipher / PRG expansion analysis.

Captures the IWT "direction-only winding" structure:
  - Period detection (small-scale exact via Brent, large-scale estimate)
  - Autocorrelation (lag-k correlation of keystream values)
  - Seed sensitivity (how quickly two neighboring seeds diverge)
  - Output-space coverage (fraction of Omega reached)
  - Statistical distance from uniform
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True, slots=True)
class PeriodDetectionResult:
    period: int
    tail_length: int
    total_rho_length: int
    method: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "period": int(self.period),
            "tail_length": int(self.tail_length),
            "total_rho_length": int(self.total_rho_length),
            "method": str(self.method),
        }


def detect_period_brent(keystream: List[int]) -> PeriodDetectionResult:
    """
    Brent's cycle detection on a keystream sequence.
    Returns (period, tail_length) where:
      keystream[tail_length] == keystream[tail_length + period]
    """
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            r = iwt_core.detect_period_brent([int(x) for x in keystream])
            return PeriodDetectionResult(
                period=int(r.period),
                tail_length=int(r.tail_length),
                total_rho_length=int(r.total_rho_length),
                method=str(r.method),
            )
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for detect_period_brent(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


@dataclass(frozen=True, slots=True)
class AutocorrelationResult:
    max_lag: int
    values: List[float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "max_lag": int(self.max_lag),
            "values": [float(v) for v in self.values],
        }


def compute_autocorrelation(keystream: List[int], max_lag: int = 32) -> AutocorrelationResult:
    """
    Normalized autocorrelation of keystream at lags 1..max_lag.
    Values near 0 = no correlation (good PRG); large |values| = structure leak.
    """
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            r = iwt_core.compute_autocorrelation([int(x) for x in keystream], int(max_lag))
            return AutocorrelationResult(max_lag=int(r.max_lag), values=[float(v) for v in r.values])
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for compute_autocorrelation(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


@dataclass(frozen=True, slots=True)
class SeedSensitivityResult:
    pair_count: int
    mean_first_divergence_position: float
    mean_hamming_fraction: float
    per_pair: List[Dict[str, Any]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pair_count": int(self.pair_count),
            "mean_first_divergence_position": float(self.mean_first_divergence_position),
            "mean_hamming_fraction": float(self.mean_hamming_fraction),
            "per_pair": list(self.per_pair),
        }


def compute_seed_sensitivity(
    keystream_base: List[int],
    neighbor_keystreams: List[List[int]],
    neighbor_seeds: List[int],
) -> SeedSensitivityResult:
    """
    Measure how quickly keystreams from neighboring seeds diverge.
    This quantifies the "direction change" aspect of expansion winding.
    Uses iwt_core (C++23) when available.
    """
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            base_cpp = [int(x) for x in keystream_base]
            neighbors_cpp = [[int(x) for x in ks] for ks in neighbor_keystreams]
            seeds_cpp = [int(s) for s in neighbor_seeds]
            result = iwt_core.compute_seed_sensitivity(base_cpp, neighbors_cpp, seeds_cpp)
            per_pair = [
                {
                    "neighbor_seed": int(p.neighbor_seed),
                    "first_divergence_position": int(p.first_divergence_position),
                    "hamming_distance": int(p.hamming_distance),
                    "hamming_fraction": float(p.hamming_fraction),
                    "length_compared": int(p.length_compared),
                }
                for p in result.per_pair
            ]
            return SeedSensitivityResult(
                pair_count=int(result.pair_count),
                mean_first_divergence_position=float(result.mean_first_divergence_position),
                mean_hamming_fraction=float(result.mean_hamming_fraction),
                per_pair=per_pair,
            )
    except Exception:
        pass

    n = len(keystream_base)
    per_pair = []
    for ks_neighbor, ns in zip(neighbor_keystreams, neighbor_seeds):
        length = min(n, len(ks_neighbor))
        first_diff = length
        diff_count = 0
        for i in range(length):
            if keystream_base[i] != ks_neighbor[i]:
                diff_count += 1
                if first_diff == length:
                    first_diff = i
        hamming_frac = float(diff_count) / float(length) if length > 0 else 0.0
        per_pair.append({
            "neighbor_seed": int(ns),
            "first_divergence_position": int(first_diff),
            "hamming_distance": int(diff_count),
            "hamming_fraction": float(hamming_frac),
            "length_compared": int(length),
        })

    if per_pair:
        mean_fdp = sum(float(p["first_divergence_position"]) for p in per_pair) / float(len(per_pair))
        mean_hf = sum(float(p["hamming_fraction"]) for p in per_pair) / float(len(per_pair))
    else:
        mean_fdp = 0.0
        mean_hf = 0.0

    return SeedSensitivityResult(
        pair_count=len(per_pair),
        mean_first_divergence_position=float(mean_fdp),
        mean_hamming_fraction=float(mean_hf),
        per_pair=per_pair,
    )


@dataclass(frozen=True, slots=True)
class CoverageResult:
    output_length: int
    distinct_values: int
    state_space_size: int
    coverage_fraction: float
    statistical_distance_from_uniform: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "output_length": int(self.output_length),
            "distinct_values": int(self.distinct_values),
            "state_space_size": int(self.state_space_size),
            "coverage_fraction": float(self.coverage_fraction),
            "statistical_distance_from_uniform": float(self.statistical_distance_from_uniform),
        }


def compute_coverage(keystream: List[int], state_space_size: int) -> CoverageResult:
    """
    Coverage and statistical distance from uniform for the keystream.
    """
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            r = iwt_core.compute_coverage([int(x) for x in keystream], int(state_space_size))
            return CoverageResult(
                output_length=int(r.output_length),
                distinct_values=int(r.distinct_values),
                state_space_size=int(r.state_space_size),
                coverage_fraction=float(r.coverage_fraction),
                statistical_distance_from_uniform=float(r.statistical_distance_from_uniform),
            )
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for compute_coverage(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )
