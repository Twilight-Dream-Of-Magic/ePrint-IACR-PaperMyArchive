from __future__ import annotations

from typing import Any, Dict, List

from ..analysis.threat_model import ThreatModelLevel
from ..analysis.tm2_focused_probes import (
    build_tm2_focus_plan_from_observations,
    run_tm2_focused_probes,
)
from ..evidence.map_utils import peak_slice_multiplicity_point
from ..utils.event_summaries import op_family_frequencies
from ..utils.stats import (
    empirical_p_ge,
    empirical_p_le,
    empirical_quantile_pos,
    is_finite_number,
    two_sided_from_one_sided,
)
from .config import RunConfig
from .types import LesionArtifacts, RunArtifacts


def compute_lesion_artifacts(
    *,
    run_config: RunConfig,
    threat_model_level: ThreatModelLevel,
    cipher: Any,
    registered_projections: List[tuple[str, Any]],
    state_indices: List[int],
    edge_counts_total: Dict[str, int],
    region_agg_total: Dict[str, Dict[str, float]],
    ys_all: List[List[int]],
    max_abs_quotient_per_trace: List[float],
    snapshot_count_per_trace: List[int],
    omega_core_size: int,
    bootstrap_confidence_intervals: Dict[str, Any],
    structure_height_pbox: Dict[str, Any] | None,
    thresholds: Dict[str, Any],
    calibration: Dict[str, Any],
    baseline_out: Dict[str, Any],
    calibration_baseline_name: str | None,
) -> LesionArtifacts:
    lesions: List[Dict[str, Any]] = []
    tm2_focused_probes: Dict[str, Any] = {}
    tm2_witnesses: List[Dict[str, Any]] = []
    tm2_evidence_objects: List[Dict[str, Any]] = []
    is_binary = bool(getattr(cipher.domain, "is_binary", False))

    binary_degenerate: Dict[str, Any] = {}
    if is_binary:
        baseline_arx_data = baseline_out.get(
            calibration_baseline_name or "random_arx_like",
            baseline_out.get("random_arx_like", {}),
        )
        z_wrap = baseline_arx_data.get("wrap_event_rate", {}).get("z_score", float("nan"))
        binary_degenerate = {
            "modulus_q": int(cipher.domain.q),
            "wrap_event_is_informative": bool(cipher.domain.wrap_event_is_informative),
            "note": "q=2: raw wrap occurrence is high-baseline/saturating; prefer patterns (shadow/NSL/intersection).",
            "wrap_z_vs_baseline": z_wrap,
        }

    # P1: Connection-type anomaly via edge-type frequency deviation (max over types)
    pf_hat = op_family_frequencies(edge_counts_total)
    baseline_mean_op_family_freq = thresholds.get("P1", {}).get("baseline_mean_pf", {})
    diffs = {
        op_family_type: abs(
            pf_hat.get(op_family_type, 0.0)
            - float(baseline_mean_op_family_freq.get(op_family_type, 0.0))
        )
        for op_family_type in set(pf_hat.keys()).union(baseline_mean_op_family_freq.keys())
    }
    p1_stat = max(diffs.values()) if diffs else 0.0
    p1_tau = thresholds.get("P1", {}).get("threshold_max_abs_diff", float("nan"))
    top_types = sorted(diffs.items(), key=lambda kv: kv[1], reverse=True)[:8]
    s1 = calibration.get("S1_max_abs_freq_diff", []) if isinstance(calibration, dict) else []
    p1_p = empirical_p_ge(s1, float(p1_stat)) if isinstance(s1, list) else float("nan")
    p1_qpos = empirical_quantile_pos(s1, float(p1_stat)) if isinstance(s1, list) else float("nan")
    p1_es = float(p1_stat) - (
        sum(float(x) for x in s1) / len(s1)
        if isinstance(s1, list) and s1
        else float("nan")
    )
    lesions.append(
        {
            "identifier": "P1",
            "flag": bool(p1_stat > float(p1_tau)) if p1_tau == p1_tau else False,
            "evidence": {
                "stat_max_abs_freq_diff": p1_stat,
                "threshold_max_abs_diff": p1_tau,
                "p_value": p1_p,
                "quantile_pos": p1_qpos,
                "effect_size_vs_baseline_mean": p1_es,
                "multiplicity_control": "max-stat over types (controls scan bias / FWER-style)",
                "top_types": top_types,
            },
        }
    )

    # P2: Shadow slice congestion via max m_t(y)
    p2 = peak_slice_multiplicity_point(ys_all)
    tau_m = thresholds.get("P2", {}).get("threshold_max_mechanism_side", float("nan"))
    s2 = calibration.get("S2_max_m", []) if isinstance(calibration, dict) else []
    p2_stat = float(p2["max_multiplicity"])
    p2_p = empirical_p_ge(s2, p2_stat) if isinstance(s2, list) else float("nan")
    p2_qpos = empirical_quantile_pos(s2, p2_stat) if isinstance(s2, list) else float("nan")
    lesions.append(
        {
            "identifier": "P2",
            "flag": bool(float(p2["max_multiplicity"]) > float(tau_m)) if tau_m == tau_m else False,
            "evidence": {
                "statistic_max_multiplicity": p2["max_multiplicity"],
                "threshold_max_mechanism_side": tau_m,
                "p_value": p2_p,
                "quantile_pos": p2_qpos,
                "argmax_time_and_projection_value": {
                    "time_index": p2["time_index"],
                    "observation_value": p2["observation_value"],
                },
                "multiplicity_control": "max-stat over (t,y)",
            },
        }
    )

    # P3: Local anomaly density over region family U = (floor, op_family)
    region_density: Dict[str, Dict[str, float]] = {}
    for rid, agg in region_agg_total.items():
        steps_r = float(agg["step_count"])
        if steps_r <= 0:
            continue
        region_density[rid] = {
            "step_count": steps_r,
            "wrap_density": float(agg["wrap_count"]) / steps_r,
            "nsl_density": float(agg["nontrivial_self_loop_count"]) / steps_r,
        }
    wrap_max = max((region_data["wrap_density"] for region_data in region_density.values()), default=0.0)
    nsl_max = max((region_data["nsl_density"] for region_data in region_density.values()), default=0.0)
    tau_wrap = thresholds.get("P3", {}).get("threshold_wrap_density_max", float("nan"))
    tau_nsl = thresholds.get("P3", {}).get("threshold_nsl_density_max", float("nan"))
    top_regions_wrap = sorted(
        ((rid, region_data["wrap_density"]) for rid, region_data in region_density.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )[:8]
    top_regions_nsl = sorted(
        ((rid, region_data["nsl_density"]) for rid, region_data in region_density.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )[:8]
    p3_flag = False
    if tau_wrap == tau_wrap and tau_nsl == tau_nsl:
        if is_binary:
            p3_flag = bool(nsl_max > float(tau_nsl))
        else:
            p3_flag = bool((wrap_max > float(tau_wrap)) or (nsl_max > float(tau_nsl)))

    stats_p3_wrap_density_max = calibration.get("S3_wrap_density_max", []) if isinstance(calibration, dict) else []
    stats_p3_nsl_density_max = calibration.get("S3_nsl_density_max", []) if isinstance(calibration, dict) else []
    p3w_p = empirical_p_ge(stats_p3_wrap_density_max, float(wrap_max)) if isinstance(stats_p3_wrap_density_max, list) else float("nan")
    p3n_p = empirical_p_ge(stats_p3_nsl_density_max, float(nsl_max)) if isinstance(stats_p3_nsl_density_max, list) else float("nan")
    p3_any = (
        min(1.0, float(p3w_p) + float(p3n_p))
        if (p3w_p == p3w_p and p3n_p == p3n_p)
        else float("nan")
    )
    lesions.append(
        {
            "identifier": "P3",
            "flag": p3_flag,
            "evidence": {
                "wrap_density_max": wrap_max,
                "threshold_wrap_density_max": tau_wrap,
                "p_value_wrap": p3w_p,
                "nsl_density_max": nsl_max,
                "threshold_nsl_density_max": tau_nsl,
                "p_value_nsl": p3n_p,
                "p_value_any_bonferroni": p3_any,
                "binary_note": "q=2: wrap occurrence saturates; P3 uses NSL-density only"
                if is_binary
                else None,
                "multiplicity_control": "max-stat over regions U; (wrap,nsl) combined by Bonferroni (2 channels)",
                "top_regions_wrap": top_regions_wrap,
                "top_regions_nsl": top_regions_nsl,
            },
        }
    )

    # P4: Coverage discordance on Omega_core = disjoint union of domains used
    r_hat = float(bootstrap_confidence_intervals["coverage_rate"]["mean"])
    coverage_lo = thresholds.get("P4", {}).get("coverage_rate_lower_bound", float("nan"))
    coverage_hi = thresholds.get("P4", {}).get("coverage_rate_upper_bound", float("nan"))
    s4 = calibration.get("S4_coverage", []) if isinstance(calibration, dict) else []
    p4_le = empirical_p_le(s4, r_hat) if isinstance(s4, list) else float("nan")
    p4_ge = empirical_p_ge(s4, r_hat) if isinstance(s4, list) else float("nan")
    p4_p2 = two_sided_from_one_sided(p4_le, p4_ge)
    p4_qpos = empirical_quantile_pos(s4, r_hat) if isinstance(s4, list) else float("nan")
    lesions.append(
        {
            "identifier": "P4",
            "flag": bool((r_hat < float(coverage_lo)) or (r_hat > float(coverage_hi)))
            if (coverage_lo == coverage_lo and coverage_hi == coverage_hi)
            else False,
            "evidence": {
                "stat_coverage": r_hat,
                "band": [coverage_lo, coverage_hi],
                "p_value_two_sided": p4_p2,
                "quantile_pos": p4_qpos,
                "omega_core_size": omega_core_size,
                "multiplicity_control": "two-sided quantile band",
            },
        }
    )

    # P5: Self-loop anomaly (trivial / non-trivial self-loop outside baseline quantile band)
    sl_hat = float(bootstrap_confidence_intervals["trivial_self_loop_rate"]["mean"])
    nsl_hat = float(bootstrap_confidence_intervals["nontrivial_self_loop_rate"]["mean"])
    sl_lo = thresholds.get("P5", {}).get("trivial_self_loop_rate_lower_bound", float("nan"))
    sl_hi = thresholds.get("P5", {}).get("trivial_self_loop_rate_upper_bound", float("nan"))
    nsl_lo = thresholds.get("P5", {}).get("nontrivial_self_loop_rate_lower_bound", float("nan"))
    nsl_hi = thresholds.get("P5", {}).get("nontrivial_self_loop_rate_upper_bound", float("nan"))
    s5sl = calibration.get("S5_SL", []) if isinstance(calibration, dict) else []
    s5nsl = calibration.get("S5_NSL", []) if isinstance(calibration, dict) else []
    p5sl = (
        two_sided_from_one_sided(empirical_p_le(s5sl, sl_hat), empirical_p_ge(s5sl, sl_hat))
        if isinstance(s5sl, list)
        else float("nan")
    )
    p5nsl = (
        two_sided_from_one_sided(empirical_p_le(s5nsl, nsl_hat), empirical_p_ge(s5nsl, nsl_hat))
        if isinstance(s5nsl, list)
        else float("nan")
    )
    p5any = min(1.0, float(p5sl) + float(p5nsl)) if (p5sl == p5sl and p5nsl == p5nsl) else float("nan")
    lesions.append(
        {
            "identifier": "P5",
            "flag": bool(
                (sl_hat < float(sl_lo))
                or (sl_hat > float(sl_hi))
                or (nsl_hat < float(nsl_lo))
                or (nsl_hat > float(nsl_hi))
            )
            if (sl_lo == sl_lo and sl_hi == sl_hi and nsl_lo == nsl_lo and nsl_hi == nsl_hi)
            else False,
            "evidence": {
                "trivial_self_loop_hat": sl_hat,
                "nontrivial_self_loop_hat": nsl_hat,
                "trivial_self_loop_range": [sl_lo, sl_hi],
                "nontrivial_self_loop_range": [nsl_lo, nsl_hi],
                "p_value_two_sided_trivial_self_loop": p5sl,
                "p_value_two_sided_nontrivial_self_loop": p5nsl,
                "p_value_any_bonferroni": p5any,
                "multiplicity_control": "two-sided bands; union by Bonferroni (2 channels)",
            },
        }
    )

    # P6: Cross-domain audit anomaly (quotient + building_exit_snapshots; full InformationHeight use)
    candidate_quotient_max = float(max(max_abs_quotient_per_trace)) if max_abs_quotient_per_trace else 0.0
    candidate_snapshot_max = int(max(snapshot_count_per_trace)) if snapshot_count_per_trace else 0
    tau_p6_q = thresholds.get("P6", {}).get("threshold_quotient_max", float("nan"))
    tau_p6_snap = thresholds.get("P6", {}).get("threshold_snapshot_max", float("nan"))
    s6q = calibration.get("S6_quotient_max", []) if isinstance(calibration, dict) else []
    s6s = calibration.get("S6_snapshot_max", []) if isinstance(calibration, dict) else []
    p6q_p = empirical_p_ge(s6q, candidate_quotient_max) if isinstance(s6q, list) and s6q else float("nan")
    p6s_p = empirical_p_ge(s6s, float(candidate_snapshot_max)) if isinstance(s6s, list) and s6s else float("nan")
    p6_flag = False
    if tau_p6_q == tau_p6_q and tau_p6_snap == tau_p6_snap:
        p6_flag = bool(candidate_quotient_max > float(tau_p6_q)) or bool(
            float(candidate_snapshot_max) > float(tau_p6_snap)
        )
    lesions.append(
        {
            "identifier": "P6",
            "flag": p6_flag,
            "evidence": {
                "stat_quotient_max": candidate_quotient_max,
                "stat_snapshot_count_max": candidate_snapshot_max,
                "threshold_quotient_max": tau_p6_q,
                "threshold_snapshot_max": tau_p6_snap,
                "p_value_quotient": p6q_p,
                "p_value_snapshot": p6s_p,
                "multiplicity_control": "max-stat over traces; (quotient, snapshot) union (2 channels)",
                "note": "cross-domain audit: quotient/snapshot channels exceed baseline quantile thresholds.",
            },
        }
    )

    # P7: same-floor non-crossing winding anomaly
    candidate_inversion_norm = float("nan")
    if isinstance(structure_height_pbox, dict) and is_finite_number(
        structure_height_pbox.get("inversion_norm")
    ):
        candidate_inversion_norm = float(structure_height_pbox["inversion_norm"])
    tau_p7 = thresholds.get("P7", {}).get("threshold_inversion_norm", float("nan"))
    s7 = calibration.get("S7_inversion_norm", []) if isinstance(calibration, dict) else []
    p7_p = (
        empirical_p_ge(s7, candidate_inversion_norm)
        if (isinstance(s7, list) and s7 and candidate_inversion_norm == candidate_inversion_norm)
        else float("nan")
    )
    p7_flag = (
        bool(candidate_inversion_norm > float(tau_p7))
        if (tau_p7 == tau_p7 and candidate_inversion_norm == candidate_inversion_norm)
        else False
    )
    lesions.append(
        {
            "identifier": "P7",
            "flag": p7_flag,
            "evidence": {
                "stat_inversion_norm": candidate_inversion_norm,
                "threshold_inversion_norm": tau_p7,
                "p_value_inversion_norm": p7_p,
                "note": "same-floor non-crossing winding: normalized inversion count exceeds baseline.",
            },
        }
    )

    if threat_model_level == ThreatModelLevel.threat_model_2_instrumented:
        focus_plan = build_tm2_focus_plan_from_observations(
            run_config=run_config,
            cipher=cipher,
            registered_projections=list(registered_projections),
            seeds=list(state_indices),
        )
        tm2_witnesses, tm2_evidence_objects = run_tm2_focused_probes(
            run_config=run_config,
            cipher=cipher,
            focus_plan=focus_plan,
        )
        tm2_focused_probes = {
            "plan": focus_plan,
            "threat_model_2_witnesses": tm2_witnesses,
            "note": "Threat Model 2 focused probes are diagnostic witnesses; they do not alter Threat Model 1 screening decisions.",
        }

    return LesionArtifacts(
        lesions=lesions,
        tm2_focused_probes=tm2_focused_probes,
        tm2_witnesses=tm2_witnesses,
        tm2_evidence_objects=tm2_evidence_objects,
        binary_degenerate=binary_degenerate,
    )


def attach_lesions(artifacts: RunArtifacts) -> RunArtifacts:
    """
    Attach lesion diagnostics and TM-2 focused probe outputs.

    Computes lesion diagnostics when missing, then normalizes outputs into
    typed artifacts.
    """
    if artifacts.threat_model_level != ThreatModelLevel.threat_model_1_black_box:
        lesions_value = artifacts.result.get("lesions", None)
        if not isinstance(lesions_value, list) or not lesions_value:
            thresholds = (
                artifacts.result.get("thresholds", {})
                if isinstance(artifacts.result.get("thresholds", {}), dict)
                else {}
            )
            calibration = (
                artifacts.result.get("calibration", {})
                if isinstance(artifacts.result.get("calibration", {}), dict)
                else {}
            )
            baseline_comparison = (
                artifacts.result.get("baseline_comparison", {})
                if isinstance(artifacts.result.get("baseline_comparison", {}), dict)
                else {}
            )

            if (not baseline_comparison) or (not thresholds):
                from .baseline_runner import compute_baseline_artifacts

                cipher = artifacts.working.get("cipher", None)
                projection = artifacts.working.get("projection", None)
                state_indices = artifacts.working.get("state_indices", [])
                total_steps = artifacts.working.get("total_steps", 0)
                omega_core_size = artifacts.working.get("omega_core_size", 0)
                if (
                    cipher is not None
                    and projection is not None
                    and isinstance(state_indices, list)
                    and int(total_steps) > 0
                    and int(omega_core_size) > 0
                ):
                    baseline_artifacts = compute_baseline_artifacts(
                        run_config=artifacts.run_config,
                        cipher=cipher,
                        state_indices=[int(x) for x in state_indices],
                        total_steps=int(total_steps),
                        proj=projection,
                        omega_core_size=int(omega_core_size),
                        bootstrap_confidence_intervals=(
                            artifacts.result.get("bootstrap_confidence_intervals", {})
                            if isinstance(
                                artifacts.result.get("bootstrap_confidence_intervals", {}),
                                dict,
                            )
                            else {}
                        ),
                        slice_shadow_report=(
                            artifacts.result.get("slice_shadow_metrics", {})
                            if isinstance(
                                artifacts.result.get("slice_shadow_metrics", {}),
                                dict,
                            )
                            else {}
                        ),
                    )
                    artifacts.result["baseline_comparison"] = dict(
                        baseline_artifacts.baseline_comparison
                    )
                    if baseline_artifacts.calibration:
                        artifacts.result["calibration"] = dict(
                            baseline_artifacts.calibration
                        )
                    artifacts.result["thresholds"] = dict(baseline_artifacts.thresholds)
                    thresholds = artifacts.result.get("thresholds", {})
                    calibration = artifacts.result.get("calibration", {})
                    baseline_comparison = artifacts.result.get("baseline_comparison", {})

            calibration_baseline_raw = thresholds.get("calibration_baseline")
            calibration_baseline_name = (
                str(calibration_baseline_raw)
                if calibration_baseline_raw not in (None, "", "none")
                else None
            )
            cipher = artifacts.working.get("cipher", None)
            if cipher is not None:
                lesion = compute_lesion_artifacts(
                    run_config=artifacts.run_config,
                    threat_model_level=artifacts.threat_model_level,
                    cipher=cipher,
                    registered_projections=list(
                        artifacts.working.get("registered_projections", [])
                    ),
                    state_indices=[
                        int(x) for x in artifacts.working.get("state_indices", [])
                    ],
                    edge_counts_total=dict(artifacts.working.get("edge_counts_total", {})),
                    region_agg_total=dict(artifacts.working.get("region_agg_total", {})),
                    ys_all=[
                        [int(v) for v in ys]
                        for ys in artifacts.working.get("ys_all", [])
                        if isinstance(ys, list)
                    ],
                    max_abs_quotient_per_trace=[
                        float(v)
                        for v in artifacts.working.get(
                            "max_abs_quotient_per_trace",
                            [],
                        )
                    ],
                    snapshot_count_per_trace=[
                        int(v)
                        for v in artifacts.working.get("snapshot_count_per_trace", [])
                    ],
                    omega_core_size=int(artifacts.working.get("omega_core_size", 0)),
                    bootstrap_confidence_intervals=(
                        artifacts.result.get("bootstrap_confidence_intervals", {})
                        if isinstance(
                            artifacts.result.get("bootstrap_confidence_intervals", {}),
                            dict,
                        )
                        else {}
                    ),
                    structure_height_pbox=(
                        artifacts.result.get("structure_height_pbox", {})
                        if isinstance(
                            artifacts.result.get("structure_height_pbox", {}),
                            dict,
                        )
                        else None
                    ),
                    thresholds=(thresholds if isinstance(thresholds, dict) else {}),
                    calibration=(calibration if isinstance(calibration, dict) else {}),
                    baseline_out=(
                        baseline_comparison
                        if isinstance(baseline_comparison, dict)
                        else {}
                    ),
                    calibration_baseline_name=calibration_baseline_name,
                )
                artifacts.result["lesions"] = list(lesion.lesions)
                if lesion.binary_degenerate:
                    artifacts.result["binary_degenerate"] = dict(lesion.binary_degenerate)
                if lesion.tm2_focused_probes:
                    artifacts.result["threat_model_2_focused_probes"] = dict(
                        lesion.tm2_focused_probes
                    )
                if lesion.tm2_witnesses:
                    artifacts.result["threat_model_2_witnesses"] = list(
                        lesion.tm2_witnesses
                    )
                if lesion.tm2_evidence_objects and isinstance(
                    artifacts.result.get("evidence_objects"),
                    list,
                ):
                    artifacts.result["evidence_objects"].extend(
                        lesion.tm2_evidence_objects
                    )
                if lesion.tm2_witnesses and isinstance(
                    artifacts.result.get("witnesses"),
                    list,
                ):
                    artifacts.result["witnesses"].extend(lesion.tm2_witnesses)

    if artifacts.threat_model_level == ThreatModelLevel.threat_model_1_black_box:
        artifacts.result["lesions"] = []

    lesions = artifacts.result.get("lesions", [])
    tm2 = artifacts.result.get("threat_model_2_focused_probes", {})
    tm2_witnesses = artifacts.result.get("threat_model_2_witnesses", [])
    binary_degenerate = artifacts.result.get("binary_degenerate", {})
    artifacts.lesion = LesionArtifacts(
        lesions=([x for x in lesions if isinstance(x, dict)] if isinstance(lesions, list) else []),
        tm2_focused_probes=(tm2 if isinstance(tm2, dict) else {}),
        tm2_witnesses=(
            [x for x in tm2_witnesses if isinstance(x, dict)]
            if isinstance(tm2_witnesses, list)
            else []
        ),
        tm2_evidence_objects=[],
        binary_degenerate=(
            binary_degenerate if isinstance(binary_degenerate, dict) else {}
        ),
    )
    return artifacts


__all__ = ["compute_lesion_artifacts", "attach_lesions"]
