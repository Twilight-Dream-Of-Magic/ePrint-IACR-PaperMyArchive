from __future__ import annotations

from typing import Any, Dict, List

from ..analysis.baseline_factory import build_baseline_runner, select_calibration_baseline
from ..evidence.map_utils import peak_slice_multiplicity_point
from ..metrics.winding_metrics import (
    compute_atomic_metrics,
    compute_mechanism_side_metrics,
    compute_pattern_side_metrics,
    compute_projection_metrics,
    compute_slice_shadow_metrics,
)
from ..run_helpers import run_trace_from_state_index, state_space_coverage_ratio
from ..utils.event_summaries import aggregate_region_counts, count_op_families, op_family_frequencies
from ..utils.stats import quantile as _quantile
from .block_core import observed_space_size_from_projection
from ..analysis.threat_model import ThreatModelLevel
from .config import RunConfig
from .types import BaselineArtifacts, RunArtifacts


def compute_baseline_artifacts(
    *,
    run_config: RunConfig,
    cipher: Any,
    state_indices: List[int],
    total_steps: int,
    proj: Any,
    omega_core_size: int,
    bootstrap_confidence_intervals: Dict[str, Any],
    slice_shadow_report: Dict[str, Any],
) -> BaselineArtifacts:
    baseline_out: Dict[str, Any] = {}
    calibration_baseline_name = select_calibration_baseline(run_config.baselines)
    is_binary = bool(cipher.domain.is_binary)
    observed_space_size = observed_space_size_from_projection(run_config)
    thresholds: Dict[str, Any] = {
        "alpha": run_config.alpha,
        "baseline_ensemble_samples": run_config.baseline_ensemble_samples,
        "calibration_baseline": calibration_baseline_name or "none",
        "binary_degenerate_q2": is_binary,
    }
    calibration: Dict[str, Any] = {}

    for baseline_name in run_config.baselines:
        base = build_baseline_runner(
            baseline_name=str(baseline_name),
            domain=cipher.domain,
            run_config=run_config,
            steps=int(total_steps),
        )

        b_wrap_rates: List[float] = []
        b_sl_rates: List[float] = []
        b_nsl_rates: List[float] = []
        b_self_intersection_rates: List[float] = []
        b_collision_rates: List[float] = []
        b_occupancy_rates: List[float] = []
        b_Ys_all: List[List[int]] = []
        for state_index in state_indices:
            states, events = run_trace_from_state_index(
                runner=base,
                state_index=int(state_index),
                run_config=run_config,
            )
            ys = [proj(st) for st in states]
            projection_metrics_b = compute_projection_metrics(ys=ys, observed_space_size=None)
            mechanism_side_b = compute_mechanism_side_metrics(states=states, events=events)
            pattern_side_b = compute_pattern_side_metrics(states=states, events=events, project=proj, observed_space_size=None)
            b_Ys_all.append(ys)
            b_wrap_rates.append(float(mechanism_side_b["wrap_event_rate"]))
            b_sl_rates.append(float(pattern_side_b["self_loop"]["trivial_self_loop_event_rate"]))
            b_nsl_rates.append(float(pattern_side_b["self_loop"]["nontrivial_self_loop_event_rate"]))
            b_collision_rates.append(projection_metrics_b.as_dict()["collision_rate"])
            b_self_intersection_rates.append(float(pattern_side_b["self_intersection_rate"]))
            if observed_space_size:
                b_occupancy_rates.append(
                    projection_metrics_b.unique_nodes / float(observed_space_size)
                )

        mu_wrap = sum(b_wrap_rates) / len(b_wrap_rates)
        var_wrap = sum((x - mu_wrap) ** 2 for x in b_wrap_rates) / max(1, (len(b_wrap_rates) - 1))
        sigma_wrap = var_wrap**0.5

        mu_col = sum(b_collision_rates) / len(b_collision_rates)
        var_col = sum((x - mu_col) ** 2 for x in b_collision_rates) / max(1, (len(b_collision_rates) - 1))
        sigma_col = var_col**0.5

        mu_sl = sum(b_sl_rates) / len(b_sl_rates)
        var_sl = sum((x - mu_sl) ** 2 for x in b_sl_rates) / max(1, (len(b_sl_rates) - 1))
        sigma_sl = var_sl**0.5

        mu_nsl = sum(b_nsl_rates) / len(b_nsl_rates)
        var_nsl = sum((x - mu_nsl) ** 2 for x in b_nsl_rates) / max(1, (len(b_nsl_rates) - 1))
        sigma_nsl = var_nsl**0.5

        mu_si = sum(b_self_intersection_rates) / len(b_self_intersection_rates)
        var_si = sum((x - mu_si) ** 2 for x in b_self_intersection_rates) / max(1, (len(b_self_intersection_rates) - 1))
        sigma_si = var_si**0.5

        if b_occupancy_rates:
            mu_occ = sum(b_occupancy_rates) / len(b_occupancy_rates)
            var_occ = sum((x - mu_occ) ** 2 for x in b_occupancy_rates) / max(1, (len(b_occupancy_rates) - 1))
            sigma_occ = var_occ**0.5
        else:
            mu_occ, sigma_occ = float("nan"), float("nan")

        slice_shadow_baseline = compute_slice_shadow_metrics(b_Ys_all).as_dict()
        mu_pair = float(slice_shadow_baseline.get("avg_pair_collision_prob", float("nan")))

        baseline_out[baseline_name] = {
            "wrap_event_rate": {
                "mean": mu_wrap,
                "std": sigma_wrap,
                "z_score": (float(bootstrap_confidence_intervals["wrap_event_rate"]["mean"]) - float(mu_wrap)) / float(sigma_wrap) if sigma_wrap > 1e-12 else float("nan"),
                "z_note": "undefined (baseline std=0)" if sigma_wrap <= 1e-12 else None,
                "delta_vs_mean": float(bootstrap_confidence_intervals["wrap_event_rate"]["mean"]) - float(mu_wrap),
            },
            "trivial_self_loop_rate": {
                "mean": mu_sl,
                "std": sigma_sl,
                "z_score": (float(bootstrap_confidence_intervals["trivial_self_loop_rate"]["mean"]) - float(mu_sl)) / float(sigma_sl) if sigma_sl > 1e-12 else float("nan"),
                "z_note": "undefined (baseline std=0)" if sigma_sl <= 1e-12 else None,
                "delta_vs_mean": float(bootstrap_confidence_intervals["trivial_self_loop_rate"]["mean"]) - float(mu_sl),
            },
            "nontrivial_self_loop_rate": {
                "mean": mu_nsl,
                "std": sigma_nsl,
                "z_score": (float(bootstrap_confidence_intervals["nontrivial_self_loop_rate"]["mean"]) - float(mu_nsl)) / float(sigma_nsl) if sigma_nsl > 1e-12 else float("nan"),
                "z_note": "undefined (baseline std=0)" if sigma_nsl <= 1e-12 else None,
                "delta_vs_mean": float(bootstrap_confidence_intervals["nontrivial_self_loop_rate"]["mean"]) - float(mu_nsl),
            },
            "self_intersection_rate": {
                "mean": mu_si,
                "std": sigma_si,
                "z_score": (float(bootstrap_confidence_intervals["self_intersection_rate"]["mean"]) - float(mu_si)) / float(sigma_si) if sigma_si > 1e-12 else float("nan"),
                "z_note": "undefined (baseline std=0)" if sigma_si <= 1e-12 else None,
                "delta_vs_mean": float(bootstrap_confidence_intervals["self_intersection_rate"]["mean"]) - float(mu_si),
            },
            "projection_collision_rate": {
                "mean": mu_col,
                "std": sigma_col,
                "z_score": (float(bootstrap_confidence_intervals["projection_collision_rate"]["mean"]) - float(mu_col)) / float(sigma_col) if sigma_col > 1e-12 else float("nan"),
                "z_note": "undefined (baseline std=0)" if sigma_col <= 1e-12 else None,
                "delta_vs_mean": float(bootstrap_confidence_intervals["projection_collision_rate"]["mean"]) - float(mu_col),
            },
            "occupancy_rate": {
                "mean": mu_occ,
                "std": sigma_occ,
                "z_score": (float(bootstrap_confidence_intervals["occupancy_rate"]["mean"]) - float(mu_occ)) / float(sigma_occ) if (mu_occ == mu_occ and sigma_occ > 1e-12) else None,
                "z_note": "undefined (baseline std=0)" if (sigma_occ <= 1e-12) else None,
                "delta_vs_mean": (float(bootstrap_confidence_intervals["occupancy_rate"]["mean"]) - float(mu_occ)) if mu_occ == mu_occ else None,
            },
            "slice_shadow": {
                "avg_pair_collision_prob": {
                    "value": float(slice_shadow_report.get("avg_pair_collision_prob", float("nan"))),
                    "baseline_mean": mu_pair,
                }
            },
        }

    if calibration_baseline_name and (run_config.baseline_ensemble_samples > 0):
        edge_freqs: List[Dict[str, float]] = []
        stats_P1_max_abs_diff: List[float] = []
        stats_P2_max_m: List[float] = []
        stats_P3_wrap_max: List[float] = []
        stats_P3_nsl_max: List[float] = []
        stats_P4_cov: List[float] = []
        stats_P5_sl: List[float] = []
        stats_P5_nsl: List[float] = []
        stats_P6_quotient_max: List[float] = []
        stats_P6_snapshot_max: List[int] = []
        stats_P7_inversion_norm: List[float] = []

        for ensemble_index in range(run_config.baseline_ensemble_samples):
            base = build_baseline_runner(
                baseline_name=str(calibration_baseline_name),
                domain=cipher.domain,
                run_config=run_config,
                steps=int(total_steps),
                ensemble_index=int(ensemble_index),
            )

            edge_counts_b: Dict[str, int] = {}
            region_agg_b: Dict[str, Dict[str, float]] = {}
            Ys_b: List[List[int]] = []
            sls: List[float] = []
            nsls: List[float] = []
            covs: List[float] = []

            for state_index in state_indices:
                states_b, events_b = run_trace_from_state_index(
                    runner=base,
                    state_index=int(state_index),
                    run_config=run_config,
                )
                atomic_metrics_baseline = compute_atomic_metrics(states=states_b, events=events_b, project=proj)
                ys_b = [proj(st) for st in states_b]
                Ys_b.append(ys_b)
                sls.append(atomic_metrics_baseline.as_dict()["trivial_self_loop_rate"])
                nsls.append(atomic_metrics_baseline.as_dict()["nontrivial_self_loop_rate"])
                covs.append(state_space_coverage_ratio(states_b, omega_core_size))

                op_family_counts_b = count_op_families(events_b)
                for op_type, count in op_family_counts_b.items():
                    edge_counts_b[op_type] = edge_counts_b.get(op_type, 0) + count

                rag_b = aggregate_region_counts(states=states_b, events=list(events_b), project=proj)
                for rid, d in rag_b.items():
                    if rid not in region_agg_b:
                        region_agg_b[rid] = {"step_count": 0.0, "wrap_count": 0.0, "nontrivial_self_loop_count": 0.0}
                    region_agg_b[rid]["step_count"] += float(d["step_count"])
                    region_agg_b[rid]["wrap_count"] += float(d["wrap_count"])
                    region_agg_b[rid]["nontrivial_self_loop_count"] += float(d["nontrivial_self_loop_count"])

                max_abs_q_b = max(abs(int(st.information_height.cross_domain_reencoding_quotient)) for st in states_b) if states_b else 0
                snap_b = len(states_b[-1].information_height.building_exit_snapshots) if states_b else 0
                stats_P6_quotient_max.append(float(max_abs_q_b))
                stats_P6_snapshot_max.append(int(snap_b))

            if calibration_baseline_name in ("random_substitution_permutation_network", "random_substitution_permutation_network_vector"):
                inv_n = base.get_pbox_inversion_norm()
                if inv_n == inv_n:
                    stats_P7_inversion_norm.append(float(inv_n))

            edge_freqs.append(op_family_frequencies(edge_counts_b))
            stats_P2_max_m.append(float(peak_slice_multiplicity_point(Ys_b)["max_multiplicity"]))

            wrap_max = 0.0
            nsl_max = 0.0
            for _, agg in region_agg_b.items():
                steps_r = float(agg["step_count"])
                if steps_r <= 0:
                    continue
                wrap_max = max(wrap_max, float(agg["wrap_count"]) / steps_r)
                nsl_max = max(nsl_max, float(agg["nontrivial_self_loop_count"]) / steps_r)
            stats_P3_wrap_max.append(float(wrap_max))
            stats_P3_nsl_max.append(float(nsl_max))

            stats_P4_cov.append(float(sum(covs) / len(covs)) if covs else float("nan"))
            stats_P5_sl.append(float(sum(sls) / len(sls)) if sls else float("nan"))
            stats_P5_nsl.append(float(sum(nsls) / len(nsls)) if nsls else float("nan"))

        all_types = set().union(*[op_family_freqs.keys() for op_family_freqs in edge_freqs]) if edge_freqs else set()
        baseline_mean_op_family_freq: Dict[str, float] = {}
        for op_family_type in all_types:
            baseline_mean_op_family_freq[op_family_type] = sum(op_family_freqs.get(op_family_type, 0.0) for op_family_freqs in edge_freqs) / max(1, len(edge_freqs))

        for op_family_freqs in edge_freqs:
            if not all_types:
                stats_P1_max_abs_diff.append(0.0)
            else:
                stats_P1_max_abs_diff.append(
                    float(max(abs(op_family_freqs.get(op_family_type, 0.0) - baseline_mean_op_family_freq.get(op_family_type, 0.0)) for op_family_type in all_types))
                )

        calibration = {
            "baseline": calibration_baseline_name,
            "S1_max_abs_freq_diff": list(stats_P1_max_abs_diff),
            "S2_max_m": list(stats_P2_max_m),
            "S3_wrap_density_max": list(stats_P3_wrap_max),
            "S3_nsl_density_max": list(stats_P3_nsl_max),
            "S4_coverage": list(stats_P4_cov),
            "S5_SL": list(stats_P5_sl),
            "S5_NSL": list(stats_P5_nsl),
            "S6_quotient_max": list(stats_P6_quotient_max),
            "S6_snapshot_max": list(stats_P6_snapshot_max),
            "S7_inversion_norm": list(stats_P7_inversion_norm),
        }

        for arr in (
            stats_P1_max_abs_diff,
            stats_P2_max_m,
            stats_P3_wrap_max,
            stats_P3_nsl_max,
            stats_P4_cov,
            stats_P5_sl,
            stats_P5_nsl,
            stats_P6_quotient_max,
            stats_P6_snapshot_max,
            stats_P7_inversion_norm,
        ):
            arr.sort()

        thresholds["P1"] = {"threshold_max_abs_diff": _quantile(stats_P1_max_abs_diff, 1.0 - run_config.alpha), "baseline_mean_pf": baseline_mean_op_family_freq}
        thresholds["P2"] = {"threshold_max_mechanism_side": _quantile(stats_P2_max_m, 1.0 - run_config.alpha)}
        thresholds["P3"] = {
            "threshold_wrap_density_max": _quantile(stats_P3_wrap_max, 1.0 - run_config.alpha),
            "threshold_nsl_density_max": _quantile(stats_P3_nsl_max, 1.0 - run_config.alpha),
        }
        thresholds["P4"] = {"coverage_rate_lower_bound": _quantile(stats_P4_cov, run_config.alpha), "coverage_rate_upper_bound": _quantile(stats_P4_cov, 1.0 - run_config.alpha)}
        thresholds["P5"] = {
            "trivial_self_loop_rate_lower_bound": _quantile(stats_P5_sl, run_config.alpha),
            "trivial_self_loop_rate_upper_bound": _quantile(stats_P5_sl, 1.0 - run_config.alpha),
            "nontrivial_self_loop_rate_lower_bound": _quantile(stats_P5_nsl, run_config.alpha),
            "nontrivial_self_loop_rate_upper_bound": _quantile(stats_P5_nsl, 1.0 - run_config.alpha),
        }
        thresholds["P6"] = {
            "threshold_quotient_max": _quantile(stats_P6_quotient_max, 1.0 - run_config.alpha) if stats_P6_quotient_max else float("nan"),
            "threshold_snapshot_max": float(_quantile(stats_P6_snapshot_max, 1.0 - run_config.alpha)) if stats_P6_snapshot_max else float("nan"),
        }
        thresholds["P7"] = {
            "threshold_inversion_norm": _quantile(stats_P7_inversion_norm, 1.0 - run_config.alpha) if stats_P7_inversion_norm else float("nan"),
        }

    return BaselineArtifacts(
        baseline_comparison=baseline_out,
        calibration=calibration,
        thresholds=thresholds,
    )


def attach_baselines(artifacts: RunArtifacts) -> RunArtifacts:
    """
    Attach baseline/calibration artifacts.

    Computes baseline/calibration artifacts when missing, then normalizes
    typed slices for downstream stages.
    """
    baseline_comparison = artifacts.result.get("baseline_comparison", {})
    calibration = artifacts.result.get("calibration", {})
    thresholds = artifacts.result.get("thresholds", {})
    if (
        artifacts.threat_model_level != ThreatModelLevel.threat_model_1_black_box
        and (not isinstance(baseline_comparison, dict) or not baseline_comparison)
    ):
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
            computed = compute_baseline_artifacts(
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
                    if isinstance(artifacts.result.get("slice_shadow_metrics", {}), dict)
                    else {}
                ),
            )
            artifacts.result["baseline_comparison"] = dict(computed.baseline_comparison)
            if computed.calibration:
                artifacts.result["calibration"] = dict(computed.calibration)
            artifacts.result["thresholds"] = dict(computed.thresholds)
            baseline_comparison = artifacts.result.get("baseline_comparison", {})
            calibration = artifacts.result.get("calibration", {})
            thresholds = artifacts.result.get("thresholds", {})

    if artifacts.threat_model_level == ThreatModelLevel.threat_model_1_black_box:
        artifacts.result["baseline_comparison"] = {}
        baseline_comparison = {}
        calibration = {}
        thresholds = {}

    artifacts.baseline = BaselineArtifacts(
        baseline_comparison=(baseline_comparison if isinstance(baseline_comparison, dict) else {}),
        calibration=(calibration if isinstance(calibration, dict) else {}),
        thresholds=(thresholds if isinstance(thresholds, dict) else {}),
    )
    return artifacts


__all__ = ["compute_baseline_artifacts", "attach_baselines"]
