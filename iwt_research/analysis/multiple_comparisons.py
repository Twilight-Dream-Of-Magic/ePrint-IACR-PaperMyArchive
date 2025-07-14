from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True, slots=True)
class BenjaminiHochbergFalseDiscoveryRateResult:
    false_discovery_rate: float
    hypothesis_count: int
    discoveries_count: int
    rejected_indices: List[int]
    adjusted_p_values: List[Optional[float]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "false_discovery_rate": float(self.false_discovery_rate),
            "hypothesis_count": int(self.hypothesis_count),
            "discoveries_count": int(self.discoveries_count),
            "rejected_indices": list(int(i) for i in self.rejected_indices),
            "adjusted_p_values": list(self.adjusted_p_values),
        }


def benjamini_hochberg_false_discovery_rate_control(
    *,
    p_values: List[Optional[float]],
    false_discovery_rate: float,
) -> BenjaminiHochbergFalseDiscoveryRateResult:
    """
    Benjamini–Hochberg procedure for controlling the false discovery rate.

    - p_values may include None; those hypotheses are treated as not testable (never rejected).
    - Returns rejected indices and BH-adjusted p-values (q-values) for testable entries.
    """
    hypothesis_count = int(len(p_values))
    testable: List[Tuple[int, float]] = []
    for index, value in enumerate(p_values):
        if value is None:
            continue
        pv = float(value)
        if pv != pv:
            continue
        if pv < 0.0 or pv > 1.0:
            continue
        testable.append((int(index), float(pv)))

    m = int(len(testable))
    adjusted: List[Optional[float]] = [None for _ in range(hypothesis_count)]
    if m == 0:
        return BenjaminiHochbergFalseDiscoveryRateResult(
            false_discovery_rate=float(false_discovery_rate),
            hypothesis_count=hypothesis_count,
            discoveries_count=0,
            rejected_indices=[],
            adjusted_p_values=adjusted,
        )

    testable_sorted = sorted(testable, key=lambda kv: kv[1])
    bh_values: List[Tuple[int, float]] = []
    for rank_one_based, (index, pv) in enumerate(testable_sorted, start=1):
        bh_values.append((int(index), float(pv) * float(m) / float(rank_one_based)))

    # Enforce monotonicity of adjusted p-values (q-values): q_i = min_{j>=i} bh_j
    running_minimum = 1.0
    for index, value in reversed(bh_values):
        running_minimum = min(float(running_minimum), float(value))
        adjusted[index] = float(min(1.0, running_minimum))

    threshold = float(false_discovery_rate)
    rejected: List[int] = []
    max_rank_rejected = 0
    for rank_one_based, (index, pv) in enumerate(testable_sorted, start=1):
        if float(pv) <= (float(rank_one_based) / float(m)) * float(threshold):
            max_rank_rejected = int(rank_one_based)
    if max_rank_rejected > 0:
        rejected = [int(index) for index, _ in testable_sorted[:max_rank_rejected]]

    return BenjaminiHochbergFalseDiscoveryRateResult(
        false_discovery_rate=float(false_discovery_rate),
        hypothesis_count=hypothesis_count,
        discoveries_count=int(len(rejected)),
        rejected_indices=rejected,
        adjusted_p_values=adjusted,
    )

