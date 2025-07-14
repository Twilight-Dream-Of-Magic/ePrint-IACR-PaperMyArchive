from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..core.atomic_trace import AtomicEvent
from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if den != 0 else 0.0


def _default_bootstrap_stat(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _op_family(op: str) -> str:
    return op.split("[", 1)[0]


@dataclass(frozen=True, slots=True)
class AtomicMetrics:
    total_steps: int
    per_op_counts: Dict[str, int]
    wrap_total: int
    wrap_by_op: Dict[str, int]
    sl_total: int
    sl_by_op: Dict[str, int]
    nsl_total: int
    nsl_by_op: Dict[str, int]

    def as_dict(self) -> Dict[str, Any]:
        def rates(counts: Dict[str, int], denom: Dict[str, int]) -> Dict[str, float]:
            return {k: _safe_div(counts.get(k, 0), denom.get(k, 0)) for k in denom.keys()}

        global_den = float(self.total_steps)
        return {
            "total_steps": self.total_steps,
            "per_op_counts": dict(self.per_op_counts),
            "wrap_total": self.wrap_total,
            "wrap_event_rate": _safe_div(self.wrap_total, global_den),
            "wrap_by_op_count": dict(self.wrap_by_op),
            "wrap_by_op_rate": rates(self.wrap_by_op, self.per_op_counts),
            "trivial_self_loop_total": self.sl_total,
            "trivial_self_loop_rate": _safe_div(self.sl_total, global_den),
            "trivial_self_loop_by_op_count": dict(self.sl_by_op),
            "trivial_self_loop_by_op_rate": rates(self.sl_by_op, self.per_op_counts),
            "nontrivial_self_loop_total": self.nsl_total,
            "nontrivial_self_loop_rate": _safe_div(self.nsl_total, global_den),
            "nontrivial_self_loop_by_op_count": dict(self.nsl_by_op),
            "nontrivial_self_loop_by_op_rate": rates(self.nsl_by_op, self.per_op_counts),
        }


def compute_atomic_metrics(
    *,
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
    events: List[AtomicEvent],
    project: Callable[[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], int],
) -> AtomicMetrics:
    """
    Compute trivial self-loop (SL) / non-trivial self-loop (NSL) using projection Pi:
    - SL 平凡自我回环: y_{t+1} == y_t AND x_{t+1} == x_t
    - NSL 非平凡自我回环: y_{t+1} == y_t AND x_{t+1} != x_t
    Uses iwt_core (C++23) when available.
    """
    if len(states) != len(events) + 1:
        raise ValueError("states must be length len(events)+1")
    try:
        from ..native import iwt_core, available as _native_available
        from .trajectory.snapshots import states_events_to_snapshots
        if _native_available and iwt_core is not None:
            state_snapshots, event_snapshots = states_events_to_snapshots(states, events)
            if state_snapshots and event_snapshots:
                projection_values = [int(project(s)) for s in states]
                result = iwt_core.compute_atomic_metrics(state_snapshots, event_snapshots, projection_values)
                return AtomicMetrics(
                    total_steps=int(result.total_steps),
                    per_op_counts=dict(result.per_operation_counts),
                    wrap_total=int(result.wrap_total),
                    wrap_by_op=dict(result.wrap_by_operation),
                    sl_total=int(result.trivial_self_loop_total),
                    sl_by_op=dict(result.trivial_self_loop_by_operation),
                    nsl_total=int(result.nontrivial_self_loop_total),
                    nsl_by_op=dict(result.nontrivial_self_loop_by_operation),
                )
    except Exception:
        pass

    per_op_counts: Dict[str, int] = {}
    wrap_by_op: Dict[str, int] = {}
    sl_by_op: Dict[str, int] = {}
    nsl_by_op: Dict[str, int] = {}

    wrap_total = 0
    sl_total = 0
    nsl_total = 0

    for i, ev in enumerate(events):
        per_op_counts[ev.op] = per_op_counts.get(ev.op, 0) + 1

        if ev.wrap:
            wrap_total += 1
            wrap_by_op[ev.op] = wrap_by_op.get(ev.op, 0) + 1

        s0 = states[i]
        s1 = states[i + 1]
        y0 = project(s0)
        y1 = project(s1)
        if y1 == y0:
            if s1.x == s0.x:
                sl_total += 1
                sl_by_op[ev.op] = sl_by_op.get(ev.op, 0) + 1
            else:
                nsl_total += 1
                nsl_by_op[ev.op] = nsl_by_op.get(ev.op, 0) + 1

    return AtomicMetrics(
        total_steps=len(events),
        per_op_counts=per_op_counts,
        wrap_total=wrap_total,
        wrap_by_op=wrap_by_op,
        sl_total=sl_total,
        sl_by_op=sl_by_op,
        nsl_total=nsl_total,
        nsl_by_op=nsl_by_op,
    )


def compute_mechanism_side_metrics(*, states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], events: List[AtomicEvent]) -> Dict[str, Any]:
    """
    Mechanism-side metrics (機制側): depend only on enhanced state + atomic events,
    not on any projection Pi(y). Uses iwt_core (C++23) when available.
    """
    if len(states) != len(events) + 1:
        raise ValueError("states must be length len(events)+1")
    try:
        from ..native import iwt_core, available as _native_available
        from .trajectory.snapshots import states_events_to_snapshots
        if _native_available and iwt_core is not None:
            state_snapshots, event_snapshots = states_events_to_snapshots(states, events)
            if state_snapshots and event_snapshots:
                wrap_directions = [dict(e.meta).get("wrap_dir", "none") for e in events]
                result = iwt_core.compute_mechanism_side_metrics(state_snapshots, event_snapshots, wrap_directions)
                return {
                    "total_atomic_steps": int(result.total_atomic_steps),
                    "operation_counts": dict(result.operation_counts),
                    "operation_family_counts": dict(result.operation_family_counts),
                    "wrap_event_count": int(result.wrap_event_count),
                    "wrap_event_rate": float(result.wrap_event_rate),
                    "wrap_event_count_by_op_family": dict(result.wrap_event_count_by_operation_family),
                    "wrap_direction_counts": dict(result.wrap_direction_counts),
                    "delta_sum": int(result.delta_sum),
                    "carry_event_count": int(result.carry_event_count),
                    "borrow_event_count": int(result.borrow_event_count),
                    "cross_domain_event_count": int(result.cross_domain_event_count),
                    "information_height_in_building_final": int(result.information_height_in_building_final),
                    "information_height_in_building_max": int(result.information_height_in_building_max),
                    "ih_cross_final": int(result.information_height_cross_final),
                }
    except Exception:
        pass

    total_steps = len(events)
    op_counts: Dict[str, int] = {}
    op_family_counts: Dict[str, int] = {}
    wrap_total = 0
    wrap_by_family: Dict[str, int] = {}
    wrap_dir_counts: Dict[str, int] = {"up": 0, "down": 0, "none": 0}
    delta_sum = 0
    carry_total = 0
    borrow_total = 0
    cross_domain_events = 0

    for ev in events:
        op_counts[ev.op] = op_counts.get(ev.op, 0) + 1
        fam = _op_family(str(ev.op))
        op_family_counts[fam] = op_family_counts.get(fam, 0) + 1
        if bool(ev.wrap):
            wrap_total += 1
            wrap_by_family[fam] = wrap_by_family.get(fam, 0) + 1
        delta_sum += int(ev.delta)
        if ev.carry:
            carry_total += int(ev.carry)
        if ev.borrow:
            borrow_total += int(ev.borrow)
        if fam == "cross_domain":
            cross_domain_events += 1
        try:
            wrap_dir = dict(ev.meta).get("wrap_dir", "none")
            if wrap_dir in wrap_dir_counts:
                wrap_dir_counts[wrap_dir] += 1
        except Exception:
            pass

    ih_in_values = [int(st.information_height.current_building_height) for st in states]
    ih_cross_values = [int(st.information_height.cross_building_event_count) for st in states]

    return {
        "total_atomic_steps": total_steps,
        "operation_counts": dict(op_counts),
        "operation_family_counts": dict(op_family_counts),
        "wrap_event_count": int(wrap_total),
        "wrap_event_rate": _safe_div(wrap_total, float(total_steps)),
        "wrap_event_count_by_op_family": dict(wrap_by_family),
        "wrap_direction_counts": dict(wrap_dir_counts),
        "delta_sum": int(delta_sum),
        "carry_event_count": int(carry_total),
        "borrow_event_count": int(borrow_total),
        "cross_domain_event_count": int(cross_domain_events),
        "information_height_in_building_final": int(ih_in_values[-1]) if ih_in_values else 0,
        "information_height_in_building_max": int(max(ih_in_values)) if ih_in_values else 0,
        "ih_cross_final": int(ih_cross_values[-1]) if ih_cross_values else 0,
    }


def compute_pattern_side_metrics(
    *,
    states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState],
    events: List[AtomicEvent],
    project: Callable[[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], int],
    observed_space_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Pattern-side metrics (图案側): depend on the projection Pi and observed trace y_t.
    Includes trivial self-loop (SL 平凡自我回环) / non-trivial self-loop (NSL 非平凡自我回环),
    self-intersection / revisit, and projection-level collision stats. Uses iwt_core (C++23) when available.
    """
    if len(states) != len(events) + 1:
        raise ValueError("states must be length len(events)+1")
    try:
        from ..native import iwt_core, available as _native_available
        from .trajectory.snapshots import states_events_to_snapshots
        if _native_available and iwt_core is not None:
            state_snapshots, event_snapshots = states_events_to_snapshots(states, events)
            if state_snapshots and event_snapshots:
                projection_values = [int(project(s)) for s in states]
                obs = int(observed_space_size) if observed_space_size is not None else None
                result = iwt_core.compute_pattern_side_metrics(
                    state_snapshots, event_snapshots, projection_values, obs,
                )
                proj = result.projection
                proj_occ = float(proj.node_occupancy_ratio) if proj.node_occupancy_ratio is not None else None
                projection_dict = {
                    "steps": int(proj.steps),
                    "unique_nodes": int(proj.unique_nodes),
                    "node_occupancy_ratio": proj_occ,
                    "collision_rate": float(proj.collision_rate),
                    "first_return_times": [int(x) for x in proj.first_return_times],
                    "observed_space_size": int(result.observed_space_size) if result.observed_space_size is not None else None,
                }
                sl = result.self_loop
                return {
                    "projection": projection_dict,
                    "self_loop": {
                        "trivial_self_loop_event_count": int(sl.trivial_self_loop_event_count),
                        "trivial_self_loop_event_rate": float(sl.trivial_self_loop_event_rate),
                        "trivial_self_loop_event_count_by_op_family": dict(sl.trivial_self_loop_event_count_by_operation_family),
                        "nontrivial_self_loop_event_count": int(sl.nontrivial_self_loop_event_count),
                        "nontrivial_self_loop_event_rate": float(sl.nontrivial_self_loop_event_rate),
                        "nontrivial_self_loop_event_count_by_op_family": dict(sl.nontrivial_self_loop_event_count_by_operation_family),
                    },
                    "self_intersection_rate": float(sl.self_intersection_rate),
                }
    except Exception:
        pass

    ys = [int(project(st)) for st in states]
    projection_metrics = compute_projection_metrics(ys=ys, observed_space_size=observed_space_size)

    sl_total = 0
    nsl_total = 0
    sl_by_family: Dict[str, int] = {}
    nsl_by_family: Dict[str, int] = {}
    for i, ev in enumerate(events):
        y0 = ys[i]
        y1 = ys[i + 1]
        fam = _op_family(str(ev.op))
        if y1 == y0:
            if states[i + 1].x == states[i].x:
                sl_total += 1
                sl_by_family[fam] = sl_by_family.get(fam, 0) + 1
            else:
                nsl_total += 1
                nsl_by_family[fam] = nsl_by_family.get(fam, 0) + 1

    # self-intersection / revisit rate on a single trace: fraction of t>0 with y_t seen before
    seen = set()
    hits = 0
    for t, y in enumerate(ys):
        if t == 0:
            seen.add(y)
            continue
        if y in seen:
            hits += 1
        seen.add(y)
    self_intersection_rate = hits / max(1, (len(ys) - 1))

    total_steps = len(events)
    return {
        "projection": {
            **projection_metrics.as_dict(),
            "observed_space_size": observed_space_size,
        },
        "self_loop": {
            "trivial_self_loop_event_count": int(sl_total),
            "trivial_self_loop_event_rate": _safe_div(sl_total, float(total_steps)),
            "trivial_self_loop_event_count_by_op_family": dict(sl_by_family),
            "nontrivial_self_loop_event_count": int(nsl_total),
            "nontrivial_self_loop_event_rate": _safe_div(nsl_total, float(total_steps)),
            "nontrivial_self_loop_event_count_by_op_family": dict(nsl_by_family),
        },
        "self_intersection_rate": float(self_intersection_rate),
    }


@dataclass(frozen=True, slots=True)
class ProjectionMetrics:
    steps: int
    unique_nodes: int
    node_occupancy_ratio: Optional[float]
    collision_rate: float
    first_return_times: List[int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "steps": self.steps,
            "unique_nodes": self.unique_nodes,
            "node_occupancy_ratio": self.node_occupancy_ratio,
            "collision_rate": self.collision_rate,
            "first_return_times": list(self.first_return_times),
        }


def compute_projection_metrics(*, ys: List[int], observed_space_size: Optional[int] = None) -> ProjectionMetrics:
    if not ys:
        return ProjectionMetrics(steps=0, unique_nodes=0, node_occupancy_ratio=None, collision_rate=0.0, first_return_times=[])
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            obs = int(observed_space_size) if observed_space_size is not None else None
            result = iwt_core.compute_projection_metrics([int(y) for y in ys], obs)
            occ = float(result.node_occupancy_ratio) if result.node_occupancy_ratio is not None else None
            return ProjectionMetrics(
                steps=int(result.steps),
                unique_nodes=int(result.unique_nodes),
                node_occupancy_ratio=occ,
                collision_rate=float(result.collision_rate),
                first_return_times=[int(x) for x in result.first_return_times],
            )
    except Exception:
        pass

    seen: Dict[int, int] = {}
    unique = 0
    revisits = 0
    frt: List[int] = []
    for t, y in enumerate(ys):
        if y in seen:
            revisits += 1
            frt.append(t - seen[y])
        else:
            unique += 1
        seen[y] = t

    occ = _safe_div(unique, float(observed_space_size)) if observed_space_size else None
    return ProjectionMetrics(
        steps=len(ys) - 1,
        unique_nodes=unique,
        node_occupancy_ratio=occ,
        collision_rate=_safe_div(revisits, float(len(ys))),
        first_return_times=frt,
    )


@dataclass(frozen=True, slots=True)
class SliceShadowMetrics:
    T: int
    ntraces: int
    avg_max_multiplicity: float
    p99_max_multiplicity: float
    avg_pair_collision_prob: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "T": self.T,
            "ntraces": self.ntraces,
            "avg_max_multiplicity": self.avg_max_multiplicity,
            "p99_max_multiplicity": self.p99_max_multiplicity,
            "avg_pair_collision_prob": self.avg_pair_collision_prob,
        }


def compute_slice_shadow_metrics(Ys: List[List[int]]) -> SliceShadowMetrics:
    if not Ys:
        return SliceShadowMetrics(T=0, ntraces=0, avg_max_multiplicity=0.0, p99_max_multiplicity=0.0, avg_pair_collision_prob=0.0)
    n = len(Ys)
    L = len(Ys[0])
    if any(len(y) != L for y in Ys):
        raise ValueError("all traces must have the same length for slice-shadow metrics")
    if L == 0:
        return SliceShadowMetrics(T=0, ntraces=n, avg_max_multiplicity=0.0, p99_max_multiplicity=0.0, avg_pair_collision_prob=0.0)
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            traces_cpp = [[int(v) for v in row] for row in Ys]
            result = iwt_core.compute_slice_shadow_metrics(traces_cpp)
            return SliceShadowMetrics(
                T=int(result.trajectory_length_T),
                ntraces=int(result.number_of_traces),
                avg_max_multiplicity=float(result.average_max_multiplicity),
                p99_max_multiplicity=float(result.p99_max_multiplicity),
                avg_pair_collision_prob=float(result.average_pair_collision_probability),
            )
    except Exception:
        pass

    max_ms: List[int] = []
    pair_cols: List[float] = []
    denom_pairs = n * (n - 1) / 2
    for t in range(L):
        counts: Dict[int, int] = {}
        for i in range(n):
            y = Ys[i][t]
            counts[y] = counts.get(y, 0) + 1
        max_ms.append(max(counts.values()) if counts else 0)
        if denom_pairs > 0:
            coll_pairs = sum(c * (c - 1) / 2 for c in counts.values())
            pair_cols.append(float(coll_pairs) / float(denom_pairs))
        else:
            pair_cols.append(0.0)

    max_ms_sorted = sorted(max_ms)
    p99_idx = int(math.floor(0.99 * (len(max_ms_sorted) - 1))) if len(max_ms_sorted) >= 2 else 0
    return SliceShadowMetrics(
        T=L - 1,
        ntraces=n,
        avg_max_multiplicity=sum(max_ms) / len(max_ms),
        p99_max_multiplicity=float(max_ms_sorted[p99_idx]),
        avg_pair_collision_prob=sum(pair_cols) / len(pair_cols),
    )


def bootstrap_ci(
    values: List[float],
    *,
    seed: int,
    iters: int = 2000,
    alpha: float = 0.05,
    stat: Callable[[List[float]], float] = _default_bootstrap_stat,
) -> Dict[str, float]:
    if not values:
        return {"mean": float("nan"), "lower_bound": float("nan"), "upper_bound": float("nan")}
    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None and stat is _default_bootstrap_stat:
            r = iwt_core.bootstrap_ci([float(x) for x in values], int(seed), int(iters), float(alpha))
            return {"mean": float(r.mean), "lower_bound": float(r.lower_bound), "upper_bound": float(r.upper_bound)}
    except Exception:
        pass
    rng = random.Random(seed)
    n = len(values)
    boots: List[float] = []
    for _ in range(iters):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        boots.append(float(stat(sample)))
    boots.sort()
    lower_bound = boots[int((alpha / 2) * iters)]
    upper_bound = boots[int((1 - alpha / 2) * iters) - 1]
    return {"mean": float(stat(values)), "lower_bound": float(lower_bound), "upper_bound": float(upper_bound)}
