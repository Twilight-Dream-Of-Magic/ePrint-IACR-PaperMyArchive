"""
Information Winding Theory toy engineering kit (清晰命名重构版).

Only Python standard library. Outputs reports into `iwt_research/report_out/` by default.
"""

from .version import __version__

from .core.ops_kernel import preflight_reduce
from .core.ops_trace import (
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
from .core.atomic_trace import AtomicEvent
from .analysis.baseline_models import (
    RandomARXLikeBaseline,
    RandomFunctionBaseline,
    RandomPermutationBaseline,
    RandomSubstitutionPermutationNetworkBaseline,
    RandomSubstitutionPermutationNetworkVectorBaseline,
)
from .core.discrete_domain import BinaryHypercubeMetrics, Domain, compute_binary_hypercube_metrics, delta, red
from .core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, InformationHeight, InFloorHistRecord
from .run_experiment import RunConfig, run_toy_iwt, write_report
from .ciphers.toy_arx_cipher import ToyARX, ToyARXConfig
from .ciphers.toy_spn import (
    ToySubstitutionPermutationNetwork,
    ToySubstitutionPermutationNetworkConfig,
)
from .ciphers.toy_spn_vector import (
    ToySubstitutionPermutationNetworkVector,
    ToySubstitutionPermutationNetworkVectorConfig,
)
