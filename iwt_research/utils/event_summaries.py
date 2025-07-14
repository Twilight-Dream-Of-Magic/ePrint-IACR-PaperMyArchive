from __future__ import annotations

from typing import Any, Dict, Iterable, List, Callable


def op_family(op: str) -> str:
    """
    Normalize an AtomicEvent op string to an operation family label.
    """
    return str(op).split("[", 1)[0]


def count_op_families(events: Iterable[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for ev in events:
        fam = op_family(str(ev.op))
        counts[fam] = int(counts.get(fam, 0)) + 1
    return counts


def op_family_frequencies(counts: Dict[str, int]) -> Dict[str, float]:
    total = sum(int(v) for v in counts.values())
    if total <= 0:
        return {}
    return {str(k): float(int(v)) / float(total) for k, v in counts.items()}


def region_id(ev: Any) -> str:
    """
    Region family id U := (floor_label, op_family).
    """
    return f"{str(ev.floor)}:{op_family(str(ev.op))}"


def aggregate_region_counts(*, states: List[Any], events: List[Any], project: Callable[[Any], Any]) -> Dict[str, Dict[str, float]]:
    """
    Aggregate counts by region:
    - steps(U)
    - wraps(U)
    - nsls(U) where NSL = 非平凡自我回环 (nontrivial self-loop): (y1==y0) and (x1!=x0)
    """
    out: Dict[str, Dict[str, float]] = {}
    for i, ev in enumerate(events):
        rid = region_id(ev)
        if rid not in out:
            out[rid] = {"step_count": 0.0, "wrap_count": 0.0, "nontrivial_self_loop_count": 0.0}
        out[rid]["step_count"] += 1.0
        if bool(getattr(ev, "wrap", False)):
            out[rid]["wrap_count"] += 1.0
        s0 = states[i]
        s1 = states[i + 1]
        y0 = project(s0)
        y1 = project(s1)
        if (y1 == y0) and (getattr(s1, "x", None) != getattr(s0, "x", None)):
            out[rid]["nontrivial_self_loop_count"] += 1.0
    return out

