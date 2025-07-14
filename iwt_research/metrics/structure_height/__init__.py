"""
縱向高度：S 解纏繞、P 有界符號越界。
統一對外：build_structure_evidence（完整證據）；per_step_* / pbox_structure_increment_at（僅要增量時）。
"""
from __future__ import annotations

from ..evidence import build_structure_evidence
from .pbox_height import (
    per_step_structure_increments_pbox,
    pbox_structure_increment_at,
)
from .sbox_height import per_step_structure_increments_sbox

__all__ = [
    "per_step_structure_increments_sbox",
    "per_step_structure_increments_pbox",
    "pbox_structure_increment_at",
    "build_structure_evidence",
]
