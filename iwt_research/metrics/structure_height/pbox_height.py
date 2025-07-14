"""
P-box 縱向高度：有界符號越界 δ^struct_t ∈ {-1,0,+1}，僅邊界穿越時記帳。
"""
from __future__ import annotations

from typing import List


def _pbox_local_lift_coefficient(
    input_index: int, output_value: int, modulus_q: int
) -> int:
    """k ∈ {-1,0,+1} 使 |(output_value + k*modulus_q) - input_index| 最小。tie-break: 距離 → |k| → k。"""
    modulus_q = int(modulus_q)
    if modulus_q <= 0:
        return 0
    input_index = int(input_index)
    output_value = int(output_value)
    candidates = [
        (abs(output_value - input_index), 0),
        (abs((output_value + modulus_q) - input_index), 1),
        (abs((output_value - modulus_q) - input_index), -1),
    ]
    candidates.sort(key=lambda item: (item[0], abs(item[1]), item[1]))
    return candidates[0][1]


def pbox_structure_increment_at(
    input_index: int, output_value: int, modulus_q: int, window_start: int = 0
) -> int:
    """單步 P-box 結構增量（paper §5.3），返回 ∈ {-1,0,+1}。"""
    try:
        from ...native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            return int(iwt_core.pbox_structure_increment_at(
                int(input_index), int(output_value), int(modulus_q), int(window_start)
            ))
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for pbox_structure_increment_at(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


def per_step_structure_increments_pbox(
    output_sequence: List[int],
    modulus_q: int,
    window_start: int = 0,
) -> List[int]:
    """P-box：有界符號越界（paper §5.3），每項 ∈ {-1,0,+1}。"""
    modulus_q = int(modulus_q)
    window_start = int(window_start)
    if len(output_sequence) != modulus_q:
        return [0] * max(modulus_q, 1)
    try:
        from ...native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            out = iwt_core.per_step_structure_increments_pbox(
                [int(x) for x in output_sequence], modulus_q, window_start
            )
            return [int(x) for x in out]
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for per_step_structure_increments_pbox(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )
