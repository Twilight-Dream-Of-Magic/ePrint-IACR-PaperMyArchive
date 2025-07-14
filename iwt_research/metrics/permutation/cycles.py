"""
置換的輪換分解：cycle_count, cycle_lengths, max_cycle_length, fixed_point_count。
與纏繞度正交，用於 P-box 結構報告（summary）。
"""
from __future__ import annotations

from typing import List


def permutation_cycles(permutation: List[int]) -> List[List[int]]:
    """permutation[i] = image of i；分解為不相交輪換。"""
    size = len(permutation)
    seen = [False] * size
    cycles: List[List[int]] = []
    for start in range(size):
        if seen[start]:
            continue
        cycle: List[int] = []
        pos = start
        while not seen[pos]:
            seen[pos] = True
            cycle.append(pos)
            pos = permutation[pos]
        if cycle:
            cycles.append(cycle)
    return cycles


def cycle_stats(permutation: List[int]) -> dict:
    """
    回傳 cycle_count, cycle_lengths（降序）, max_cycle_length, fixed_point_count。
    若 permutation 非合法置換（有越界），回傳空結構。有 C++ 時優先用 C++。
    """
    size = len(permutation)
    if size == 0:
        return {
            "cycle_count": 0,
            "cycle_lengths": [],
            "max_cycle_length": 0,
            "fixed_point_count": 0,
        }
    try:
        from ...native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            r = iwt_core.cycle_stats([int(x) for x in permutation])
            return {
                "cycle_count": int(r.cycle_count),
                "cycle_lengths": [int(x) for x in r.cycle_lengths],
                "max_cycle_length": int(r.max_cycle_length),
                "fixed_point_count": int(r.fixed_point_count),
            }
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for cycle_stats(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )
