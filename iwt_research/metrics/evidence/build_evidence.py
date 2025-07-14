"""
統一入口：build_structure_evidence(kind, output_sequence, q, w) -> StructureEvidence。
core 只調用此函數，再從 evidence.per_step_height_delta[index] 取 δ。
"""
from __future__ import annotations

from typing import Literal

from .types import StructureEvidence


def build_structure_evidence(
    kind: Literal["sbox", "pbox"],
    output_sequence: list[int],
    q: int,
    w: int = 0,
    *,
    head_len: int = 20,
) -> StructureEvidence:
    """
    產出結構證據：縱向 per_step_height_delta、橫向 tangle、摘要 summary。
    kind="sbox"：解纏繞 + turn/cross；kind="pbox"：有界 lift + inv(π) + cycle_stats。
    """
    modulus_q = int(q)
    window_start = int(w)
    if kind == "sbox":
        from ..structure_height.sbox_height import (
            _crossing_count,
            _sbox_lifted_sequence,
            _turn_count,
            per_step_structure_increments_sbox,
        )
        per_step_deltas = per_step_structure_increments_sbox(
            output_sequence, modulus_q, window_start
        )
        if len(output_sequence) != modulus_q:
            tangle = {"turn_count": 0, "crossing_count": 0}
            summary = {
                "total_winding_strength": 0,
                "net_winding": 0,
                "turn_count": 0,
                "crossing_count": 0,
                "increment_count": 0,
                "increments_head": [],
            }
        else:
            lifted_sequence = _sbox_lifted_sequence(output_sequence, modulus_q, window_start)
            input_indices = [window_start + t for t in range(modulus_q)]
            turn_count_val = _turn_count(lifted_sequence)
            crossing_count_val = _crossing_count(
                input_indices, lifted_sequence
            )
            tangle = {
                "turn_count": turn_count_val,
                "crossing_count": crossing_count_val,
            }
            summary = {
                "total_winding_strength": sum(
                    abs(delta) for delta in per_step_deltas
                ),
                "net_winding": sum(per_step_deltas),
                "turn_count": turn_count_val,
                "crossing_count": crossing_count_val,
                "increment_count": len(per_step_deltas),
                "increments_head": per_step_deltas[:head_len],
            }
        return StructureEvidence(
            kind="sbox",
            q=modulus_q,
            w=window_start,
            per_step_height_delta=tuple(per_step_deltas),
            tangle=tangle,
            summary=summary,
        )
    else:
        from ..structure_height.pbox_height import per_step_structure_increments_pbox
        from ..tangling import inversion_norm, inv_parity, inversion_count_permutation
        from ..permutation import cycle_stats

        per_step_deltas = per_step_structure_increments_pbox(
            output_sequence, modulus_q, window_start
        )
        wrap_right_count = sum(1 for delta in per_step_deltas if delta == 1)
        wrap_left_count = sum(1 for delta in per_step_deltas if delta == -1)
        permutation_zero_based = [
            int(output_sequence[t]) - window_start
            for t in range(modulus_q)
        ]
        if len(output_sequence) != modulus_q or any(
            elem < 0 or elem >= modulus_q for elem in permutation_zero_based
        ):
            inversion_count = 0
            normalized_inv = 0.0
            inv_parity_value = 0
            summary = {
                "cycle_count": 0,
                "cycle_lengths": [],
                "max_cycle_length": 0,
                "fixed_point_count": 0,
                "wrap_right_count": wrap_right_count,
                "wrap_left_count": wrap_left_count,
                "wrap_strength": wrap_right_count + wrap_left_count,
                "wrap_balance": wrap_right_count - wrap_left_count,
                "increments_head": per_step_deltas[:head_len],
            }
        else:
            inversion_count = inversion_count_permutation(
                permutation_zero_based
            )
            normalized_inv = inversion_norm(inversion_count, modulus_q)
            inv_parity_value = inv_parity(inversion_count)
            cycle_stats_dict = cycle_stats(permutation_zero_based)
            summary = {
                "cycle_count": cycle_stats_dict["cycle_count"],
                "cycle_lengths": cycle_stats_dict["cycle_lengths"],
                "max_cycle_length": cycle_stats_dict["max_cycle_length"],
                "fixed_point_count": cycle_stats_dict["fixed_point_count"],
                "wrap_right_count": wrap_right_count,
                "wrap_left_count": wrap_left_count,
                "wrap_strength": wrap_right_count + wrap_left_count,
                "wrap_balance": wrap_right_count - wrap_left_count,
                "increments_head": per_step_deltas[:head_len],
            }
        tangle = {
            "inv_count": inversion_count,
            "inversion_norm": normalized_inv,
            "inv_parity": inv_parity_value,
        }
        return StructureEvidence(
            kind="pbox",
            q=modulus_q,
            w=window_start,
            per_step_height_delta=tuple(per_step_deltas),
            tangle=tangle,
            summary=summary,
        )
