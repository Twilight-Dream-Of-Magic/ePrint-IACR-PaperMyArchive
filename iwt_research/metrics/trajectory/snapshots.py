from __future__ import annotations

from typing import Any, Dict, List

from ...core.atomic_trace import AtomicEvent
from ...core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState

MAX_NATIVE_SIGNED_INT64 = (1 << 63) - 1


def operation_family(op_name: str) -> str:
    op = str(op_name).lower()
    if "s_box" in op or "substitut" in op:
        return "substitution"
    if "p_box" in op or "permute_bits" in op or "perm_step" in op or "permute_values" in op:
        return "permutation"
    if "rotl" in op or "rotr" in op or "rot" in op:
        return "rotation"
    if "cross_domain" in op or "cross_floor" in op:
        return "cross_domain"
    if "xor" in op:
        return "xor"
    if "add" in op:
        return "addition"
    if "sub" in op:
        return "subtraction"
    return "other"


def is_vector_state_value(x: Any) -> bool:
    return isinstance(x, (tuple, list))


def contains_vector_state(states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState]) -> bool:
    for state in states:
        if is_vector_state_value(state.x):
            return True
    return False


def pack_state_value_for_native_snapshot(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
) -> int | None:
    x = state.x
    if not is_vector_state_value(x):
        return int(x)
    modulus_q = int(state.domain.q)
    packed = 0
    factor = 1
    for lane_value in x:
        packed += (int(lane_value) % modulus_q) * factor
        factor *= modulus_q
    if packed > MAX_NATIVE_SIGNED_INT64:
        return None
    return int(packed)


def state_value_for_joint_analysis(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
) -> Any:
    x = state.x
    if is_vector_state_value(x):
        return tuple(int(v) for v in x)
    return int(x)


def trajectory_semantics_metadata(
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
) -> Dict[str, Any]:
    if contains_vector_state(states):
        lane_count = 0
        for state in states:
            x = state.x
            if is_vector_state_value(x):
                lane_count = max(lane_count, len(x))
        return {
            "contains_vector_state": True,
            "state_value_encoding": "vector_tuple_signature",
            "lane_count": int(lane_count),
        }
    return {
        "contains_vector_state": False,
        "state_value_encoding": "scalar",
        "lane_count": 1,
    }


def states_events_to_snapshots(
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
    events: List[AtomicEvent],
    backend_meta: Dict[str, Any] | None = None,
) -> tuple[list, list]:
    """Build C++ StateSnapshot and EventSnapshot lists from Python states/events."""
    try:
        from ...native import available as _native_available, iwt_core

        if not _native_available or iwt_core is None:
            if backend_meta is not None:
                backend_meta["snapshot_builder"] = {
                    "backend": "python_only",
                    "reason": "native_unavailable",
                }
            return [], []
    except Exception as exc:
        if backend_meta is not None:
            backend_meta["snapshot_builder"] = {
                "backend": "python_only",
                "reason": f"native_import_error:{type(exc).__name__}",
            }
        return [], []
    state_snapshots = []
    for s in states:
        value_x = pack_state_value_for_native_snapshot(s)
        if value_x is None:
            if backend_meta is not None:
                backend_meta["snapshot_builder"] = {
                    "backend": "python_only",
                    "reason": "vector_state_packed_value_out_of_int64_range",
                }
            return [], []
        snap = iwt_core.StateSnapshot()
        snap.value_x = value_x
        snap.time_counter = int(s.tc)
        snap.floor = str(s.floor)
        snap.current_building_side_depth = int(s.information_height.current_building_side_depth)
        snap.current_building_height = int(s.information_height.current_building_height)
        snap.cross_building_event_count = int(s.information_height.cross_building_event_count)
        snap.cross_domain_reencoding_quotient = int(s.information_height.cross_domain_reencoding_quotient)
        state_snapshots.append(snap)
    event_snapshots = []
    for e in events:
        ev = iwt_core.EventSnapshot()
        ev.time_counter = int(e.tc)
        ev.operation = str(e.op)
        ev.floor = str(e.floor)
        ev.modulus = int(e.q)
        ev.representative = int(e.w)
        ev.value_before = int(e.x0)
        ev.value_after_reduction = int(e.x1)
        ev.raw_value_before_reduction = int(e.raw)
        ev.boundary_quotient_delta = int(e.delta)
        ev.wrap_occurred = bool(e.wrap)
        ev.carry = e.carry
        ev.borrow = e.borrow
        event_snapshots.append(ev)
    if backend_meta is not None:
        backend_meta["snapshot_builder"] = {
            "backend": "native_cpp",
            "state_value_encoding": (
                "base_q_lanes_packed_int64"
                if contains_vector_state(states)
                else "scalar"
            ),
        }
    return state_snapshots, event_snapshots

