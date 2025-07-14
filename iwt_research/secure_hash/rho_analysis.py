"""
Rho-structure analysis for general (non-bijective) functions f: {0..n-1} -> {0..n-1}.

A bijection's functional graph decomposes into disjoint cycles.
A general function's graph decomposes into the **rho-shape**:
  - Trees (tails) hanging off cycles
  - Each node has exactly one outgoing edge (deterministic)
  - Nodes on cycles have period; tail nodes eventually reach a cycle

This captures the "compression winding" structure:
  - Tail nodes represent paths that CONVERGE (merge) into cycles
  - Multiple paths merging = the "two paths stacked together" winding the user described
  - In-degree > 1 at a node = collision = merge point
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True, slots=True)
class RhoStructureMetrics:
    state_count: int
    image_count: int
    collision_count: int
    cycle_count: int
    cycle_length_histogram: Dict[int, int]
    total_cycle_nodes: int
    tail_node_count: int
    tail_length_histogram: Dict[int, int]
    max_tail_length: int
    mean_tail_length: float
    max_in_degree: int
    in_degree_histogram: Dict[int, int]
    tree_count: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state_count": int(self.state_count),
            "image_count": int(self.image_count),
            "collision_count": int(self.collision_count),
            "cycle_count": int(self.cycle_count),
            "cycle_length_histogram": {str(k): int(v) for k, v in self.cycle_length_histogram.items()},
            "total_cycle_nodes": int(self.total_cycle_nodes),
            "tail_node_count": int(self.tail_node_count),
            "tail_length_histogram": {str(k): int(v) for k, v in self.tail_length_histogram.items()},
            "max_tail_length": int(self.max_tail_length),
            "mean_tail_length": float(self.mean_tail_length),
            "max_in_degree": int(self.max_in_degree),
            "in_degree_histogram": {str(k): int(v) for k, v in self.in_degree_histogram.items()},
            "tree_count": int(self.tree_count),
        }


def compute_rho_structure(
    *,
    successor: Callable[[int], int],
    state_count: int,
) -> RhoStructureMetrics:
    """
    Exhaustive rho-structure decomposition for f: {0..state_count-1} -> {0..state_count-1}.

    Algorithm:
    1. Build full successor table + in-degree table
    2. Find all cycle nodes (iteratively strip tail nodes with in-degree 0 after
       removing already-processed tails)
    3. For each non-cycle node, compute tail length (distance to nearest cycle node)
    4. Compute all structural metrics
    """
    n = int(state_count)
    if n <= 0:
        return _empty_metrics()

    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            successor_table = []
            for x in range(n):
                y = int(successor(x))
                if y < 0 or y >= n:
                    y = y % n
                successor_table.append(y)
            r = iwt_core.compute_rho_structure(successor_table, n)
            cycle_length_histogram = {int(k): int(v) for k, v in r.cycle_length_histogram.items()}
            tail_length_histogram = {int(k): int(v) for k, v in r.tail_length_histogram.items()}
            in_degree_histogram = {int(k): int(v) for k, v in r.in_degree_histogram.items()}
            return RhoStructureMetrics(
                state_count=int(r.state_count),
                image_count=int(r.image_count),
                collision_count=int(r.collision_count),
                cycle_count=int(r.cycle_count),
                cycle_length_histogram=cycle_length_histogram,
                total_cycle_nodes=int(r.total_cycle_nodes),
                tail_node_count=int(r.tail_node_count),
                tail_length_histogram=tail_length_histogram,
                max_tail_length=int(r.max_tail_length),
                mean_tail_length=float(r.mean_tail_length),
                max_in_degree=int(r.max_in_degree),
                in_degree_histogram=in_degree_histogram,
                tree_count=int(r.tree_count),
            )
    except Exception:
        pass

    succ = [0] * n
    in_deg = [0] * n
    image_set: set[int] = set()

    for x in range(n):
        y = int(successor(x))
        if y < 0 or y >= n:
            y = y % n
        succ[x] = y
        in_deg[y] += 1
        image_set.add(y)

    image_count = len(image_set)
    collision_count = n - image_count

    on_cycle = [False] * n
    visited = [0] * n  # 0=unvisited, 1=in-progress, 2=done

    for start in range(n):
        if visited[start] == 2:
            continue

        path: List[int] = []
        path_set: Dict[int, int] = {}
        node = start

        while visited[node] == 0 and node not in path_set:
            path_set[node] = len(path)
            path.append(node)
            visited[node] = 1
            node = succ[node]

        if visited[node] == 1 and node in path_set:
            cycle_start_idx = path_set[node]
            for i in range(cycle_start_idx, len(path)):
                on_cycle[path[i]] = True

        for p in path:
            visited[p] = 2

    cycle_nodes = [i for i in range(n) if on_cycle[i]]
    total_cycle_nodes = len(cycle_nodes)
    tail_node_count = n - total_cycle_nodes

    cycle_lengths: List[int] = []
    cycle_visited = [False] * n
    for node in range(n):
        if not on_cycle[node] or cycle_visited[node]:
            continue
        length = 0
        cur = node
        while not cycle_visited[cur]:
            cycle_visited[cur] = True
            length += 1
            cur = succ[cur]
        cycle_lengths.append(length)

    cycle_count = len(cycle_lengths)
    cycle_length_hist: Dict[int, int] = {}
    for cl in cycle_lengths:
        cycle_length_hist[cl] = cycle_length_hist.get(cl, 0) + 1

    tail_length = [-1] * n
    for i in range(n):
        if on_cycle[i]:
            tail_length[i] = 0

    changed = True
    while changed:
        changed = False
        for i in range(n):
            if tail_length[i] >= 0:
                continue
            s = succ[i]
            if tail_length[s] >= 0:
                tail_length[i] = tail_length[s] + 1
                changed = True

    for i in range(n):
        if tail_length[i] < 0:
            tail_length[i] = n

    tail_length_hist: Dict[int, int] = {}
    for i in range(n):
        if not on_cycle[i]:
            tl = tail_length[i]
            tail_length_hist[tl] = tail_length_hist.get(tl, 0) + 1

    max_tail = max((tail_length[i] for i in range(n) if not on_cycle[i]), default=0)
    sum_tail = sum(tail_length[i] for i in range(n) if not on_cycle[i])
    mean_tail = float(sum_tail) / float(tail_node_count) if tail_node_count > 0 else 0.0

    in_deg_hist: Dict[int, int] = {}
    max_in_deg = 0
    for i in range(n):
        d = in_deg[i]
        in_deg_hist[d] = in_deg_hist.get(d, 0) + 1
        if d > max_in_deg:
            max_in_deg = d

    tree_roots = set()
    for i in range(n):
        if on_cycle[i] and in_deg[i] > 1:
            tree_roots.add(i)
        elif on_cycle[i]:
            has_tail_child = False
            for j in range(n):
                if succ[j] == i and not on_cycle[j]:
                    has_tail_child = True
                    break
            if has_tail_child:
                tree_roots.add(i)
    tree_count = len(tree_roots)

    return RhoStructureMetrics(
        state_count=n,
        image_count=image_count,
        collision_count=collision_count,
        cycle_count=cycle_count,
        cycle_length_histogram=cycle_length_hist,
        total_cycle_nodes=total_cycle_nodes,
        tail_node_count=tail_node_count,
        tail_length_histogram=tail_length_hist,
        max_tail_length=max_tail,
        mean_tail_length=mean_tail,
        max_in_degree=max_in_deg,
        in_degree_histogram=in_deg_hist,
        tree_count=tree_count,
    )


def _empty_metrics() -> RhoStructureMetrics:
    return RhoStructureMetrics(
        state_count=0,
        image_count=0,
        collision_count=0,
        cycle_count=0,
        cycle_length_histogram={},
        total_cycle_nodes=0,
        tail_node_count=0,
        tail_length_histogram={},
        max_tail_length=0,
        mean_tail_length=0.0,
        max_in_degree=0,
        in_degree_histogram={},
        tree_count=0,
    )
