from __future__ import annotations

from typing import Any, Dict

from ..analysis.threat_model import ThreatModelLevel, parse_threat_model_level
from .block_core import compute_block_core_artifacts
from .config import RunConfig
from .tm1_runner import attach_tm1_multi_projection_scan, attach_tm1_observation_evidence
from .types import RunArtifacts, TraceBatchArtifacts


def run_block_pipeline(run_config: RunConfig) -> RunArtifacts:
    """
    Execute the block-cipher pipeline core.

    Runs block core directly and exposes context required by downstream
    pipeline stages (exhaustive/baseline/lesion).
    """
    threat_model_level = parse_threat_model_level(run_config.threat_model_level)
    core = compute_block_core_artifacts(
        run_config=run_config,
        threat_model_level=threat_model_level,
    )
    result: Dict[str, Any] = dict(core.result)
    attach_tm1_observation_evidence(
        result=result,
        primary_projection_spec=str(core.primary_projection_spec),
    )
    attach_tm1_multi_projection_scan(
        run_config=run_config,
        result=result,
        threat_model_level=threat_model_level,
        cipher=core.cipher,
        registered_projections=list(core.registered_projections),
        state_indices=[int(x) for x in core.state_indices],
        total_steps=int(core.total_steps),
    )
    trace_batch = TraceBatchArtifacts(
        metrics={
            "bootstrap_confidence_intervals": result.get("bootstrap_confidence_intervals", {}),
            "slice_shadow_metrics": result.get("slice_shadow_metrics", {}),
            "non_degeneracy_report": result.get("non_degeneracy_report", {}),
        },
        example=(result.get("example_trace", {}) if isinstance(result.get("example_trace"), dict) else {}),
        state_indices=[int(x) for x in core.state_indices],
    )
    return RunArtifacts(
        run_config=run_config,
        threat_model_level=threat_model_level,
        result=result,
        trace_batch=trace_batch,
        working={
            "cipher": core.cipher,
            "registered_projections": list(core.registered_projections),
            "primary_projection_spec": str(core.primary_projection_spec),
            "projection": core.projection,
            "state_indices": [int(x) for x in core.state_indices],
            "total_steps": int(core.total_steps),
            "omega_core_size": int(core.omega_core_size),
            "empirical_adjacency": core.empirical_adjacency,
            "empirical_sources": core.empirical_sources,
            "edge_counts_total": dict(core.edge_counts_total),
            "region_agg_total": dict(core.region_agg_total),
            "ys_all": [list(int(v) for v in ys) for ys in core.ys_all],
            "max_abs_quotient_per_trace": [
                float(v) for v in core.max_abs_quotient_per_trace
            ],
            "snapshot_count_per_trace": [int(v) for v in core.snapshot_count_per_trace],
        },
    )


__all__ = ["run_block_pipeline"]
