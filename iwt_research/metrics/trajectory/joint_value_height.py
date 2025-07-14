from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ...core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState
from .snapshots import (
    contains_vector_state,
    state_value_for_joint_analysis,
    states_events_to_snapshots,
)


@dataclass(frozen=True, slots=True)
class JointValueHeightAnalysis:
    trajectory_length: int
    distinct_value_height_pairs: int
    trajectory_self_intersection_count: int
    trajectory_self_intersection_rate: float
    value_spread_at_height_levels: List[Dict[str, Any]]
    trajectory_sample_head: List[Dict[str, Any]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "trajectory_length": int(self.trajectory_length),
            "distinct_value_height_pairs": int(self.distinct_value_height_pairs),
            "trajectory_self_intersection_count": int(self.trajectory_self_intersection_count),
            "trajectory_self_intersection_rate": float(self.trajectory_self_intersection_rate),
            "value_spread_at_height_levels": list(self.value_spread_at_height_levels),
            "trajectory_sample_head": list(self.trajectory_sample_head),
        }


def compute_joint_value_height_analysis(
    *,
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
    backend_meta: Dict[str, Any] | None = None,
) -> JointValueHeightAnalysis:
    has_vector_state = contains_vector_state(states)
    if not has_vector_state:
        try:
            from ...native import available as _native_available, iwt_core

            if _native_available and iwt_core is not None:
                state_snapshots, _ = states_events_to_snapshots(states, [], backend_meta=backend_meta)
                if state_snapshots:
                    r = iwt_core.compute_joint_value_height_analysis(state_snapshots)
                    value_spread_at_height_levels = [
                        {
                            "information_height_level": int(lev.information_height_level),
                            "distinct_values_visited": int(lev.distinct_values_visited),
                            "visit_count": int(lev.visit_count),
                        }
                        for lev in r.value_spread_at_height_levels
                    ]
                    trajectory_sample_head = [
                        {
                            "time_step": int(s.time_step),
                            "value": int(s.value),
                            "information_height": int(s.information_height),
                        }
                        for s in r.trajectory_sample_head
                    ]
                    if backend_meta is not None:
                        backend_meta["joint_value_height_analysis"] = {"backend": "native_cpp"}
                    return JointValueHeightAnalysis(
                        trajectory_length=int(r.trajectory_length),
                        distinct_value_height_pairs=int(r.distinct_value_height_pairs),
                        trajectory_self_intersection_count=int(r.trajectory_self_intersection_count),
                        trajectory_self_intersection_rate=float(r.trajectory_self_intersection_rate),
                        value_spread_at_height_levels=value_spread_at_height_levels,
                        trajectory_sample_head=trajectory_sample_head,
                    )
        except Exception as exc:
            if backend_meta is not None:
                backend_meta["joint_value_height_analysis"] = {
                    "backend": "python_fallback",
                    "reason": f"native_exception:{type(exc).__name__}",
                }
    else:
        if backend_meta is not None:
            backend_meta["joint_value_height_analysis"] = {
                "backend": "python_fallback",
                "reason": "vector_tuple_signature_required",
            }
    if backend_meta is not None and "joint_value_height_analysis" not in backend_meta:
        backend_meta["joint_value_height_analysis"] = {
            "backend": "python_fallback",
            "reason": "native_path_not_used",
        }
    pairs: List[Tuple[Any, int]] = []
    for s in states:
        val = state_value_for_joint_analysis(s)
        pairs.append((val, int(s.information_height.current_building_height)))

    n = len(pairs)
    pair_set: set = set()
    intersection_count = 0
    for p in pairs:
        if p in pair_set:
            intersection_count += 1
        pair_set.add(p)

    distinct = len(pair_set)
    intersection_rate = float(intersection_count) / float(n) if n > 0 else 0.0

    height_to_values: Dict[int, set] = {}
    for val, h in pairs:
        if h not in height_to_values:
            height_to_values[h] = set()
        height_to_values[h].add(val)

    spread_levels: List[Dict[str, Any]] = []
    for h in sorted(height_to_values.keys()):
        spread_levels.append(
            {
                "information_height_level": int(h),
                "distinct_values_visited": len(height_to_values[h]),
                "visit_count": sum(1 for _, hh in pairs if hh == h),
            }
        )

    if len(spread_levels) > 30:
        step = max(1, len(spread_levels) // 30)
        spread_levels = spread_levels[::step]

    sample_head: List[Dict[str, Any]] = []
    for i, (v, h) in enumerate(pairs[:30]):
        if isinstance(v, tuple):
            sample_head.append(
                {
                    "time_step": int(i),
                    "value_lanes": [int(x) for x in v],
                    "information_height": int(h),
                }
            )
        else:
            sample_head.append(
                {
                    "time_step": int(i),
                    "value": int(v),
                    "information_height": int(h),
                }
            )

    return JointValueHeightAnalysis(
        trajectory_length=n,
        distinct_value_height_pairs=distinct,
        trajectory_self_intersection_count=intersection_count,
        trajectory_self_intersection_rate=intersection_rate,
        value_spread_at_height_levels=spread_levels,
        trajectory_sample_head=sample_head,
    )

