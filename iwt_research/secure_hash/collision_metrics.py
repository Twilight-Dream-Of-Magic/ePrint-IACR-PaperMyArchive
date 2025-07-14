"""
Collision and convergence metrics for compression analysis.

Captures the "merging winding" structure specific to non-injective functions:
  - Collision counting and multi-collision distribution
  - Preimage size distribution (how many inputs map to each output)
  - Avalanche effect (1-bit input change -> output distance)
  - Merge depth (how many iterations until two random inputs converge)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple


@dataclass(frozen=True, slots=True)
class CollisionMetrics:
    state_count: int
    image_count: int
    collision_pair_count: int
    max_preimage_size: int
    mean_preimage_size: float
    preimage_size_histogram: Dict[int, int]
    multi_collision_counts: Dict[int, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state_count": int(self.state_count),
            "image_count": int(self.image_count),
            "collision_pair_count": int(self.collision_pair_count),
            "max_preimage_size": int(self.max_preimage_size),
            "mean_preimage_size": float(self.mean_preimage_size),
            "preimage_size_histogram": {str(k): int(v) for k, v in self.preimage_size_histogram.items()},
            "multi_collision_counts": {str(k): int(v) for k, v in self.multi_collision_counts.items()},
        }


def compute_collision_metrics(
    *,
    successor: Callable[[int], int],
    state_count: int,
) -> CollisionMetrics:
    """
    Exhaustive collision analysis for f: {0..state_count-1} -> {0..state_count-1}.
    Uses iwt_core (C++23) when available.
    """
    n = int(state_count)
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            successor_table = [int(successor(x)) for x in range(n)]
            result = iwt_core.compute_collision_metrics(successor_table, n)
            return CollisionMetrics(
                state_count=int(result.state_count),
                image_count=int(result.image_count),
                collision_pair_count=int(result.collision_pair_count),
                max_preimage_size=int(result.max_preimage_size),
                mean_preimage_size=float(result.mean_preimage_size),
                preimage_size_histogram=dict(result.preimage_size_histogram),
                multi_collision_counts=dict(result.multi_collision_counts),
            )
    except Exception:
        pass

    preimage_lists: Dict[int, List[int]] = {}
    for x in range(n):
        y = int(successor(x))
        if y < 0 or y >= n:
            y = y % n
        if y not in preimage_lists:
            preimage_lists[y] = []
        preimage_lists[y].append(x)

    image_count = len(preimage_lists)
    collision_pair_count = 0
    for y, preimages in preimage_lists.items():
        k = len(preimages)
        if k >= 2:
            collision_pair_count += k * (k - 1) // 2

    preimage_sizes = [len(v) for v in preimage_lists.values()]
    max_preimage = max(preimage_sizes) if preimage_sizes else 0
    mean_preimage = float(sum(preimage_sizes)) / float(len(preimage_sizes)) if preimage_sizes else 0.0
    preimage_hist: Dict[int, int] = {}
    for s in preimage_sizes:
        preimage_hist[s] = preimage_hist.get(s, 0) + 1
    multi_collision: Dict[int, int] = {}
    for k_threshold in [2, 3, 4, 5, 8, 16]:
        count = sum(1 for s in preimage_sizes if s >= k_threshold)
        if count > 0:
            multi_collision[k_threshold] = count

    return CollisionMetrics(
        state_count=n,
        image_count=image_count,
        collision_pair_count=collision_pair_count,
        max_preimage_size=max_preimage,
        mean_preimage_size=mean_preimage,
        preimage_size_histogram=preimage_hist,
        multi_collision_counts=multi_collision,
    )


@dataclass(frozen=True, slots=True)
class AvalancheMetrics:
    bit_width: int
    pair_count: int
    mean_hamming_distance: float
    mean_hamming_fraction: float
    min_hamming_distance: int
    max_hamming_distance: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "bit_width": int(self.bit_width),
            "pair_count": int(self.pair_count),
            "mean_hamming_distance": float(self.mean_hamming_distance),
            "mean_hamming_fraction": float(self.mean_hamming_fraction),
            "min_hamming_distance": int(self.min_hamming_distance),
            "max_hamming_distance": int(self.max_hamming_distance),
        }


def compute_avalanche(
    *,
    successor: Callable[[int], int],
    state_count: int,
    bit_width: int,
    sample_count: int = 0,
    rng_seed: int = 0,
) -> AvalancheMetrics:
    """
    Avalanche effect: for each input x, flip each bit and measure output Hamming distance.
    If sample_count > 0, sample that many inputs; otherwise exhaustive.
    Uses iwt_core (C++23) when available.
    """
    n = int(state_count)
    bw = int(bit_width)

    if sample_count > 0 and sample_count < n:
        rng = random.Random(int(rng_seed))
        input_sample = [rng.randrange(n) for _ in range(sample_count)]
    else:
        input_sample = list(range(n))

    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            successor_table = [int(successor(x)) for x in range(n)]
            result = iwt_core.compute_avalanche(
                successor_table, n, bw, input_sample,
            )
            return AvalancheMetrics(
                bit_width=int(result.bit_width),
                pair_count=int(result.pair_count),
                mean_hamming_distance=float(result.mean_hamming_distance),
                mean_hamming_fraction=float(result.mean_hamming_fraction),
                min_hamming_distance=int(result.min_hamming_distance),
                max_hamming_distance=int(result.max_hamming_distance),
            )
    except Exception:
        pass

    distances: List[int] = []
    for x in input_sample:
        y = int(successor(x))
        for bit in range(bw):
            x_flipped = x ^ (1 << bit)
            if x_flipped >= n:
                continue
            y_flipped = int(successor(x_flipped))
            hd = bin(y ^ y_flipped).count("1")
            distances.append(hd)

    if not distances:
        return AvalancheMetrics(
            bit_width=bw, pair_count=0,
            mean_hamming_distance=0.0, mean_hamming_fraction=0.0,
            min_hamming_distance=0, max_hamming_distance=0,
        )

    mean_hd = sum(distances) / float(len(distances))
    return AvalancheMetrics(
        bit_width=bw,
        pair_count=len(distances),
        mean_hamming_distance=float(mean_hd),
        mean_hamming_fraction=float(mean_hd) / float(bw) if bw > 0 else 0.0,
        min_hamming_distance=min(distances),
        max_hamming_distance=max(distances),
    )


@dataclass(frozen=True, slots=True)
class MergeDepthMetrics:
    pair_count: int
    mean_merge_depth: float
    max_merge_depth: int
    merged_fraction: float
    merge_depth_histogram: Dict[int, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pair_count": int(self.pair_count),
            "mean_merge_depth": float(self.mean_merge_depth),
            "max_merge_depth": int(self.max_merge_depth),
            "merged_fraction": float(self.merged_fraction),
            "merge_depth_histogram": {str(k): int(v) for k, v in self.merge_depth_histogram.items()},
        }


def compute_merge_depth(
    *,
    successor: Callable[[int], int],
    state_count: int,
    pair_count: int = 100,
    max_steps: int = 0,
    rng_seed: int = 0,
) -> MergeDepthMetrics:
    """
    Merge depth: for random pairs (a, b), iterate f on both until they
    reach the same value. The number of steps is the "merge depth" —
    the direct quantification of compression winding convergence.
    Uses iwt_core (C++23) when available.
    """
    n = int(state_count)
    if max_steps <= 0:
        max_steps = n * 2
    rng = random.Random(int(rng_seed))

    initial_pairs: List[Tuple[int, int]] = []
    for _ in range(int(pair_count)):
        a = rng.randrange(n)
        b = rng.randrange(n)
        if a == b:
            b = (b + 1) % n
        initial_pairs.append((a, b))

    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            successor_table = [int(successor(x)) for x in range(n)]
            result = iwt_core.compute_merge_depth(
                successor_table, n, initial_pairs, max_steps,
            )
            return MergeDepthMetrics(
                pair_count=int(result.pair_count),
                mean_merge_depth=float(result.mean_merge_depth),
                max_merge_depth=int(result.max_merge_depth),
                merged_fraction=float(result.merged_fraction),
                merge_depth_histogram=dict(result.merge_depth_histogram),
            )
    except Exception:
        pass

    depths: List[int] = []
    merged_count = 0
    for a, b in initial_pairs:
        ca, cb = a, b
        depth = 0
        found = False
        for _ in range(max_steps):
            if ca == cb:
                found = True
                break
            ca = int(successor(ca))
            cb = int(successor(cb))
            depth += 1
        if found:
            depths.append(depth)
            merged_count += 1

    hist: Dict[int, int] = {}
    for d in depths:
        hist[d] = hist.get(d, 0) + 1
    mean_depth = float(sum(depths)) / float(len(depths)) if depths else 0.0
    max_depth = max(depths) if depths else 0
    merged_frac = float(merged_count) / float(pair_count) if pair_count > 0 else 0.0

    return MergeDepthMetrics(
        pair_count=int(pair_count),
        mean_merge_depth=float(mean_depth),
        max_merge_depth=int(max_depth),
        merged_fraction=float(merged_frac),
        merge_depth_histogram=hist,
    )
