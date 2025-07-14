from __future__ import annotations

from typing import Any, Dict, List

from ...core.atomic_trace import AtomicEvent
from ...core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState
from .cross_domain import compute_cross_domain_switching_pattern
from .information_height import compute_information_height_profile
from .joint_value_height import compute_joint_value_height_analysis
from .snapshots import trajectory_semantics_metadata


def compute_winding_trajectory_report(
    *,
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
    events: List[AtomicEvent],
) -> Dict[str, Any]:
    backend_meta: Dict[str, Any] = {}
    trajectory_semantics = trajectory_semantics_metadata(states)
    height_profile = compute_information_height_profile(
        states=states,
        events=events,
        backend_meta=backend_meta,
    )
    switching_pattern = compute_cross_domain_switching_pattern(
        states=states,
        events=events,
        backend_meta=backend_meta,
    )
    joint_analysis = compute_joint_value_height_analysis(
        states=states,
        backend_meta=backend_meta,
    )

    return {
        "information_height_profile": height_profile.as_dict(),
        "cross_domain_switching_pattern": switching_pattern.as_dict(),
        "joint_value_height_analysis": joint_analysis.as_dict(),
        "trajectory_semantics": trajectory_semantics,
        "computation_backend": backend_meta,
    }


def aggregate_winding_trajectory_reports(
    reports: List[Dict[str, Any]],
) -> Dict[str, Any]:
    n = len(reports)
    if n == 0:
        return {"trace_count": 0}

    final_heights = []
    max_heights = []
    mean_increments = []
    burst_counts = []
    cross_domain_totals = []
    net_counters = []
    distinct_pairs_list = []
    intersection_rates = []
    backend_counts: Dict[str, int] = {}
    encoding_counts: Dict[str, int] = {}

    for r in reports:
        hp = r.get("information_height_profile", {})
        final_heights.append(int(hp.get("final_height", 0)))
        max_heights.append(int(hp.get("max_height", 0)))
        mean_increments.append(float(hp.get("mean_increment_per_step", 0)))
        burst_counts.append(int(hp.get("burst_step_count", 0)))

        sp = r.get("cross_domain_switching_pattern", {})
        cross_domain_totals.append(int(sp.get("total_cross_domain_events", 0)))
        net_counters.append(int(sp.get("net_cross_domain_counter", 0)))

        ja = r.get("joint_value_height_analysis", {})
        distinct_pairs_list.append(int(ja.get("distinct_value_height_pairs", 0)))
        intersection_rates.append(float(ja.get("trajectory_self_intersection_rate", 0)))

        semantics = r.get("trajectory_semantics", {})
        if isinstance(semantics, dict):
            enc = str(semantics.get("state_value_encoding", "") or "")
            if enc:
                encoding_counts[enc] = int(encoding_counts.get(enc, 0)) + 1
        backend = r.get("computation_backend", {})
        if isinstance(backend, dict):
            for key in (
                "information_height_profile",
                "cross_domain_switching_pattern",
                "joint_value_height_analysis",
            ):
                section = backend.get(key, {})
                if not isinstance(section, dict):
                    continue
                backend_name = str(section.get("backend", "") or "")
                if not backend_name:
                    continue
                label = f"{key}:{backend_name}"
                backend_counts[label] = int(backend_counts.get(label, 0)) + 1

    def _stats(values: List[float]) -> Dict[str, float]:
        if not values:
            return {"mean": 0.0, "min": 0.0, "max": 0.0}
        return {
            "mean": sum(values) / float(len(values)),
            "min": float(min(values)),
            "max": float(max(values)),
        }

    return {
        "trace_count": int(n),
        "information_height_summary": {
            "final_height": _stats([float(v) for v in final_heights]),
            "max_height": _stats([float(v) for v in max_heights]),
            "mean_increment_per_step": _stats(mean_increments),
            "burst_step_count": _stats([float(v) for v in burst_counts]),
        },
        "cross_domain_summary": {
            "total_cross_domain_events": _stats([float(v) for v in cross_domain_totals]),
            "net_cross_domain_counter": _stats([float(v) for v in net_counters]),
        },
        "joint_value_height_summary": {
            "distinct_value_height_pairs": _stats([float(v) for v in distinct_pairs_list]),
            "trajectory_self_intersection_rate": _stats(intersection_rates),
        },
        "trajectory_semantics_summary": {
            "state_value_encoding_counts": {str(k): int(v) for k, v in encoding_counts.items()},
        },
        "computation_backend_summary": {
            "section_backend_counts": {str(k): int(v) for k, v in backend_counts.items()},
        },
    }

