from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Domain:
    """
    Discrete domain with representative interval [representative, representative + modulus).
    Paper: D=(q,w), Omega_D = {w, w+1, ..., w+q-1}. Full names: modulus, representative.
    """

    modulus: int
    representative: int = 0

    def __post_init__(self) -> None:
        if self.modulus < 2:
            raise ValueError("modulus must be >= 2")

    @property
    def q(self) -> int:
        """Alias for modulus (paper q)."""
        return self.modulus

    @property
    def w(self) -> int:
        """Alias for representative (paper w)."""
        return self.representative

    @property
    def v(self) -> int:
        """Upper bound of representative interval: representative + modulus (paper v = w+q)."""
        return self.representative + self.modulus

    @property
    def is_binary(self) -> bool:
        return self.modulus == 2 and self.representative == 0

    @property
    def wrap_event_is_informative(self) -> bool:
        """
        Engineering guard rail for modulus=2 hypercube space:
        raw wrap occurrence tends to be a high-baseline / saturating statistic,
        so "wrap happened?" is usually not used as a lesion signal; prefer
        distribution / patterns (shadowing, NSL, intersections).
        """
        return not self.is_binary


@dataclass(frozen=True, slots=True)
class BinaryHypercubeMetrics:
    """
    Exact geometry summary on an observed directed graph over {0,1}^n.

    The graph is typically empirical (collected from traces), but the metrics
    are defined with respect to the canonical q=2 hypercube geometry.
    """

    dimension: int
    full_node_count: int
    observed_node_count: int
    observed_coverage_fraction: float
    observed_directed_edge_count: int
    zero_hamming_edge_fraction: float
    one_hamming_edge_fraction: float
    multi_hamming_edge_fraction: float
    mean_edge_hamming_distance: float
    max_edge_hamming_distance: int
    axis_flip_counts: list[int]
    axis_flip_balance_l1: float
    hamming_weight_histogram: Dict[str, int]
    edge_hamming_distance_histogram: Dict[str, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "dimension": int(self.dimension),
            "full_node_count": int(self.full_node_count),
            "observed_node_count": int(self.observed_node_count),
            "observed_coverage_fraction": float(self.observed_coverage_fraction),
            "observed_directed_edge_count": int(self.observed_directed_edge_count),
            "zero_hamming_edge_fraction": float(self.zero_hamming_edge_fraction),
            "one_hamming_edge_fraction": float(self.one_hamming_edge_fraction),
            "multi_hamming_edge_fraction": float(self.multi_hamming_edge_fraction),
            "mean_edge_hamming_distance": float(self.mean_edge_hamming_distance),
            "max_edge_hamming_distance": int(self.max_edge_hamming_distance),
            "axis_flip_counts": [int(x) for x in self.axis_flip_counts],
            "axis_flip_balance_l1": float(self.axis_flip_balance_l1),
            "hamming_weight_histogram": dict(self.hamming_weight_histogram),
            "edge_hamming_distance_histogram": dict(self.edge_hamming_distance_histogram),
        }

def red(domain: Domain, z: int) -> int:
    """Representative reduction: Red_{q,w}(z) = representative + ((z-representative) mod modulus). Paper §2.3."""
    from ..native import iwt_core, available as _native_available
    if _native_available and iwt_core is not None:
        cpp_domain = iwt_core.Domain(domain.modulus, domain.representative)
        return int(iwt_core.representative_reduction(cpp_domain, z))
    raise RuntimeError(
        "iwt_core (C++ extension) is required for red() (representative_reduction). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


def delta(domain: Domain, z: int) -> int:
    """
    Boundary quotient: Delta_{q,w}(z) = floor((z-representative)/modulus). Paper §2.3.
    """
    from ..native import iwt_core, available as _native_available
    if _native_available and iwt_core is not None:
        cpp_domain = iwt_core.Domain(domain.modulus, domain.representative)
        return int(iwt_core.boundary_quotient(cpp_domain, z))
    raise RuntimeError(
        "iwt_core (C++ extension) is required for delta() (boundary_quotient). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


def is_power_of_two(n: int) -> bool:
    from ..native import iwt_core, available as _native_available
    if _native_available and iwt_core is not None:
        native_fn = getattr(iwt_core, "is_power_of_two", None)
        if callable(native_fn):
            return bool(native_fn(n))
    # Compatibility fallback: some older native builds may not export is_power_of_two.
    # Keep behavior deterministic instead of raising AttributeError at runtime.
    x = int(n)
    return x > 0 and (x & (x - 1)) == 0


def compute_binary_hypercube_metrics(
    *,
    domain: Domain,
    adjacency: Mapping[Sequence[int], Iterable[Sequence[int]]],
    dimension: int,
) -> BinaryHypercubeMetrics:
    """
    Analyze an observed directed graph in modulus=2 (binary) high-dimensional space Omega^n.

    Parameters:
    - domain: must satisfy modulus=2, representative=0.
    - adjacency: directed graph adjacency (node -> iterable of neighbors).
    - dimension: n in Omega^n = {0,1}^n.
    """
    if not domain.is_binary:
        raise ValueError("binary hypercube metrics require modulus=2 and representative=0")
    dim = int(dimension)
    if dim <= 0:
        raise ValueError("dimension must be positive")

    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            adj_list: list[tuple[list[int], list[list[int]]]] = []
            for source, targets in adjacency.items():
                src_list = [int(x) for x in source]
                tgt_list = [[int(x) for x in t] for t in targets]
                adj_list.append((src_list, tgt_list))
            cpp_result = iwt_core.compute_binary_hypercube_metrics(dim, adj_list)
            return BinaryHypercubeMetrics(
                dimension=cpp_result.dimension,
                full_node_count=int(cpp_result.full_node_count),
                observed_node_count=int(cpp_result.observed_node_count),
                observed_coverage_fraction=float(cpp_result.observed_coverage_fraction),
                observed_directed_edge_count=int(cpp_result.observed_directed_edge_count),
                zero_hamming_edge_fraction=float(cpp_result.zero_hamming_edge_fraction),
                one_hamming_edge_fraction=float(cpp_result.one_hamming_edge_fraction),
                multi_hamming_edge_fraction=float(cpp_result.multi_hamming_edge_fraction),
                mean_edge_hamming_distance=float(cpp_result.mean_edge_hamming_distance),
                max_edge_hamming_distance=int(cpp_result.max_edge_hamming_distance),
                axis_flip_counts=[int(x) for x in cpp_result.axis_flip_counts],
                axis_flip_balance_l1=float(cpp_result.axis_flip_balance_l1),
                hamming_weight_histogram=dict(cpp_result.hamming_weight_histogram),
                edge_hamming_distance_histogram=dict(cpp_result.edge_hamming_distance_histogram),
            )
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for compute_binary_hypercube_metrics(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )

