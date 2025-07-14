from __future__ import annotations

from typing import Any, Dict, List, Tuple


def compute_lane_coupling_matrix(
    *,
    cipher: Any,
    seed: int,
    samples_per_source_lane: int,
) -> Dict[str, Any]:
    """
    Coupling signature:
    flip one bit in a source lane and estimate which target lanes differ after full rounds.

    Output:
    - coupling_probability[source_lane][target_lane] in [0,1]
    Uses iwt_core (C++23) when available for aggregation.
    """
    random_pairs = list(cipher.iter_neighbor_pairs(seed=int(seed), pair_count=int(samples_per_source_lane) * 64))
    if not random_pairs:
        return {"lane_count": 0, "coupling_probability": []}

    lane_count = len(random_pairs[0][0])
    source_and_differing_targets: List[Tuple[int, List[int]]] = []
    used = 0
    for lanes_a, lanes_b in random_pairs:
        diff_lanes = [i for i, (x, y) in enumerate(zip(lanes_a, lanes_b)) if int(x) != int(y)]
        if len(diff_lanes) != 1:
            continue
        source_lane = int(diff_lanes[0])
        states_a, _ = cipher.run_from_lanes(lanes_a)
        states_b, _ = cipher.run_from_lanes(lanes_b)
        xa = tuple(states_a[-1].x)  # type: ignore[arg-type]
        xb = tuple(states_b[-1].x)  # type: ignore[arg-type]
        differing = [t for t in range(lane_count) if int(xa[t]) != int(xb[t])]
        source_and_differing_targets.append((source_lane, differing))
        used += 1
        if used >= int(samples_per_source_lane) * int(lane_count):
            break

    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            result = iwt_core.compute_lane_coupling_from_diffs(lane_count, source_and_differing_targets)
            return {
                "lane_count": int(result.lane_count),
                "samples_per_source_lane_effective": [int(x) for x in result.samples_per_source_lane_effective],
                "coupling_probability": [list(map(float, row)) for row in result.coupling_probability],
            }
    except Exception:
        pass

    counts = [[0 for _ in range(lane_count)] for _ in range(lane_count)]
    totals = [0 for _ in range(lane_count)]
    for source_lane, differing in source_and_differing_targets:
        totals[source_lane] += 1
        for target_lane in differing:
            counts[source_lane][target_lane] += 1
    probabilities = []
    for source_lane in range(lane_count):
        denom = max(1, int(totals[source_lane]))
        probabilities.append([float(counts[source_lane][t]) / float(denom) for t in range(lane_count)])
    return {
        "lane_count": int(lane_count),
        "samples_per_source_lane_effective": list(int(x) for x in totals),
        "coupling_probability": probabilities,
    }


__all__ = ["compute_lane_coupling_matrix"]
