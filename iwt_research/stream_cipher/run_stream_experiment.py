"""
Runner for stream cipher (expansion / PRG) experiments.

Produces report.json + report.md with:
  - keystream period detection
  - autocorrelation profile
  - seed sensitivity (divergence of neighbor seeds)
  - output coverage and statistical distance from uniform
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Dict, List

from .toy_prg import ToyPRGConfig, generate_keystream, generate_keystream_from_seed
from .keystream_metrics import (
    AutocorrelationResult,
    CoverageResult,
    PeriodDetectionResult,
    SeedSensitivityResult,
    compute_autocorrelation,
    compute_coverage,
    compute_seed_sensitivity,
    detect_period_brent,
)
from ..metrics.trajectory import (
    compute_winding_trajectory_report,
    aggregate_winding_trajectory_reports,
)
from ..alignment.todo_alignment import build_todo_alignment_section
from ..report import attach_report_contract_metadata


def run_stream_experiment(prg_config: ToyPRGConfig, neighbor_count: int = 4) -> Dict[str, Any]:
    """Run a full stream cipher / PRG analysis and return a report dict."""

    keystream, meta = generate_keystream(prg_config, collect_internal_traces=True)
    state_space_size = int(meta["state_space_size"])

    period_result = detect_period_brent(keystream)

    acorr_result = compute_autocorrelation(keystream, max_lag=min(64, len(keystream) // 4))

    coverage_result = compute_coverage(keystream, state_space_size)

    base_seed = int(prg_config.cipher_seed)
    neighbor_seeds = [base_seed + index + 1 for index in range(int(neighbor_count))]
    neighbor_keystreams = [
        generate_keystream_from_seed(prg_config, seed_value) for seed_value in neighbor_seeds
    ]
    sensitivity_result = compute_seed_sensitivity(keystream, neighbor_keystreams, neighbor_seeds)

    internal_traces = meta.get("internal_traces", [])
    per_block_trajectory_reports: List[Dict[str, Any]] = []
    for states, events in internal_traces:
        per_block_trajectory_reports.append(
            compute_winding_trajectory_report(states=states, events=events)
        )

    trajectory_summary = aggregate_winding_trajectory_reports(per_block_trajectory_reports)

    # Structural diagnosis (Information Winding Theory lesion-style flags for stream cipher).
    structural_diagnosis = _compute_stream_structural_diagnosis(
        period_result=period_result,
        coverage_result=coverage_result,
        acorr_result=acorr_result,
        sensitivity_result=sensitivity_result,
        state_space_size=state_space_size,
        keystream_length=len(keystream),
    )
    theory_correspondence = _build_stream_theory_correspondence(
        prg_config=prg_config,
        period_result=period_result,
        coverage_result=coverage_result,
        sensitivity_result=sensitivity_result,
    )

    report: Dict[str, Any] = {
        "experiment_type": "stream_cipher_prg",
        "config": prg_config.as_dict(),
        "state_space_size": int(state_space_size),
        "keystream_length": len(keystream),
        "period_detection": period_result.as_dict(),
        "autocorrelation": acorr_result.as_dict(),
        "coverage": coverage_result.as_dict(),
        "seed_sensitivity": sensitivity_result.as_dict(),
        "winding_trajectory_profile": trajectory_summary,
        "performance_budget": {
            "branch": "empirical_sampling",
            "within_budget": bool(len(keystream) <= 4096),
            "trace_count_effective": int(len(keystream)),
            "empirical_trace_threshold": 4096,
            "exhaustive_state_count_estimate": int(state_space_size),
            "exhaustive_threshold": int(state_space_size),
            "overrun_amount": int(max(0, len(keystream) - 4096)),
            "budget_assertion": "keystream_length <= empirical_trace_threshold",
        },
        "structural_diagnosis": structural_diagnosis,
        "theory_correspondence": theory_correspondence,
    }
    if per_block_trajectory_reports:
        report["winding_trajectory_example"] = per_block_trajectory_reports[0]
    attach_report_contract_metadata(report)
    report["todo_alignment"] = build_todo_alignment_section(report)

    return report


def _compute_stream_structural_diagnosis(
    *,
    period_result: PeriodDetectionResult,
    coverage_result: CoverageResult,
    acorr_result: AutocorrelationResult,
    sensitivity_result: SeedSensitivityResult,
    state_space_size: int,
    keystream_length: int,
) -> List[Dict[str, Any]]:
    """Build structural_diagnosis list (id, flag, value, threshold_or_note) for stream report."""
    import math
    out: List[Dict[str, Any]] = []

    period = int(period_result.period)
    period_threshold = max(2, int(math.sqrt(state_space_size))) if state_space_size > 0 else 2
    flag_period = period == 0 or period <= period_threshold
    out.append({
        "identifier": "period_short",
        "flag": bool(flag_period),
        "value": period,
        "threshold_or_note": f"period not detected or <= {period_threshold} (sqrt(q) or 2)",
    })

    coverage_frac = float(coverage_result.coverage_fraction)
    flag_coverage = coverage_frac < 0.9
    out.append({
        "identifier": "coverage_low",
        "flag": bool(flag_coverage),
        "value": round(coverage_frac, 6),
        "threshold_or_note": "coverage_fraction < 0.9",
    })

    acorr_vals = list(acorr_result.values)
    max_abs_acorr = max((abs(v) for v in acorr_vals), default=0.0)
    flag_acorr = max_abs_acorr > 0.5
    out.append({
        "identifier": "autocorrelation_high",
        "flag": bool(flag_acorr),
        "value": round(max_abs_acorr, 6),
        "threshold_or_note": "max |autocorrelation| > 0.5",
    })

    mean_div = float(sensitivity_result.mean_first_divergence_position)
    div_threshold = max(1, keystream_length // 4)
    flag_sensitivity = mean_div > div_threshold
    out.append({
        "identifier": "sensitivity_low",
        "flag": bool(flag_sensitivity),
        "value": round(mean_div, 2),
        "threshold_or_note": f"mean_first_divergence_position > {div_threshold} (late divergence)",
    })

    return out


def _build_stream_theory_correspondence(
    *,
    prg_config: ToyPRGConfig,
    period_result: PeriodDetectionResult,
    coverage_result: CoverageResult,
    sensitivity_result: SeedSensitivityResult,
) -> Dict[str, Any]:
    """Build explicit mapping from Section-7 symbols to stream implementation."""
    keystream_mode = str(prg_config.mode).strip().lower()
    if keystream_mode == "counter":
        state_update_law = "x_t=(IV+t) mod q, y_t=E_k(x_t)"
    else:
        state_update_law = "s_{t+1}=E_k(s_t), y_t=s_t"
    return {
        "section": "paper_2_1_section_7",
        "path_type": "expansion",
        "theta": {
            "cipher_preset": str(prg_config.cipher_preset),
            "word_bits": int(prg_config.word_bits),
            "rounds": int(prg_config.rounds),
            "seed": int(prg_config.cipher_seed),
            "mode": keystream_mode,
            "initial_value": int(prg_config.initial_value),
            "output_length": int(prg_config.output_length),
        },
        "symbol_mapping": {
            "E_{Theta,T}": "stream_cipher/toy_prg.py::generate_keystream",
            "state_update_law": state_update_law,
        },
        "difficulty_proxy": {
            "assumption": "Permutation-driven single-valued update in tracked window",
            "A_E_T": 1,
            "D_E_T_bits": 0.0,
        },
        "observable_proxies": {
            "period": int(period_result.period),
            "coverage_fraction": float(coverage_result.coverage_fraction),
            "mean_first_divergence_position": float(
                sensitivity_result.mean_first_divergence_position
            ),
            "mean_hamming_fraction": float(sensitivity_result.mean_hamming_fraction),
        },
    }


def write_stream_report(report: Dict[str, Any], out_dir: str) -> None:
    """Write report.json + report.md for a stream cipher experiment."""
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
    report_config = report.get("config", {})
    lines: List[str] = []
    lines.append("# Stream Cipher / PRG Analysis Report")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- cipher_preset: `{report_config.get('cipher_preset', '?')}`")
    lines.append(f"- word_bits: `{report_config.get('word_bits', '?')}`")
    lines.append(f"- rounds: `{report_config.get('rounds', '?')}`")
    lines.append(f"- mode: `{report_config.get('mode', '?')}`")
    lines.append(f"- initial_value: `{report_config.get('initial_value', '?')}`")
    lines.append(f"- cipher_seed: `{report_config.get('cipher_seed', '?')}`")
    lines.append(f"- output_length: `{report_config.get('output_length', '?')}`")
    lines.append(f"- state_space_size: `{report.get('state_space_size', '?')}`")
    lines.append("")

    pd = report.get("period_detection", {})
    lines.append("## Period Detection")
    lines.append("")
    if pd.get("period", 0) > 0:
        lines.append(f"- Period: **{pd['period']}**")
        lines.append(f"- Tail length: {pd.get('tail_length', '?')}")
        lines.append(f"- Total rho length: {pd.get('total_rho_length', '?')}")
    else:
        lines.append(f"- No period detected within keystream window ({pd.get('method', '?')})")
    lines.append("")

    ac = report.get("autocorrelation", {})
    vals = ac.get("values", [])
    lines.append("## Autocorrelation")
    lines.append("")
    if vals:
        max_abs = max(abs(v) for v in vals) if vals else 0.0
        lines.append(f"- Max |autocorrelation| over lags 1..{ac.get('max_lag', '?')}: **{max_abs:.6f}**")
        top5 = sorted(enumerate(vals), key=lambda x: abs(x[1]), reverse=True)[:5]
        for idx, val in top5:
            lines.append(f"  - lag {idx + 1}: {val:.6f}")
    else:
        lines.append("- (no data)")
    lines.append("")

    cov = report.get("coverage", {})
    lines.append("## Output Coverage")
    lines.append("")
    lines.append(f"- Distinct values: {cov.get('distinct_values', '?')} / {cov.get('state_space_size', '?')}")
    lines.append(f"- Coverage fraction: **{cov.get('coverage_fraction', 0):.4f}**")
    lines.append(f"- Statistical distance from uniform: **{cov.get('statistical_distance_from_uniform', 0):.6f}**")
    lines.append("")

    ss = report.get("seed_sensitivity", {})
    lines.append("## Seed Sensitivity (Expansion Winding)")
    lines.append("")
    lines.append(f"- Neighbor pairs tested: {ss.get('pair_count', '?')}")
    lines.append(f"- Mean first divergence position: **{ss.get('mean_first_divergence_position', 0):.2f}**")
    lines.append(f"- Mean Hamming fraction: **{ss.get('mean_hamming_fraction', 0):.4f}**")
    lines.append("")

    wt = report.get("winding_trajectory_profile", {})
    if wt:
        lines.append("## Winding Trajectory Profile (Internal Cipher)")
        lines.append("")
        ih = wt.get("information_height_summary", {})
        if ih:
            lines.append(f"- Final height (mean): {ih.get('final_height', {}).get('mean', '?')}")
            lines.append(f"- Max height (mean): {ih.get('max_height', {}).get('mean', '?')}")
            lines.append(f"- Mean increment per step: {ih.get('mean_increment_per_step', {}).get('mean', '?')}")
        cd = wt.get("cross_domain_summary", {})
        if cd:
            lines.append(f"- Cross-domain events (mean): {cd.get('total_cross_domain_events', {}).get('mean', '?')}")
        lines.append(f"- Traces aggregated: {wt.get('trace_count', '?')}")
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
            lines.append(f"- **{did}**: flag=`{flag}`, value=`{val}` — {note}")
        lines.append("")

    theory = report.get("theory_correspondence", {})
    if isinstance(theory, dict) and theory:
        lines.append("## Theory Correspondence (Paper Section 7)")
        lines.append("")
        sym = theory.get("symbol_mapping", {}) if isinstance(theory.get("symbol_mapping", {}), dict) else {}
        diff = theory.get("difficulty_proxy", {}) if isinstance(theory.get("difficulty_proxy", {}), dict) else {}
        obs = theory.get("observable_proxies", {}) if isinstance(theory.get("observable_proxies", {}), dict) else {}
        lines.append(f"- Path type: `{theory.get('path_type', '?')}`")
        lines.append(f"- `E_{{Theta,T}}` implementation: `{sym.get('E_{Theta,T}', '?')}`")
        lines.append(f"- State update law: `{sym.get('state_update_law', '?')}`")
        lines.append(f"- Ambiguity proxy: `A_E(T)={diff.get('A_E_T', '?')}`, `D_E(T)={diff.get('D_E_T_bits', '?')}`")
        lines.append(f"- Observables: period={obs.get('period', '?')}, coverage_fraction={obs.get('coverage_fraction', '?')}")
        lines.append("")

    return lines
