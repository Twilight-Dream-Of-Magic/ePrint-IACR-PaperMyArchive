from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List

from ..utils.stats import is_finite_number


def _sanitize_for_json(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_for_json(v) for v in value]
    return value


def _format_float(value: Any, digits: int) -> str:
    if value is None or not is_finite_number(value):
        return "na"
    return f"{float(value):.{digits}f}"


def _format_ci(interval: Dict[str, Any]) -> str:
    mean = _format_float(interval.get("mean"), 6)
    low = _format_float(interval.get("lower_bound"), 6)
    high = _format_float(interval.get("upper_bound"), 6)
    return f"{mean} (CI[{low}, {high}])"


def _format_z(value: Any) -> str:
    if value is None or not is_finite_number(value):
        return "undef"
    return f"{float(value):.3f}"


def write_report(out_dir: str, data: Dict[str, Any]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "report.json")
    md_path = os.path.join(out_dir, "report.md")
    md_summary_path = os.path.join(out_dir, "report_summary.md")
    md_lesions_path = os.path.join(out_dir, "report_lesions.md")
    md_baselines_path = os.path.join(out_dir, "report_baselines.md")

    sanitized_data = _sanitize_for_json(data)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sanitized_data, f, ensure_ascii=False, indent=2, allow_nan=False)

    run_config = sanitized_data.get("config", {}) if isinstance(sanitized_data, dict) else {}
    confidence_intervals = (
        sanitized_data.get("bootstrap_confidence_intervals", {})
        if isinstance(sanitized_data, dict)
        else {}
    )
    baseline_comparison = (
        sanitized_data.get("baseline_comparison", {})
        if isinstance(sanitized_data, dict)
        else {}
    )
    lesions = sanitized_data.get("lesions", []) if isinstance(sanitized_data, dict) else []

    summary: List[str] = []
    summary.append("# Information Winding Theory Report Summary")
    summary.append("")
    summary.append("## Configuration")
    summary.append("")
    for key in (
        "cipher_preset",
        "threat_model_level",
        "word_bits",
        "lane_count",
        "rounds",
        "rotation_mode",
        "rotation_direction",
        "projection",
        "trace_count",
        "exhaustive",
    ):
        if key in run_config:
            summary.append(f"- {key}: `{run_config.get(key)}`")
    summary.append("")

    if isinstance(confidence_intervals, dict) and confidence_intervals:
        summary.append("## Bootstrap Metrics")
        summary.append("")
        for metric in (
            "wrap_event_rate",
            "trivial_self_loop_rate",
            "nontrivial_self_loop_rate",
            "self_intersection_rate",
            "projection_collision_rate",
            "coverage_rate",
            "information_height_in_building_max",
            "information_height_in_building_final",
        ):
            interval = confidence_intervals.get(metric)
            if isinstance(interval, dict):
                summary.append(f"- {metric}: **{_format_ci(interval)}**")
        summary.append("")

    if isinstance(sanitized_data.get("sampling"), dict):
        sampling = sanitized_data["sampling"]
        summary.append("## Sampling")
        summary.append("")
        summary.append(
            f"- mode: `{sampling.get('mode', '?')}`; trace_count_effective: `{sampling.get('trace_count_effective', '?')}`"
        )
        summary.append("")

    if isinstance(sanitized_data.get("high_dimensional_metrics"), dict):
        high_dimensional = sanitized_data["high_dimensional_metrics"]
        summary.append("## High-Dimensional Highlights")
        summary.append("")
        neighbor = high_dimensional.get("neighbor_separation", {})
        if isinstance(neighbor, dict):
            mean_bit = neighbor.get("mean_bit_hamming_distance_by_time", [])
            if isinstance(mean_bit, list) and mean_bit:
                summary.append(
                    f"- neighbor_separation mean_bit_hamming(t=final): **{_format_float(mean_bit[-1], 3)}**"
                )
        reachability = high_dimensional.get("empirical_reachability", {})
        if isinstance(reachability, dict) and "node_count" in reachability:
            summary.append(
                f"- empirical_reachability nodes: `{reachability.get('node_count')}`; "
                f"unreachable_fraction: **{_format_float(reachability.get('unreachable_fraction'), 3)}**"
            )
        summary.append("")

    if isinstance(sanitized_data.get("winding_trajectory_profile"), dict):
        summary.append("## Trajectory Profile")
        summary.append("")
        trajectory = sanitized_data["winding_trajectory_profile"]
        trace_count = trajectory.get("trace_count", "?")
        summary.append(f"- trace_count: `{trace_count}`")
        summary.append("")

    baselines_md: List[str] = []
    baselines_md.append("# Baseline Comparison (z-score)")
    baselines_md.append("")
    if isinstance(baseline_comparison, dict):
        for baseline_name, baseline_data in baseline_comparison.items():
            if not isinstance(baseline_data, dict):
                continue
            baselines_md.append(f"## {baseline_name}")
            baselines_md.append("")
            for metric in (
                "wrap_event_rate",
                "trivial_self_loop_rate",
                "nontrivial_self_loop_rate",
                "self_intersection_rate",
                "projection_collision_rate",
                "occupancy_rate",
            ):
                metric_data = baseline_data.get(metric, {})
                z = metric_data.get("z_score") if isinstance(metric_data, dict) else None
                baselines_md.append(f"- {metric} z: **{_format_z(z)}**")
            baselines_md.append("")

    lesions_md: List[str] = []
    lesions_md.append("# Lesions (P1-P7)")
    lesions_md.append("")
    if isinstance(lesions, list):
        for lesion_entry in lesions:
            if not isinstance(lesion_entry, dict):
                continue
            lesions_md.append(f"## {lesion_entry.get('identifier', '?')}")
            lesions_md.append("")
            lesions_md.append(f"- flag: `{bool(lesion_entry.get('flag', False))}`")
            evidence = lesion_entry.get("evidence")
            if isinstance(evidence, dict):
                lesions_md.append(f"- evidence: `{evidence}`")
            lesions_md.append("")

    with open(md_summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")
    with open(md_baselines_path, "w", encoding="utf-8") as f:
        f.write("\n".join(baselines_md) + "\n")
    with open(md_lesions_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lesions_md) + "\n")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")
