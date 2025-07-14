"""
結構證據型別：可審計、可復現的 evidence object。
縱向 per_step_height_delta + 橫向 tangle + 結構摘要 summary。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class StructureEvidence:
    """
    統一結構證據：S-box 或 P-box 的縱向高度增量與橫向纏繞證據。
    """
    kind: Literal["sbox", "pbox"]
    q: int
    w: int
    per_step_height_delta: tuple[int, ...]
    tangle: dict[str, int | float | list[int]]
    summary: dict[str, Any]
