"""
逆序對 inv(π)：同層纏繞（橫向軸）。
inv(π) = #{(i,j): i < j ∧ π(i) > π(j)}，等價於置換箭頭圖交叉數、Kendall tau 到恒等置換的距離。
O(q log q) 用 Fenwick tree 實現。
"""
from __future__ import annotations


def inversion_count_permutation(permutation: list[int]) -> int:
    """
    permutation 為 0..q-1 的置換；返回 inv(π)。
    若值域為 [w, w+q-1]，呼叫前請先做座標壓縮 permutation[i]-w。
    複雜度 O(q log q)。若已構建 C++ 擴展則使用 C++ 實現。
    """
    try:
        from ...native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None:
            return int(iwt_core.inversion_count_permutation([int(x) for x in permutation]))
    except Exception:
        pass
    raise RuntimeError(
        "iwt_core (C++ extension) is required for inversion_count_permutation(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


def inversion_norm(inv_count: int, q: int) -> float:
    """歸一化逆序數 inversion pair number ∈ [0,1]：2*inv / (q*(q-1))。q<=1 時回傳 0.0。"""
    if q <= 1:
        return 0.0
    return 2.0 * inv_count / (q * (q - 1))


def inv_parity(inv_count: int) -> int:
    """逆序數奇偶性：0 偶、1 奇，可作結構指紋。"""
    return inv_count % 2
