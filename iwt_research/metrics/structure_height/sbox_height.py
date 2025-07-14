"""
S-box 縱向高度：值域解纏繞 → 每步 δ^struct_t（不固定）。
"""
from __future__ import annotations

from typing import List, Tuple


def _sbox_lifted_sequence(
    output_sequence: List[int],
    modulus_q: int,
    window_start: int = 0,
) -> List[int]:
    """S-box 解纏繞後的 lifted 序列 (ỹ_0, ỹ_1, ...)。僅由 C++ iwt_core.sbox_lifted_sequence 實作，無 Python 重複邏輯。"""
    modulus_q = int(modulus_q)
    window_start = int(window_start)
    if len(output_sequence) != modulus_q:
        return []
    try:
        from ...native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            out = iwt_core.sbox_lifted_sequence(
                [int(x) for x in output_sequence], modulus_q, window_start
            )
            return [int(x) for x in out]
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for _sbox_lifted_sequence(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


def per_step_structure_increments_sbox(
    output_sequence: List[int],
    modulus_q: int,
    window_start: int = 0,
) -> List[int]:
    """S-box：值域解纏繞 → 每步 δ^struct_t（paper §5.2）。"""
    modulus_q = int(modulus_q)
    window_start = int(window_start)
    if len(output_sequence) != modulus_q:
        return [0] * max(modulus_q, 1)
    try:
        from ...native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            out = iwt_core.per_step_structure_increments_sbox(
                [int(x) for x in output_sequence], modulus_q, window_start
            )
            return [int(x) for x in out]
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for per_step_structure_increments_sbox(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


def _turn_count(lifted_sequence: List[int]) -> int:
    if len(lifted_sequence) < 3:
        return 0
    count = 0
    slope_prev = lifted_sequence[1] - lifted_sequence[0]
    for t in range(2, len(lifted_sequence)):
        slope_cur = lifted_sequence[t] - lifted_sequence[t - 1]
        if slope_cur * slope_prev < 0:
            count += 1
        slope_prev = slope_cur
    return count


def _segment_intersect(
    x0_s1: float, y0_s1: float, x1_s1: float, y1_s1: float,
    x0_s2: float, y0_s2: float, x1_s2: float, y1_s2: float,
) -> bool:
    """Segment 1: (x0_s1,y0_s1)->(x1_s1,y1_s1); segment 2: (x0_s2,y0_s2)->(x1_s2,y1_s2)."""
    def cross_product_orientation(
        origin: Tuple[float, float],
        segment_end: Tuple[float, float],
        query_point: Tuple[float, float],
    ) -> float:
        return (
            (segment_end[0] - origin[0]) * (query_point[1] - origin[1])
            - (segment_end[1] - origin[1]) * (query_point[0] - origin[0])
        )

    orient_1 = cross_product_orientation(
        (x0_s1, y0_s1), (x1_s1, y1_s1), (x0_s2, y0_s2)
    )
    orient_2 = cross_product_orientation(
        (x0_s1, y0_s1), (x1_s1, y1_s1), (x1_s2, y1_s2)
    )
    orient_3 = cross_product_orientation(
        (x0_s2, y0_s2), (x1_s2, y1_s2), (x0_s1, y0_s1)
    )
    orient_4 = cross_product_orientation(
        (x0_s2, y0_s2), (x1_s2, y1_s2), (x1_s1, y1_s1)
    )
    return orient_1 * orient_2 < 0 and orient_3 * orient_4 < 0


def _crossing_count(
    input_indices: List[int], lifted_sequence: List[int]
) -> int:
    length = len(input_indices)
    if length != len(lifted_sequence) or length < 2:
        return 0
    segments = [
        (
            float(input_indices[i - 1]),
            float(lifted_sequence[i - 1]),
            float(input_indices[i]),
            float(lifted_sequence[i]),
        )
        for i in range(1, length)
    ]
    count = 0
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            if j == i + 1:
                continue
            x0_s1, y0_s1, x1_s1, y1_s1 = segments[i]
            x0_s2, y0_s2, x1_s2, y1_s2 = segments[j]
            if _segment_intersect(
                x0_s1, y0_s1, x1_s1, y1_s1,
                x0_s2, y0_s2, x1_s2, y1_s2,
            ):
                count += 1
    return count


