from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ...core.atomic_trace import AtomicEvent
from ...core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState
from .snapshots import operation_family, states_events_to_snapshots


@dataclass(frozen=True, slots=True)
class CrossDomainSwitchingPattern:
    total_cross_domain_events: int
    net_cross_domain_counter: int
    building_visit_sequence: List[Dict[str, Any]]
    building_dwell_times: List[Dict[str, Any]]
    unique_buildings_visited: int
    switching_regularity_stddev: float
    cross_domain_counter_time_series_head: List[Dict[str, Any]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_cross_domain_events": int(self.total_cross_domain_events),
            "net_cross_domain_counter": int(self.net_cross_domain_counter),
            "building_visit_sequence": list(self.building_visit_sequence),
            "building_dwell_times": list(self.building_dwell_times),
            "unique_buildings_visited": int(self.unique_buildings_visited),
            "switching_regularity_stddev": float(self.switching_regularity_stddev),
            "cross_domain_counter_time_series_head": list(self.cross_domain_counter_time_series_head),
        }


def compute_cross_domain_switching_pattern(
    *,
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
    events: List[AtomicEvent],
    backend_meta: Dict[str, Any] | None = None,
) -> CrossDomainSwitchingPattern:
    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            state_snapshots, event_snapshots = states_events_to_snapshots(
                states,
                events,
                backend_meta=backend_meta,
            )
            if state_snapshots and event_snapshots:
                r = iwt_core.compute_cross_domain_switching_pattern(state_snapshots, event_snapshots)
                building_visit_sequence = [
                    {"time_step": int(e.time_step), "building_label": str(e.building_label)}
                    for e in r.building_visit_sequence
                ]
                building_dwell_times = [
                    {
                        "building_label": str(d.building_label),
                        "enter_time_step": int(d.enter_time_step),
                        "leave_time_step": int(d.leave_time_step),
                        "dwell_steps": int(d.dwell_steps),
                    }
                    for d in r.building_dwell_times
                ]
                counter_head = [
                    {"time_step": int(t), "cross_domain_counter": int(c)}
                    for t, c in r.cross_domain_counter_time_series_head
                ]
                if backend_meta is not None:
                    backend_meta["cross_domain_switching_pattern"] = {"backend": "native_cpp"}
                return CrossDomainSwitchingPattern(
                    total_cross_domain_events=int(r.total_cross_domain_events),
                    net_cross_domain_counter=int(r.net_cross_domain_counter),
                    building_visit_sequence=building_visit_sequence,
                    building_dwell_times=building_dwell_times,
                    unique_buildings_visited=int(r.unique_buildings_visited),
                    switching_regularity_stddev=float(r.switching_regularity_stddev),
                    cross_domain_counter_time_series_head=counter_head,
                )
    except Exception as exc:
        if backend_meta is not None:
            backend_meta["cross_domain_switching_pattern"] = {
                "backend": "python_fallback",
                "reason": f"native_exception:{type(exc).__name__}",
            }
    if backend_meta is not None and "cross_domain_switching_pattern" not in backend_meta:
        backend_meta["cross_domain_switching_pattern"] = {
            "backend": "python_fallback",
            "reason": "native_path_not_used",
        }
    cross_counter_series: List[Tuple[int, int]] = [
        (int(s.tc), int(s.information_height.cross_building_event_count)) for s in states
    ]

    cross_events = 0
    for ev in events:
        family = operation_family(str(ev.op))
        if family == "cross_domain":
            cross_events += 1

    net_counter = int(states[-1].information_height.cross_building_event_count) if states else 0

    building_visits: List[Dict[str, Any]] = []
    dwell_times: List[Dict[str, Any]] = []
    buildings_seen: set = set()

    if states:
        current_building = str(states[0].floor)
        buildings_seen.add(current_building)
        segment_start = 0
        building_visits.append(
            {
                "time_step": 0,
                "building_label": current_building,
            }
        )

        for i in range(1, len(states)):
            b = str(states[i].floor)
            if b != current_building:
                dwell_times.append(
                    {
                        "building_label": current_building,
                        "enter_time_step": int(segment_start),
                        "leave_time_step": int(i),
                        "dwell_steps": int(i - segment_start),
                    }
                )
                building_visits.append(
                    {
                        "time_step": int(states[i].tc),
                        "building_label": b,
                    }
                )
                current_building = b
                buildings_seen.add(b)
                segment_start = i

        dwell_times.append(
            {
                "building_label": current_building,
                "enter_time_step": int(segment_start),
                "leave_time_step": int(len(states) - 1),
                "dwell_steps": int(len(states) - 1 - segment_start),
            }
        )

    dwell_step_values = [int(d["dwell_steps"]) for d in dwell_times]
    if len(dwell_step_values) >= 2:
        mean_dwell = sum(dwell_step_values) / float(len(dwell_step_values))
        variance = sum((v - mean_dwell) ** 2 for v in dwell_step_values) / float(len(dwell_step_values))
        stddev = variance ** 0.5
    else:
        stddev = 0.0

    head_limit = 30
    counter_head = [
        {"time_step": int(t), "cross_domain_counter": int(c)}
        for t, c in cross_counter_series[:head_limit]
    ]

    return CrossDomainSwitchingPattern(
        total_cross_domain_events=cross_events,
        net_cross_domain_counter=net_counter,
        building_visit_sequence=building_visits,
        building_dwell_times=dwell_times,
        unique_buildings_visited=len(buildings_seen),
        switching_regularity_stddev=stddev,
        cross_domain_counter_time_series_head=counter_head,
    )

