from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .baseline_models import (
    RandomARXLikeBaseline,
    RandomFunctionBaseline,
    RandomPermutationBaseline,
    RandomSubstitutionPermutationNetworkBaseline,
    RandomSubstitutionPermutationNetworkVectorBaseline,
)
from ..evidence.objects import EvidenceObject, WitnessObject
from .multiple_comparisons import benjamini_hochberg_false_discovery_rate_control
from ..metrics.observation_metrics import compute_observation_side_metrics
from ..evidence.map_utils import (
    peak_slice_multiplicity_point,
    top_revisit_times,
    top_slice_multiplicity_points,
)
from ..utils.stats import (
    empirical_p_ge,
    empirical_p_le,
    empirical_quantile_pos,
    mean,
    stddev,
    two_sided_from_one_sided,
)
from ..run_helpers import run_trace_from_state_index


def _run_config_get(run_config: Any, key: str, default: Any = None) -> Any:
    if isinstance(run_config, dict):
        return run_config.get(key, default)
    return getattr(run_config, key, default)


def run_tm1_multi_projection_scan(
    *,
    run_config: Any,
    cipher: Any,
    registered_projections: List[Tuple[str, Any]],
    seeds: List[int],
    total_steps: int,
    threat_model_level: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    TM-1 multi-projection scan (observation-only):
    - statistic: mean observation_self_intersection_rate over a deterministic seed pool
    - baseline calibration: empirical two-sided p-values vs chosen baseline family
    - multiple comparisons: BH-FDR across projections
    - outputs: scan dict + 6.E evidence objects + witness objects
    """
    seed_pool = list(int(s) for s in seeds[: min(len(seeds), 64)])

    def collect_projected_traces(*, runner: Any, projection_function: Any) -> List[List[int]]:
        observations_by_trace: List[List[int]] = []
        for state_index in seed_pool:
            states_tmp, _ = run_trace_from_state_index(
                runner=runner,
                state_index=int(state_index),
                run_config=run_config,
            )
            observations_by_trace.append([int(projection_function(st)) for st in states_tmp])
        return observations_by_trace

    def mean_observation_self_intersection_rate(*, observations_by_trace: List[List[int]]) -> float:
        per_trace: List[float] = []
        for obs in observations_by_trace:
            per_trace.append(float(compute_observation_side_metrics(observations=obs).observation_self_intersection_rate))
        return mean(per_trace)

    preset = str(_run_config_get(run_config, "cipher_preset", "")).strip().lower()
    baselines_list = _run_config_get(run_config, "baselines", ())
    if isinstance(baselines_list, list):
        baselines_set = set(str(x) for x in baselines_list)
    elif isinstance(baselines_list, tuple):
        baselines_set = set(str(x) for x in baselines_list)
    else:
        baselines_set = set()

    if preset in ("toy_spn_vector", "toy_substitution_permutation_network_vector"):
        baseline_family_name = "random_substitution_permutation_network_vector"
    elif preset in ("toy_spn", "toy_substitution_permutation_network"):
        baseline_family_name = "random_substitution_permutation_network"
    else:
        baseline_family_name = "random_arx_like"
    if baseline_family_name not in baselines_set:
        baseline_family_name = "random_permutation" if "random_permutation" in baselines_set else "random_function"

    baseline_ensemble_samples = int(max(0, int(_run_config_get(run_config, "baseline_ensemble_samples", 0) or 0)))

    def make_tm1_baseline(sample_index: int) -> Any:
        seed0 = int(_run_config_get(run_config, "seed", 0) or 0) ^ 0x51A1_7E01
        seed = int(seed0) + int(sample_index)
        word_bits = int(_run_config_get(run_config, "word_bits", 0) or 0)
        rounds = int(_run_config_get(run_config, "rounds", 0) or 0)
        lane_count = int(_run_config_get(run_config, "lane_count", 0) or 0)
        if baseline_family_name == "random_arx_like":
            return RandomARXLikeBaseline(
                domain=cipher.domain,
                rounds=int(rounds),
                seed=int(seed),
                word_bits=int(word_bits),
                rot_mode=str(_run_config_get(run_config, "rot_mode", "bits")),
                rot_dir=str(_run_config_get(run_config, "rotation_direction", "l")),
                cross_domain_q=_run_config_get(run_config, "cross_domain_modulus", None),
                cross_every_rounds=int(_run_config_get(run_config, "cross_every_rounds", 4) or 4),
            )
        if baseline_family_name == "random_substitution_permutation_network":
            return RandomSubstitutionPermutationNetworkBaseline(
                domain=cipher.domain,
                rounds=int(rounds),
                seed=int(seed),
            )
        if baseline_family_name == "random_substitution_permutation_network_vector":
            return RandomSubstitutionPermutationNetworkVectorBaseline(
                domain=cipher.domain,
                rounds=int(rounds),
                lane_count=int(lane_count),
                seed=int(seed),
            )
        if baseline_family_name == "random_permutation":
            return RandomPermutationBaseline(domain=cipher.domain, steps=int(total_steps), seed=int(seed))
        return RandomFunctionBaseline(domain=cipher.domain, steps=int(total_steps), seed=int(seed))

    tests: List[Dict[str, Any]] = []
    projection_specs: List[str] = []
    p_values: List[float | None] = []
    for projection_spec, projection_function in registered_projections:
        observed_observations_by_trace = collect_projected_traces(runner=cipher, projection_function=projection_function)
        observed_stat = float(mean_observation_self_intersection_rate(observations_by_trace=observed_observations_by_trace))
        baseline_stats: List[float] = []
        for ensemble_index in range(int(baseline_ensemble_samples)):
            base = make_tm1_baseline(ensemble_index)
            base_observations_by_trace = collect_projected_traces(runner=base, projection_function=projection_function)
            baseline_stats.append(float(mean_observation_self_intersection_rate(observations_by_trace=base_observations_by_trace)))
        p_ge = empirical_p_ge(baseline_stats, float(observed_stat)) if baseline_stats else float("nan")
        p_le = empirical_p_le(baseline_stats, float(observed_stat)) if baseline_stats else float("nan")
        p_two_sided = two_sided_from_one_sided(float(p_le), float(p_ge)) if baseline_stats else float("nan")
        p_value = p_two_sided if (p_two_sided == p_two_sided) else None
        qpos = empirical_quantile_pos(baseline_stats, float(observed_stat)) if baseline_stats else None
        projection_specs.append(str(projection_spec))
        p_values.append(p_value)
        evidence_map = {
            "max_shadow_point": peak_slice_multiplicity_point(observed_observations_by_trace),
            "top_shadow_points": top_slice_multiplicity_points(observations_by_trace=observed_observations_by_trace, top_k=8),
            "top_revisit_times": top_revisit_times(observations_by_trace=observed_observations_by_trace, top_k=8),
            "note": "Evidence-map is observation-only (TM-1) and can be used to prioritize time windows / (t,y) hot spots for follow-up.",
        }
        tests.append(
            {
                "projection_spec": str(projection_spec),
                "statistic": {
                    "name": "mean_observation_self_intersection_rate",
                    "observed": float(observed_stat),
                    "baseline_mean": float(mean(baseline_stats)) if baseline_stats else None,
                    "baseline_std": float(stddev(baseline_stats)) if baseline_stats else None,
                    "trace_seed_count": int(len(seed_pool)),
                },
                "p_value_two_sided": p_value,
                "p_value_ge": None if (p_ge != p_ge) else float(p_ge),
                "p_value_le": None if (p_le != p_le) else float(p_le),
                "quantile_pos": qpos,
                "baseline_family": str(baseline_family_name),
                "baseline_ensemble_samples": int(baseline_ensemble_samples),
                "baseline_stats_samples_head": list(float(x) for x in baseline_stats[: min(64, len(baseline_stats))]),
                "evidence_map": evidence_map,
            }
        )

    fdr_result = benjamini_hochberg_false_discovery_rate_control(
        p_values=list(p_values),
        false_discovery_rate=float(_run_config_get(run_config, "false_discovery_rate", 0.10) or 0.10),
    ).as_dict()
    adjusted_p_values = fdr_result.get("adjusted_p_values", [])
    rejected_indices = set(int(i) for i in fdr_result.get("rejected_indices", [])) if isinstance(fdr_result, dict) else set()

    scan_evidence_objects: List[Dict[str, Any]] = []
    scan_witnesses: List[Dict[str, Any]] = []
    for idx, test in enumerate(tests):
        q_value = adjusted_p_values[idx] if isinstance(adjusted_p_values, list) and idx < len(adjusted_p_values) else None
        proj_spec = str(test.get("projection_spec", f"proj#{idx}"))
        p_two = test.get("p_value_two_sided", None)
        ev_map = test.get("evidence_map", {}) if isinstance(test.get("evidence_map", {}), dict) else {}
        stat = test.get("statistic", {}) if isinstance(test.get("statistic", {}), dict) else {}
        witness = WitnessObject(
            config={
                "threat_model_level": str(threat_model_level),
                "projection_spec": proj_spec,
                "baseline_family": str(test.get("baseline_family", "")),
                "baseline_ensemble_samples": int(test.get("baseline_ensemble_samples", 0) or 0),
                "false_discovery_rate": float(_run_config_get(run_config, "false_discovery_rate", 0.10) or 0.10),
                "benjamini_hochberg_adjusted_p_value": q_value,
                "benjamini_hochberg_rejected": bool(idx in rejected_indices),
            },
            E={
                "statistic_name": str(stat.get("name", "mean_observation_self_intersection_rate")),
                "observed": stat.get("observed"),
                "baseline_mean": stat.get("baseline_mean"),
                "baseline_std": stat.get("baseline_std"),
                "p_value_two_sided": p_two,
                "p_value_ge": test.get("p_value_ge"),
                "p_value_le": test.get("p_value_le"),
            },
            Z={"top_shadow_points": ev_map.get("top_shadow_points", []), "top_revisit_times": ev_map.get("top_revisit_times", [])},
            evidence_map=ev_map,
        ).as_dict()
        scan_witnesses.append(witness)
        scan_evidence_objects.append(
            EvidenceObject(
                identifier=f"threat_model_1_multi_projection_scan::{proj_spec}",
                summary="TM-1 multi-projection calibrated evidence object (baseline-calibrated p-value + BH-FDR + evidence-map).",
                value={"projection_spec": proj_spec, "statistic": stat, "p_value_two_sided": p_two, "benjamini_hochberg_adjusted_p_value": q_value, "benjamini_hochberg_rejected": bool(idx in rejected_indices)},
                p_value=(float(p_two) if (p_two is not None) else None),
                witness=witness,
                metadata={
                    "baseline_family": str(test.get("baseline_family", "")),
                    "baseline_ensemble_samples": int(test.get("baseline_ensemble_samples", 0) or 0),
                    "false_discovery_rate": float(_run_config_get(run_config, "false_discovery_rate", 0.10) or 0.10),
                },
            ).as_dict()
        )

    scan = {
        "projection_specs": list(projection_specs),
        "p_values": list(p_values),
        "benjamini_hochberg_false_discovery_rate": fdr_result,
        "tests": tests,
        "calibration": {
            "baseline_family": str(baseline_family_name),
            "baseline_ensemble_samples": int(baseline_ensemble_samples),
            "trace_seed_count": int(len(seed_pool)),
            "note": "TM-1 p-values are calibrated against the chosen baseline family; BH-FDR is applied across projections.",
        },
    }
    return scan, scan_evidence_objects, scan_witnesses

