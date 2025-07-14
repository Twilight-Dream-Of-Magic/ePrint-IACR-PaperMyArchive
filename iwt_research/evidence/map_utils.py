"""
TM-1 safe evidence-map helpers: slice multiplicity and revisit-time statistics.
Output shapes match report keys max_shadow_point, top_shadow_points, top_revisit_times.
"""
from __future__ import annotations

from typing import Any, Dict, List


def peak_slice_multiplicity_point(observations_by_trace: List[List[int]]) -> Dict[str, Any]:
    """
    max_{t,y} m_t(y) with argmax (t,y). Report key: max_shadow_point.
    """
    if not observations_by_trace:
        return {"max_multiplicity": 0, "time_index": None, "observation_value": None}
    n = len(observations_by_trace)
    T = len(observations_by_trace[0]) if n else 0
    best_m = 0
    best_t = None
    best_y = None
    for t in range(T):
        counts: Dict[int, int] = {}
        for i in range(n):
            y = int(observations_by_trace[i][t])
            counts[y] = counts.get(y, 0) + 1
        if not counts:
            continue
        y_star, m_star = max(counts.items(), key=lambda kv: kv[1])
        if int(m_star) > best_m:
            best_m = int(m_star)
            best_t = int(t)
            best_y = int(y_star)
    return {"max_multiplicity": best_m, "time_index": best_t, "observation_value": best_y}


def top_slice_multiplicity_points(
    *,
    observations_by_trace: List[List[int]],
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """
    Top-k (t,y) by slice multiplicity m_t(y). Report key: top_shadow_points.
    """
    if not observations_by_trace:
        return []
    n = len(observations_by_trace)
    T = len(observations_by_trace[0]) if n else 0
    points: List[Dict[str, Any]] = []
    for t in range(T):
        counts: Dict[int, int] = {}
        for i in range(n):
            y = int(observations_by_trace[i][t])
            counts[y] = counts.get(y, 0) + 1
        if not counts:
            continue
        y_star, m_star = max(counts.items(), key=lambda kv: kv[1])
        points.append({
            "time_index": int(t),
            "observation_value": int(y_star),
            "multiplicity": int(m_star),
            "fraction": float(m_star) / float(n) if n else None,
        })
    points.sort(key=lambda d: (int(d.get("multiplicity", 0)), -int(d.get("time_index", 0))), reverse=True)
    return points[: max(0, int(top_k))]


def top_revisit_times(
    *,
    observations_by_trace: List[List[int]],
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """
    Per step t>0: count of traces with y[t] seen earlier in that trace. Report key: top_revisit_times.
    """
    if not observations_by_trace:
        return []
    n = len(observations_by_trace)
    T = len(observations_by_trace[0]) if n else 0
    freq = [0 for _ in range(T)]
    for obs in observations_by_trace:
        seen: set[int] = set()
        for t, y in enumerate(obs):
            yy = int(y)
            if t == 0:
                seen.add(yy)
                continue
            if yy in seen:
                freq[t] += 1
            seen.add(yy)
    out: List[Dict[str, Any]] = []
    for t in range(1, T):
        out.append({
            "time_index": int(t),
            "revisit_trace_count": int(freq[t]),
            "fraction": float(freq[t]) / float(n) if n else None,
        })
    out.sort(key=lambda d: int(d.get("revisit_trace_count", 0)), reverse=True)
    return out[: max(0, int(top_k))]
