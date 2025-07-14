"""
Runner for secure hash (compression) experiments.

Produces report.json + report.md with:
  - rho-structure decomposition (tail + cycle + tree)
  - collision metrics (collision count, preimage distribution)
  - avalanche effect
  - merge depth (convergence winding quantification)
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List

from .toy_sponge import DirectCompression, DirectCompressionConfig, ToySponge, ToySpongeConfig
from .rho_analysis import RhoStructureMetrics, compute_rho_structure
from .collision_metrics import (
    AvalancheMetrics,
    CollisionMetrics,
    MergeDepthMetrics,
    compute_avalanche,
    compute_collision_metrics,
    compute_merge_depth,
)
from ..metrics.trajectory import (
    compute_winding_trajectory_report,
    aggregate_winding_trajectory_reports,
)
from ..alignment.todo_alignment import build_todo_alignment_section
from ..report import attach_report_contract_metadata


def _compute_hash_structural_diagnosis(
    *,
    rho: Dict[str, Any],
    collision_metrics: Dict[str, Any],
    avalanche: Dict[str, Any],
    merge_depth: Dict[str, Any],
    q: int,
) -> List[Dict[str, Any]]:
    """Build structural_diagnosis list (id, flag, value, threshold_or_note) for hash report."""
    import math
    out: List[Dict[str, Any]] = []

    collision_count = int(rho.get("collision_count", 0))
    max_in_degree = int(rho.get("max_in_degree", 0))
    collision_threshold = max(1, q // 4)
    flag_collision = collision_count > collision_threshold or max_in_degree > collision_threshold
    out.append({
        "identifier": "collision_high",
        "flag": bool(flag_collision),
        "value": {"collision_count": collision_count, "max_in_degree": max_in_degree},
        "threshold_or_note": f"collision_count or max_in_degree > {collision_threshold} (q/4)",
    })

    max_tail = int(rho.get("max_tail_length", 0))
    tail_threshold = max(1, int(math.sqrt(q))) if q > 0 else 1
    flag_rho = max_tail > tail_threshold
    out.append({
        "identifier": "rho_tail_long",
        "flag": bool(flag_rho),
        "value": max_tail,
        "threshold_or_note": f"max_tail_length > {tail_threshold} (sqrt(q))",
    })

    mean_ham_frac = float(avalanche.get("mean_hamming_fraction", 0.5))
    flag_avalanche = mean_ham_frac < 0.4
    out.append({
        "identifier": "avalanche_weak",
        "flag": bool(flag_avalanche),
        "value": round(mean_ham_frac, 4),
        "threshold_or_note": "mean_hamming_fraction < 0.4 (ideal 0.5)",
    })

    mean_merge = float(merge_depth.get("mean_merge_depth", 0))
    merge_threshold = max(1.0, math.sqrt(q)) if q > 0 else 1.0
    flag_merge = mean_merge > merge_threshold
    out.append({
        "identifier": "merge_depth_high",
        "flag": bool(flag_merge),
        "value": round(mean_merge, 2),
        "threshold_or_note": f"mean_merge_depth > {merge_threshold:.1f}",
    })

    return out


def run_hash_experiment_direct(config: DirectCompressionConfig) -> Dict[str, Any]:
    """
    Run compression analysis on the direct (non-injective) compression function.
    This is the best way to see rho-structure on small domains.
    """
    comp = DirectCompression(config)
    q = comp.state_space_size
    f = comp.as_successor()
    bw = int(config.word_bits)

    rho = compute_rho_structure(successor=f, state_count=q)
    collisions = compute_collision_metrics(successor=f, state_count=q)
    avalanche = compute_avalanche(successor=f, state_count=q, bit_width=bw)
    merge = compute_merge_depth(successor=f, state_count=q, pair_count=min(200, q * q), rng_seed=config.sbox_seed)
    theory_correspondence = _build_hash_theory_correspondence(
        config=config.as_dict(),
        rho=rho,
        merge=merge,
        construction="direct",
        fixed_message_block=None,
    )

    structural_diagnosis = _compute_hash_structural_diagnosis(
        rho=rho.as_dict(),
        collision_metrics=collisions.as_dict(),
        avalanche=avalanche.as_dict(),
        merge_depth=merge.as_dict(),
        q=int(q),
    )

    report = {
        "experiment_type": "secure_hash_direct_compression",
        "config": config.as_dict(),
        "state_space_size": int(q),
        "rho_structure": rho.as_dict(),
        "collision_metrics": collisions.as_dict(),
        "avalanche": avalanche.as_dict(),
        "merge_depth": merge.as_dict(),
        "performance_budget": {
            "branch": "strict_exhaustive",
            "within_budget": bool(int(q) <= 65536),
            "trace_count_effective": int(q),
            "empirical_trace_threshold": 4096,
            "exhaustive_state_count_estimate": int(q),
            "exhaustive_threshold": 65536,
            "overrun_amount": int(max(0, int(q) - 65536)),
            "budget_assertion": "state_space_size <= exhaustive_threshold",
        },
        "structural_diagnosis": structural_diagnosis,
        "theory_correspondence": theory_correspondence,
        "winding_trajectory_note": "Not applicable (direct compression has no internal cipher).",
    }
    attach_report_contract_metadata(report)
    report["todo_alignment"] = build_todo_alignment_section(report)
    return report


# Exhaustive sponge analysis cost is O(rate_q) for rho/collision and O(rate_q * rate_bits) for avalanche.
# merge_depth does up to (pair_count * max_steps) successor calls with max_steps = rate_q * 2.
# To avoid "stuck" when rate_bits is large, cap rate space for full exhaustive run.
MAX_RATE_Q_FOR_FULL_SPONGE = 65536


def run_hash_experiment_sponge(config: ToySpongeConfig, message_blocks_count: int = 4) -> Dict[str, Any]:
    """
    Run compression analysis on the sponge construction.
    We analyze the single-step compression function (chaining_value, msg) -> chaining_value'
    by fixing a message block and studying the resulting function on the rate space.
    """
    sponge = ToySponge(config)
    rate_q = sponge.rate_space_size
    if rate_q > MAX_RATE_Q_FOR_FULL_SPONGE:
        raise ValueError(
            f"rate_space_size {rate_q} (2^{config.rate_bits}) exceeds cap {MAX_RATE_Q_FOR_FULL_SPONGE}; "
            "use smaller --rate-bits (e.g. <= 12) to avoid long-running exhaustive analysis."
        )

    fixed_msg = 0
    def sponge_compression_fixed_msg(cv: int) -> int:
        return sponge.compression_function(cv, fixed_msg)

    rho = compute_rho_structure(successor=sponge_compression_fixed_msg, state_count=rate_q)
    collisions = compute_collision_metrics(successor=sponge_compression_fixed_msg, state_count=rate_q)
    avalanche = compute_avalanche(
        successor=sponge_compression_fixed_msg,
        state_count=rate_q,
        bit_width=config.rate_bits,
    )
    merge = compute_merge_depth(
        successor=sponge_compression_fixed_msg,
        state_count=rate_q,
        pair_count=min(200, rate_q * rate_q),
    )
    theory_correspondence = _build_hash_theory_correspondence(
        config=config.as_dict(),
        rho=rho,
        merge=merge,
        construction="sponge",
        fixed_message_block=int(fixed_msg),
    )

    multi_msg_collisions: Dict[str, Any] = {}
    if rate_q <= 4096:
        outputs_by_msg: Dict[int, List[int]] = {}
        for msg in range(min(rate_q, 16)):
            digests = []
            for cv in range(rate_q):
                d = sponge.compression_function(cv, msg)
                digests.append(d)
            distinct = len(set(digests))
            outputs_by_msg[str(msg)] = {
                "distinct_outputs": distinct,
                "collision_fraction": 1.0 - float(distinct) / float(rate_q),
            }
        multi_msg_collisions = {"per_message_block": outputs_by_msg}

    # Winding trajectory: sponge internal permutation is the block cipher. Sample a few
    # internal states and run the cipher to get (states, events), then aggregate.
    state_space_size = sponge.state_space_size
    trajectory_reports: List[Dict[str, Any]] = []
    sample_count = min(8, state_space_size)
    step = max(1, (state_space_size - 1) // sample_count) if state_space_size > 1 else 1
    for j in range(sample_count):
        internal_state = (j * step) % state_space_size
        states, events = sponge._cipher.run(internal_state)
        trajectory_reports.append(
            compute_winding_trajectory_report(states=states, events=events)
        )
    winding_aggregate = aggregate_winding_trajectory_reports(trajectory_reports)

    structural_diagnosis = _compute_hash_structural_diagnosis(
        rho=rho.as_dict(),
        collision_metrics=collisions.as_dict(),
        avalanche=avalanche.as_dict(),
        merge_depth=merge.as_dict(),
        q=int(rate_q),
    )

    report = {
        "experiment_type": "secure_hash_sponge",
        "config": config.as_dict(),
        "rate_space_size": int(rate_q),
        "state_space_size": int(sponge.state_space_size),
        "fixed_message_block": int(fixed_msg),
        "rho_structure": rho.as_dict(),
        "collision_metrics": collisions.as_dict(),
        "avalanche": avalanche.as_dict(),
        "merge_depth": merge.as_dict(),
        "performance_budget": {
            "branch": "strict_exhaustive",
            "within_budget": bool(int(rate_q) <= int(MAX_RATE_Q_FOR_FULL_SPONGE)),
            "trace_count_effective": int(rate_q),
            "empirical_trace_threshold": 4096,
            "exhaustive_state_count_estimate": int(rate_q),
            "exhaustive_threshold": int(MAX_RATE_Q_FOR_FULL_SPONGE),
            "overrun_amount": int(max(0, int(rate_q) - int(MAX_RATE_Q_FOR_FULL_SPONGE))),
            "budget_assertion": "rate_space_size <= exhaustive_threshold",
        },
        "structural_diagnosis": structural_diagnosis,
        "theory_correspondence": theory_correspondence,
        "multi_message_analysis": multi_msg_collisions,
        "winding_trajectory_profile": winding_aggregate,
        "winding_trajectory_example": trajectory_reports[0] if trajectory_reports else None,
    }
    attach_report_contract_metadata(report)
    report["todo_alignment"] = build_todo_alignment_section(report)
    return report


def _build_hash_theory_correspondence(
    *,
    config: Dict[str, Any],
    rho: RhoStructureMetrics,
    merge: MergeDepthMetrics,
    construction: str,
    fixed_message_block: int | None,
) -> Dict[str, Any]:
    """Build explicit mapping from Section-7 symbols to hash/compression implementation."""
    max_in_degree = int(rho.max_in_degree)
    a_c_lower_bound = max(1, max_in_degree)
    d_c_lower_bound = float(math.log2(float(a_c_lower_bound)))
    if construction == "direct":
        implementation = "secure_hash/toy_sponge.py::DirectCompression.__call__"
        update_law = "C_Theta(x)=sbox[x] XOR (x >> shift)"
    else:
        implementation = "secure_hash/toy_sponge.py::ToySponge.compression_function"
        update_law = "C_{Theta,m}(cv)=permute(cv XOR m) mod 2^rate_bits"
    return {
        "section": "paper_2_1_section_7",
        "path_type": "compression",
        "construction": str(construction),
        "theta": dict(config),
        "symbol_mapping": {
            "C_{Theta,m}": implementation,
            "state_update_law": update_law,
            "fixed_message_block": fixed_message_block,
        },
        "difficulty_lower_bound_proxy": {
            "M_C_max_observed": max_in_degree,
            "A_C_T_lower_bound": int(a_c_lower_bound),
            "D_C_T_lower_bound_bits": float(d_c_lower_bound),
        },
        "theorem_2_proxies": {
            "d_bar_merge_proxy": float(merge.mean_merge_depth),
            "Delta_in_proxy": int(max_in_degree),
            "collision_count": int(rho.collision_count),
        },
    }


def write_hash_report(report: Dict[str, Any], out_dir: str) -> None:
    """Write report.json + report.md for a hash experiment."""
    os.makedirs(out_dir, exist_ok=True)

    json_path = os.path.join(out_dir, "report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"Wrote: {json_path}")

    md_path = os.path.join(out_dir, "report.md")
    lines = _build_markdown(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote: {md_path}")


def _build_markdown(report: Dict[str, Any]) -> List[str]:
    config = report.get("config", {})
    exp_type = report.get("experiment_type", "?")
    lines: List[str] = []
    lines.append("# Secure Hash / Compression Analysis Report")
    lines.append("")
    lines.append(f"## Experiment Type: `{exp_type}`")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    for k, v in config.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")

    rho = report.get("rho_structure", {})
    lines.append("## Rho-Structure (Compression Winding)")
    lines.append("")
    lines.append(f"- State space: {rho.get('state_count', '?')}")
    lines.append(f"- Image count: {rho.get('image_count', '?')} (collision_count = **{rho.get('collision_count', '?')}**)")
    lines.append(f"- Cycles: {rho.get('cycle_count', '?')} (total cycle nodes: {rho.get('total_cycle_nodes', '?')})")
    lines.append(f"- Tail nodes: {rho.get('tail_node_count', '?')}")
    lines.append(f"- Max tail length: **{rho.get('max_tail_length', '?')}** (mean: {rho.get('mean_tail_length', 0):.2f})")
    lines.append(f"- Max in-degree: **{rho.get('max_in_degree', '?')}** (largest collision cluster)")
    lines.append(f"- Trees hanging off cycles: {rho.get('tree_count', '?')}")
    lines.append("")

    clh = rho.get("cycle_length_histogram", {})
    if clh:
        lines.append("### Cycle Length Histogram")
        lines.append("")
        for length, count in sorted(clh.items(), key=lambda x: int(x[0])):
            lines.append(f"  - length {length}: {count} cycle(s)")
        lines.append("")

    col = report.get("collision_metrics", {})
    lines.append("## Collision Metrics")
    lines.append("")
    lines.append(f"- Collision pairs: **{col.get('collision_pair_count', '?')}**")
    lines.append(f"- Max preimage size: {col.get('max_preimage_size', '?')}")
    lines.append(f"- Mean preimage size: {col.get('mean_preimage_size', 0):.2f}")
    mc = col.get("multi_collision_counts", {})
    if mc:
        lines.append("- Multi-collision counts:")
        for k, v in sorted(mc.items(), key=lambda x: int(x[0])):
            lines.append(f"  - >= {k} preimages: {v} outputs")
    lines.append("")

    av = report.get("avalanche", {})
    lines.append("## Avalanche Effect")
    lines.append("")
    lines.append(f"- Bit width: {av.get('bit_width', '?')}")
    lines.append(f"- Pairs tested: {av.get('pair_count', '?')}")
    lines.append(f"- Mean Hamming distance: **{av.get('mean_hamming_distance', 0):.3f}**")
    lines.append(f"- Mean Hamming fraction: **{av.get('mean_hamming_fraction', 0):.4f}** (ideal = 0.5)")
    lines.append(f"- Range: [{av.get('min_hamming_distance', '?')}, {av.get('max_hamming_distance', '?')}]")
    lines.append("")

    md = report.get("merge_depth", {})
    lines.append("## Merge Depth (Convergence Winding)")
    lines.append("")
    lines.append(f"- Pairs tested: {md.get('pair_count', '?')}")
    lines.append(f"- Merged fraction: **{md.get('merged_fraction', 0):.4f}**")
    lines.append(f"- Mean merge depth: **{md.get('mean_merge_depth', 0):.2f}**")
    lines.append(f"- Max merge depth: {md.get('max_merge_depth', '?')}")
    lines.append("")

    diag = report.get("structural_diagnosis", [])
    if isinstance(diag, list) and diag:
        lines.append("## Structural diagnosis (Information Winding Theory lesion-style)")
        lines.append("")
        for item in diag:
            if not isinstance(item, dict):
                continue
            did = item.get("identifier", "?")
            flag = item.get("flag", False)
            val = item.get("value", "?")
            note = item.get("threshold_or_note", "")
            if isinstance(val, dict):
                val = str(val)
            lines.append(f"- **{did}**: flag=`{flag}`, value=`{val}` — {note}")
        lines.append("")

    mma = report.get("multi_message_analysis", {})
    per_msg = mma.get("per_message_block", {})
    if per_msg:
        lines.append("## Multi-Message Collision Analysis (Sponge)")
        lines.append("")
        for msg_key, info in sorted(per_msg.items(), key=lambda x: int(x[0])):
            lines.append(f"- msg={msg_key}: distinct={info['distinct_outputs']}, collision_frac={info['collision_fraction']:.4f}")
        lines.append("")

    wt = report.get("winding_trajectory_profile", {})
    if wt:
        lines.append("## Winding Trajectory Profile (Internal Permutation)")
        lines.append("")
        ih = wt.get("information_height_summary", {})
        if ih:
            lines.append(f"- Final height (mean): {ih.get('final_height', {}).get('mean', '?')}")
            lines.append(f"- Max height (mean): {ih.get('max_height', {}).get('mean', '?')}")
        lines.append(f"- Traces aggregated: {wt.get('trace_count', '?')}")
        lines.append("")
    elif report.get("experiment_type") == "secure_hash_direct_compression":
        lines.append("## Winding Trajectory")
        lines.append("")
        lines.append("- Not applicable (direct compression has no internal cipher).")
        lines.append("")

    theory = report.get("theory_correspondence", {})
    if isinstance(theory, dict) and theory:
        lines.append("## Theory Correspondence (Paper Section 7)")
        lines.append("")
        sym = theory.get("symbol_mapping", {}) if isinstance(theory.get("symbol_mapping", {}), dict) else {}
        lb = theory.get("difficulty_lower_bound_proxy", {}) if isinstance(theory.get("difficulty_lower_bound_proxy", {}), dict) else {}
        p2 = theory.get("theorem_2_proxies", {}) if isinstance(theory.get("theorem_2_proxies", {}), dict) else {}
        lines.append(f"- Path type: `{theory.get('path_type', '?')}` (`{theory.get('construction', '?')}`)")
        lines.append(f"- `C_{{Theta,m}}` implementation: `{sym.get('C_{Theta,m}', '?')}`")
        lines.append(f"- State update law: `{sym.get('state_update_law', '?')}`")
        lines.append(f"- Lower bound proxy: `A_C(T)>= {lb.get('A_C_T_lower_bound', '?')}`, `D_C(T)>= {lb.get('D_C_T_lower_bound_bits', '?')}`")
        lines.append(
            "- Theorem-2 proxies: "
            f"`mean_merge_depth={p2.get('d_bar_merge_proxy', '?')}`, "
            f"`max_in_degree={p2.get('Delta_in_proxy', '?')}`, "
            f"`collision_count={p2.get('collision_count', '?')}`"
        )
        lines.append("")

    return lines
