from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True, slots=True)
class EmpiricalReachabilityMetrics:
    """
    Discrete high-dimensional geometry as a point-set directed graph.

    Nodes: visited points in Omega^n (empirical support).
    Edges: one-step transitions observed in traces.

    Reachability/unreachability are defined relative to this empirical graph:
    - reachable: reachable from a chosen source set within the graph
    - unreachable: nodes in the empirical graph not reachable from the sources
    """

    node_count: int
    directed_edge_count: int
    source_node_count: int
    reachable_node_count: int
    unreachable_node_count: int
    unreachable_fraction: float
    in_degree_zero_node_count: int
    max_out_degree: int
    mean_out_degree: float
    branching_node_count: int
    branching_node_fraction: float
    sink_node_count: int
    sink_node_fraction: float
    max_shortest_path_distance: int
    mean_shortest_path_distance: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "node_count": int(self.node_count),
            "directed_edge_count": int(self.directed_edge_count),
            "source_node_count": int(self.source_node_count),
            "reachable_node_count": int(self.reachable_node_count),
            "unreachable_node_count": int(self.unreachable_node_count),
            "unreachable_fraction": float(self.unreachable_fraction),
            "in_degree_zero_node_count": int(self.in_degree_zero_node_count),
            "max_out_degree": int(self.max_out_degree),
            "mean_out_degree": float(self.mean_out_degree),
            "branching_node_count": int(self.branching_node_count),
            "branching_node_fraction": float(self.branching_node_fraction),
            "sink_node_count": int(self.sink_node_count),
            "sink_node_fraction": float(self.sink_node_fraction),
            "max_shortest_path_distance": int(self.max_shortest_path_distance),
            "mean_shortest_path_distance": float(self.mean_shortest_path_distance),
        }


def _nodes_from_adjacency(adjacency: Dict[Any, Iterable[Any]]) -> set[Any]:
    nodes: set[Any] = set()
    for source, targets in adjacency.items():
        nodes.add(source)
        for target in targets:
            nodes.add(target)
    return nodes


def compute_empirical_reachability_metrics(
    *,
    adjacency: Dict[Any, Iterable[Any]],
    sources: List[Any],
) -> EmpiricalReachabilityMetrics:
    """
    Compute reachability/unreachability on a directed graph.

    - adjacency: mapping node -> iterable of outgoing neighbors
    - sources: starting nodes for reachability
    Uses iwt_core (C++23) when available for BFS.
    """
    nodes = _nodes_from_adjacency(adjacency)
    if not nodes:
        return EmpiricalReachabilityMetrics(
            node_count=0,
            directed_edge_count=0,
            source_node_count=len(sources),
            reachable_node_count=0,
            unreachable_node_count=0,
            unreachable_fraction=0.0,
            in_degree_zero_node_count=0,
            max_out_degree=0,
            mean_out_degree=0.0,
            branching_node_count=0,
            branching_node_fraction=0.0,
            sink_node_count=0,
            sink_node_fraction=0.0,
            max_shortest_path_distance=0,
            mean_shortest_path_distance=0.0,
        )

    out_degree: Dict[Any, int] = {node: 0 for node in nodes}
    branching_node_count = 0
    sink_node_count = 0
    directed_edge_count_unique = 0
    for node in nodes:
        unique_targets = {target for target in adjacency.get(node, ()) if target in nodes}
        deg = int(len(unique_targets))
        out_degree[node] = deg
        directed_edge_count_unique += deg
        if deg > 1:
            branching_node_count += 1
        if deg == 0:
            sink_node_count += 1
    node_count = int(len(nodes))
    max_out_degree = max(int(v) for v in out_degree.values()) if out_degree else 0
    mean_out_degree = float(directed_edge_count_unique) / float(node_count) if node_count else 0.0
    branching_node_fraction = float(branching_node_count) / float(node_count) if node_count else 0.0
    sink_node_fraction = float(sink_node_count) / float(node_count) if node_count else 0.0

    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            node_list = list(nodes)
            node_to_idx = {n: i for i, n in enumerate(node_list)}
            adjacency_index: List[List[int]] = [
                [node_to_idx[t] for t in adjacency.get(n, []) if t in node_to_idx]
                for n in node_list
            ]
            source_indices = [node_to_idx[s] for s in sources if s in node_to_idx]
            result = iwt_core.compute_empirical_reachability_metrics(adjacency_index, source_indices)
            return EmpiricalReachabilityMetrics(
                node_count=int(result.node_count),
                directed_edge_count=int(result.directed_edge_count),
                source_node_count=int(result.source_node_count),
                reachable_node_count=int(result.reachable_node_count),
                unreachable_node_count=int(result.unreachable_node_count),
                unreachable_fraction=float(result.unreachable_fraction),
                in_degree_zero_node_count=int(result.in_degree_zero_node_count),
                max_out_degree=int(max_out_degree),
                mean_out_degree=float(mean_out_degree),
                branching_node_count=int(branching_node_count),
                branching_node_fraction=float(branching_node_fraction),
                sink_node_count=int(sink_node_count),
                sink_node_fraction=float(sink_node_fraction),
                max_shortest_path_distance=int(result.max_shortest_path_distance),
                mean_shortest_path_distance=float(result.mean_shortest_path_distance),
            )
    except Exception:
        pass

    in_degree: Dict[Any, int] = {node: 0 for node in nodes}
    directed_edge_count = 0
    for source, targets in adjacency.items():
        for target in targets:
            directed_edge_count += 1
            in_degree[target] = int(in_degree.get(target, 0)) + 1
            if source not in in_degree:
                in_degree[source] = int(in_degree.get(source, 0))

    in_degree_zero_node_count = sum(1 for node in nodes if int(in_degree.get(node, 0)) == 0)

    reached: set[Any] = set()
    distance: Dict[Any, int] = {}
    frontier: List[Any] = []
    for source in sources:
        if source in nodes and source not in reached:
            reached.add(source)
            distance[source] = 0
            frontier.append(source)

    head = 0
    while head < len(frontier):
        node = frontier[head]
        head += 1
        next_distance = int(distance.get(node, 0)) + 1
        for neighbor in adjacency.get(node, ()):
            if neighbor not in nodes:
                continue
            if neighbor in reached:
                continue
            reached.add(neighbor)
            distance[neighbor] = next_distance
            frontier.append(neighbor)

    reachable_node_count = int(len(reached))
    unreachable_node_count = int(node_count - reachable_node_count)
    unreachable_fraction = float(unreachable_node_count) / float(node_count) if node_count else 0.0

    if distance:
        max_shortest_path_distance = max(int(v) for v in distance.values())
        mean_shortest_path_distance = sum(float(v) for v in distance.values()) / float(len(distance))
    else:
        max_shortest_path_distance = 0
        mean_shortest_path_distance = 0.0

    return EmpiricalReachabilityMetrics(
        node_count=node_count,
        directed_edge_count=int(directed_edge_count),
        source_node_count=int(len(sources)),
        reachable_node_count=reachable_node_count,
        unreachable_node_count=unreachable_node_count,
        unreachable_fraction=float(unreachable_fraction),
        in_degree_zero_node_count=int(in_degree_zero_node_count),
        max_out_degree=int(max_out_degree),
        mean_out_degree=float(mean_out_degree),
        branching_node_count=int(branching_node_count),
        branching_node_fraction=float(branching_node_fraction),
        sink_node_count=int(sink_node_count),
        sink_node_fraction=float(sink_node_fraction),
        max_shortest_path_distance=int(max_shortest_path_distance),
        mean_shortest_path_distance=float(mean_shortest_path_distance),
    )


def add_trace_to_empirical_adjacency(
    *,
    adjacency: Dict[Any, set[Any]],
    trace_nodes: List[Any],
) -> None:
    if len(trace_nodes) < 2:
        return
    for i in range(len(trace_nodes) - 1):
        source = trace_nodes[i]
        target = trace_nodes[i + 1]
        if source not in adjacency:
            adjacency[source] = set()
        adjacency[source].add(target)


__all__ = [
    "EmpiricalReachabilityMetrics",
    "add_trace_to_empirical_adjacency",
    "compute_empirical_reachability_metrics",
]
