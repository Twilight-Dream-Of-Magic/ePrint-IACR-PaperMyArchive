from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True, slots=True)
class CycleDecompositionMetrics:
    state_count: int
    cycle_count: int
    fixed_point_count: int
    max_cycle_length: int
    mean_cycle_length: float
    cycle_length_histogram: Dict[int, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state_count": int(self.state_count),
            "cycle_count": int(self.cycle_count),
            "fixed_point_count": int(self.fixed_point_count),
            "max_cycle_length": int(self.max_cycle_length),
            "mean_cycle_length": float(self.mean_cycle_length),
            "cycle_length_histogram": {str(int(k)): int(v) for k, v in self.cycle_length_histogram.items()},
        }


def compute_cycle_decomposition_metrics_for_bijection(
    *,
    successor_of_index: Callable[[int], int],
    state_count: int,
) -> CycleDecompositionMetrics:
    """
    Exact cycle decomposition of a bijection f on {0..state_count-1}.
    This is the strict "unreachability by orbit separation" structure:
    different cycles are mutually unreachable by forward iteration.
    Uses iwt_core (C++23) when available.
    """
    n = int(state_count)
    if n <= 0:
        return CycleDecompositionMetrics(
            state_count=0,
            cycle_count=0,
            fixed_point_count=0,
            max_cycle_length=0,
            mean_cycle_length=0.0,
            cycle_length_histogram={},
        )
    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            successor_table = [int(successor_of_index(i)) for i in range(n)]
            result = iwt_core.compute_cycle_decomposition_metrics_for_bijection(successor_table, n)
            return CycleDecompositionMetrics(
                state_count=int(result.state_count),
                cycle_count=int(result.cycle_count),
                fixed_point_count=int(result.fixed_point_count),
                max_cycle_length=int(result.max_cycle_length),
                mean_cycle_length=float(result.mean_cycle_length),
                cycle_length_histogram=dict(result.cycle_length_histogram),
            )
    except Exception:
        pass
    visited = [False] * n
    cycle_lengths: List[int] = []
    histogram: Dict[int, int] = {}
    fixed_point_count = 0

    for start in range(n):
        if visited[start]:
            continue
        current = start
        index_seen_at: Dict[int, int] = {}
        step = 0
        while True:
            if visited[current]:
                for node in index_seen_at.keys():
                    visited[node] = True
                break
            if current in index_seen_at:
                cycle_start_step = int(index_seen_at[current])
                cycle_length = int(step - cycle_start_step)
                cycle_lengths.append(int(cycle_length))
                histogram[cycle_length] = int(histogram.get(cycle_length, 0)) + 1
                if cycle_length == 1:
                    fixed_point_count += 1
                for node in index_seen_at.keys():
                    visited[node] = True
                break
            index_seen_at[current] = int(step)
            step += 1
            current = int(successor_of_index(int(current)))
            if current < 0 or current >= n:
                raise ValueError("successor_of_index returned out-of-range index; mapping must be a bijection on [0..n)")

    if not cycle_lengths:
        return CycleDecompositionMetrics(
            state_count=n,
            cycle_count=0,
            fixed_point_count=0,
            max_cycle_length=0,
            mean_cycle_length=0.0,
            cycle_length_histogram={},
        )
    max_cycle_length = max(int(x) for x in cycle_lengths)
    mean_cycle_length = sum(float(x) for x in cycle_lengths) / float(len(cycle_lengths))
    return CycleDecompositionMetrics(
        state_count=n,
        cycle_count=int(len(cycle_lengths)),
        fixed_point_count=int(fixed_point_count),
        max_cycle_length=int(max_cycle_length),
        mean_cycle_length=float(mean_cycle_length),
        cycle_length_histogram=dict(histogram),
    )


def compute_reachability_queries_on_functional_graph(
    *,
    successor_of_index: Callable[[int], int],
    state_count: int,
    source_index: int,
    target_indices: List[int],
) -> Dict[str, Any]:
    """
    Exact reachability queries on a functional graph (outdegree=1).
    Returns, for each target:
    - reachable_by_forward_iteration: bool
    - steps_if_reachable: exact step count to first hit (within at most state_count steps)
    Uses iwt_core (C++23) when available.
    """
    n = int(state_count)
    source = int(source_index)
    if source < 0 or source >= n:
        raise ValueError("source_index out of range")

    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            successor_table = [int(successor_of_index(i)) for i in range(n)]
            result = iwt_core.compute_reachability_queries_on_functional_graph(
                successor_table, n, source, [int(t) for t in target_indices],
            )
            out = []
            for tr in result.targets:
                out.append({
                    "target_index": int(tr.target_index),
                    "reachable_by_forward_iteration": bool(tr.reachable_by_forward_iteration),
                    "steps_if_reachable": int(tr.steps_if_reachable) if tr.steps_if_reachable is not None else None,
                })
            return {
                "state_count": int(result.state_count),
                "source_index": int(result.source_index),
                "targets": out,
            }
    except Exception:
        pass

    target_set = {int(t) for t in target_indices if 0 <= int(t) < n}
    hits: Dict[int, int] = {}
    current = source
    for step in range(n + 1):
        if current in target_set and current not in hits:
            hits[current] = int(step)
            if len(hits) == len(target_set):
                break
        current = int(successor_of_index(int(current)))
        if current < 0 or current >= n:
            raise ValueError("successor_of_index returned out-of-range index")
        if current == source:
            break

    out = []
    for target in target_indices:
        t = int(target)
        if t < 0 or t >= n:
            out.append({"target_index": t, "reachable_by_forward_iteration": False, "steps_if_reachable": None})
        elif t in hits:
            out.append({"target_index": t, "reachable_by_forward_iteration": True, "steps_if_reachable": int(hits[t])})
        else:
            out.append({"target_index": t, "reachable_by_forward_iteration": False, "steps_if_reachable": None})
    return {
        "state_count": n,
        "source_index": source,
        "targets": out,
    }


__all__ = [
    "CycleDecompositionMetrics",
    "compute_cycle_decomposition_metrics_for_bijection",
    "compute_reachability_queries_on_functional_graph",
]
