from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ...core.atomic_trace import AtomicEvent
from ...core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState
from .snapshots import operation_family, states_events_to_snapshots


@dataclass(frozen=True, slots=True)
class InformationHeightProfile:
    final_height: int
    max_height: int
    height_time_series: List[Tuple[int, int]]
    increment_time_series: List[Tuple[int, int]]
    mean_increment_per_step: float
    burst_step_count: int
    burst_steps: List[Tuple[int, int]]
    height_by_building: Dict[str, int]
    height_by_operation_family: Dict[str, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "final_height": int(self.final_height),
            "max_height": int(self.max_height),
            "height_time_series_length": len(self.height_time_series),
            "height_time_series_head": [
                {"time_step": int(t), "information_height": int(h)}
                for t, h in self.height_time_series[:20]
            ],
            "height_time_series_tail": [
                {"time_step": int(t), "information_height": int(h)}
                for t, h in self.height_time_series[-10:]
            ],
            "mean_increment_per_step": float(self.mean_increment_per_step),
            "burst_step_count": int(self.burst_step_count),
            "burst_steps_head": [
                {"time_step": int(t), "increment": int(d)}
                for t, d in self.burst_steps[:10]
            ],
            "height_by_building": {str(k): int(v) for k, v in self.height_by_building.items()},
            "height_by_operation_family": {str(k): int(v) for k, v in self.height_by_operation_family.items()},
        }


def compute_information_height_profile(
    *,
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
    events: List[AtomicEvent],
    backend_meta: Dict[str, Any] | None = None,
) -> InformationHeightProfile:
    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            state_snapshots, event_snapshots = states_events_to_snapshots(
                states,
                events,
                backend_meta=backend_meta,
            )
            if state_snapshots and event_snapshots:
                r = iwt_core.compute_information_height_profile(state_snapshots, event_snapshots)
                height_time_series = [(int(a), int(b)) for a, b in r.height_time_series]
                increment_time_series = [(int(a), int(b)) for a, b in r.increment_time_series]
                burst_steps = [(int(a), int(b)) for a, b in r.burst_steps]
                height_by_building = dict(r.height_by_building)
                height_by_operation_family = dict(r.height_by_operation_family)
                if backend_meta is not None:
                    backend_meta["information_height_profile"] = {"backend": "native_cpp"}
                return InformationHeightProfile(
                    final_height=int(r.final_height),
                    max_height=int(r.max_height),
                    height_time_series=height_time_series,
                    increment_time_series=increment_time_series,
                    mean_increment_per_step=float(r.mean_increment_per_step),
                    burst_step_count=int(r.burst_step_count),
                    burst_steps=burst_steps,
                    height_by_building=height_by_building,
                    height_by_operation_family=height_by_operation_family,
                )
    except Exception as exc:
        if backend_meta is not None:
            backend_meta["information_height_profile"] = {
                "backend": "python_fallback",
                "reason": f"native_exception:{type(exc).__name__}",
            }
    if backend_meta is not None and "information_height_profile" not in backend_meta:
        backend_meta["information_height_profile"] = {
            "backend": "python_fallback",
            "reason": "native_path_not_used",
        }
    height_series: List[Tuple[int, int]] = []
    for state in states:
        height_series.append((int(state.tc), int(state.information_height.current_building_height)))

    increment_series: List[Tuple[int, int]] = []
    height_by_building: Dict[str, int] = {}
    height_by_family: Dict[str, int] = {}

    for event in events:
        delta = int(event.delta)
        increment_series.append((int(event.tc), delta))

        building = str(event.floor)
        height_by_building[building] = height_by_building.get(building, 0) + delta

        family = operation_family(str(event.op))
        height_by_family[family] = height_by_family.get(family, 0) + delta

    total_steps = len(events)
    total_delta = sum(d for _, d in increment_series)
    mean_inc = float(total_delta) / float(total_steps) if total_steps > 0 else 0.0

    burst_threshold = max(1, int(mean_inc * 2.0)) if mean_inc > 0 else 1
    bursts = [(t, d) for t, d in increment_series if d >= burst_threshold]

    heights = [h for _, h in height_series]
    final_h = heights[-1] if heights else 0
    max_h = max(heights) if heights else 0

    return InformationHeightProfile(
        final_height=final_h,
        max_height=max_h,
        height_time_series=height_series,
        increment_time_series=increment_series,
        mean_increment_per_step=mean_inc,
        burst_step_count=len(bursts),
        burst_steps=bursts,
        height_by_building=height_by_building,
        height_by_operation_family=height_by_family,
    )

