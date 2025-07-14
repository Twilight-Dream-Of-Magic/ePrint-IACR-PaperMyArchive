from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True, slots=True)
class NeighborSeparationMetrics:
    rounds: int
    pair_count: int
    mean_bit_hamming_distance_by_time: List[float]
    p99_bit_hamming_distance_by_time: List[float]
    mean_lane_difference_count_by_time: List[float]
    p99_lane_difference_count_by_time: List[float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rounds": int(self.rounds),
            "pair_count": int(self.pair_count),
            "mean_bit_hamming_distance_by_time": list(self.mean_bit_hamming_distance_by_time),
            "p99_bit_hamming_distance_by_time": list(self.p99_bit_hamming_distance_by_time),
            "mean_lane_difference_count_by_time": list(self.mean_lane_difference_count_by_time),
            "p99_lane_difference_count_by_time": list(self.p99_lane_difference_count_by_time),
        }


def _p99(values: List[int]) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(int(v) for v in values)
    idx = int(0.99 * (len(values_sorted) - 1)) if len(values_sorted) > 1 else 0
    return float(values_sorted[idx])


def compute_neighbor_separation_metrics(
    *,
    cipher: Any,
    seed: int,
    pair_count: int,
) -> NeighborSeparationMetrics:
    """
    High-dimensional signature:
    measure how a one-bit local perturbation separates over time in Omega^n.

    Contract required from cipher:
    - iter_neighbor_pairs(seed=..., pair_count=...) -> iterable of (lanes_a, lanes_b)
    - run_from_lanes(lanes) -> (states, events) where states[t].x is lanes tuple
    - bit_hamming_distance(lanes_a, lanes_b) -> int
    - lane_difference_count(lanes_a, lanes_b) -> int
    """
    pairs = list(cipher.iter_neighbor_pairs(seed=int(seed), pair_count=int(pair_count)))
    if not pairs:
        return NeighborSeparationMetrics(
            rounds=0,
            pair_count=0,
            mean_bit_hamming_distance_by_time=[],
            p99_bit_hamming_distance_by_time=[],
            mean_lane_difference_count_by_time=[],
            p99_lane_difference_count_by_time=[],
        )

    states0, _ = cipher.run_from_lanes(pairs[0][0])
    time_length = len(states0)
    bit_dists_by_time: List[List[int]] = [[] for _ in range(time_length)]
    lane_diffs_by_time: List[List[int]] = [[] for _ in range(time_length)]

    for lanes_a, lanes_b in pairs:
        states_a, _ = cipher.run_from_lanes(lanes_a)
        states_b, _ = cipher.run_from_lanes(lanes_b)
        if len(states_a) != time_length or len(states_b) != time_length:
            raise ValueError("all traces must have the same length for neighbor separation metrics")
        for t in range(time_length):
            xa = tuple(states_a[t].x)  # type: ignore[arg-type]
            xb = tuple(states_b[t].x)  # type: ignore[arg-type]
            bit_dists_by_time[t].append(int(cipher.bit_hamming_distance(xa, xb)))
            lane_diffs_by_time[t].append(int(cipher.lane_difference_count(xa, xb)))

    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            result = iwt_core.compute_neighbor_separation_aggregate(bit_dists_by_time, lane_diffs_by_time)
            return NeighborSeparationMetrics(
                rounds=int(result.rounds),
                pair_count=int(result.pair_count),
                mean_bit_hamming_distance_by_time=[float(x) for x in result.mean_bit_hamming_distance_by_time],
                p99_bit_hamming_distance_by_time=[float(x) for x in result.p99_bit_hamming_distance_by_time],
                mean_lane_difference_count_by_time=[float(x) for x in result.mean_lane_difference_count_by_time],
                p99_lane_difference_count_by_time=[float(x) for x in result.p99_lane_difference_count_by_time],
            )
    except Exception:
        pass

    mean_bit = [sum(v) / len(v) if v else 0.0 for v in bit_dists_by_time]
    p99_bit = [_p99(v) for v in bit_dists_by_time]
    mean_lane = [sum(v) / len(v) if v else 0.0 for v in lane_diffs_by_time]
    p99_lane = [_p99(v) for v in lane_diffs_by_time]
    rounds = max(0, time_length - 1)
    return NeighborSeparationMetrics(
        rounds=int(rounds),
        pair_count=int(len(pairs)),
        mean_bit_hamming_distance_by_time=[float(x) for x in mean_bit],
        p99_bit_hamming_distance_by_time=[float(x) for x in p99_bit],
        mean_lane_difference_count_by_time=[float(x) for x in mean_lane],
        p99_lane_difference_count_by_time=[float(x) for x in p99_lane],
    )


__all__ = [
    "NeighborSeparationMetrics",
    "compute_neighbor_separation_metrics",
]
