from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ..analysis.threat_model import ThreatModelLevel


@dataclass(frozen=True, slots=True)
class RunConfig:
    cipher_preset: str = "toy_arx"
    word_bits: int = 8
    lane_count: int = 4
    rounds: int = 16
    rotation_mode: str = "bits"
    rotation_direction: str = "l"
    trace_count: int = 200
    seed: int = 0
    projection: str = "lowbits:4"
    cross_domain_modulus: int | None = None
    cross_every_rounds: int = 4
    baselines: Tuple[str, ...] = ("random_arx_like", "random_permutation", "random_function")
    bootstrap_iters: int = 2000
    baseline_ensemble_samples: int = 200
    alpha: float = 0.01
    exhaustive: bool = False
    max_exhaustive_modulus: int = 4096
    max_exhaustive_state_count: int = 65536
    max_empirical_trace_count: int = 4096
    threat_model_level: str = ThreatModelLevel.threat_model_2_instrumented.value
    additional_projection_specs_csv: str | None = None
    false_discovery_rate: float = 0.10
    reachability_target_indices_csv: str | None = None
    threat_model_3_max_probes: int = 8
    threat_model_3_focus_topk: int = 4
    threat_model_3_window_radius: int = 2
    threat_model_3_intervention_budget: int = 64

