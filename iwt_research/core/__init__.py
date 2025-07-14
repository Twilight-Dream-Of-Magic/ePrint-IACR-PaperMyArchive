"""Information Winding Theory core domain model and atomic operator interfaces."""

from .ops_kernel import preflight_reduce
from .ops_trace import (
    add,
    cross_domain,
    cross_floor,
    permute_bits,
    permute_values,
    rotl_bits,
    rotr_bits,
    sub,
    substitute_box,
    xor,
)
from .atomic_trace import AtomicEvent
from .discrete_domain import (
    BinaryHypercubeMetrics,
    Domain,
    compute_binary_hypercube_metrics,
    delta,
    is_power_of_two,
    red,
)
from .enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, InformationHeight, InFloorHistRecord

__all__ = [
    "add", "cross_domain", "cross_floor", "permute_bits", "permute_values", "preflight_reduce",
    "rotl_bits", "rotr_bits",
    "sub", "substitute_box", "xor",
    "AtomicEvent",
    "Domain", "delta", "is_power_of_two", "red",
    "BinaryHypercubeMetrics", "compute_binary_hypercube_metrics",
    "DiscreteHighdimensionalInformationSpace_TrackTrajectoryState", "InformationHeight", "InFloorHistRecord",
]
