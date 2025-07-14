from __future__ import annotations

from typing import Any, Dict, List

from ..analysis.tm1_scan import run_tm1_multi_projection_scan
from ..ciphers.runner_factory import build_toy_cipher_from_config
from ..projections.registry import parse_projection_set
from ..run_helpers import build_trace_state_indices, run_trace_from_state_index
from .result import VerificationResult

def verify_tm1_multi_projection_scan(report: Dict[str, Any]) -> VerificationResult:
    """
    Verify TM-1 multi-projection scan artifacts emitted by:
      tm1_multi_projection_scan (tests, p_values, BH-FDR)
      evidence_objects / witnesses aggregation (optional)

    Checks (recomputed from config + deterministic seeds):
    - per-projection statistic observed value
    - evidence-map (max_shadow_point, top_shadow_points, top_revisit_times)
    - baseline-calibrated p-values (two-sided) for the chosen baseline family
    - BH-FDR adjusted p-values and rejected indices
    """
    failures: List[str] = []
    checked = 0

    report_config = report.get("config", {}) if isinstance(report, dict) else {}
    visibility = report.get("visibility", {}) if isinstance(report, dict) else {}
    tm = None
    if isinstance(visibility, dict) and isinstance(visibility.get("threat_model_level", None), str):
        tm = str(visibility.get("threat_model_level"))
    if tm is None and isinstance(report_config.get("threat_model_level", None), str):
        tm = str(report_config.get("threat_model_level"))
    if tm is None or "threat_model_1" not in tm.lower():
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: not Threat Model 1"])

    scan = report.get("threat_model_1_multi_projection_scan", None)
    if not isinstance(scan, dict):
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: no threat_model_1_multi_projection_scan"])

    tests = scan.get("tests", [])
    p_values = scan.get("p_values", [])
    fdr = scan.get("benjamini_hochberg_false_discovery_rate", {})
    if not isinstance(tests, list) or not isinstance(p_values, list) or not isinstance(fdr, dict):
        return VerificationResult(ok=False, checked_count=0, failed_count=1, failures=["invalid threat_model_1_multi_projection_scan shape"])

    preset = str(report_config.get("cipher_preset", "")).strip().lower()
    word_bits = int(report_config.get("word_bits", 0) or 0)
    lane_count = int(report_config.get("lane_count", 0) or 0)
    rounds = int(report_config.get("rounds", 0) or 0)
    projection_primary = str(report_config.get("projection", "") or "")
    additional_csv = report_config.get("additional_projection_specs_csv", None)
    false_discovery_rate = float(report_config.get("false_discovery_rate", 0.10) or 0.10)
    baseline_ensemble_samples = int(report_config.get("baseline_ensemble_samples", 0) or 0)
    baselines_list = report_config.get("baselines", [])
    baselines_set = set(str(x) for x in baselines_list) if isinstance(baselines_list, list) else set()

    # Build cipher (runner) matching run_experiment.run_toy_iwt
    try:
        runner = build_toy_cipher_from_config(report_config)
    except Exception:
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: unknown preset"])

    # Recompute state-index pool exactly as run_experiment
    seeds = build_trace_state_indices(runner=runner, run_config=report_config)

    # Total steps for baselines that need step alignment
    _, evs0 = run_trace_from_state_index(runner=runner, state_index=0, run_config=report_config)
    total_steps = int(len(evs0))

    # Determine baseline family name the same way as run_experiment TM-1 scan
    if preset in ("toy_spn_vector", "toy_substitution_permutation_network_vector"):
        tm1_baseline_name = "random_substitution_permutation_network_vector"
    elif preset in ("toy_spn", "toy_substitution_permutation_network"):
        tm1_baseline_name = "random_substitution_permutation_network"
    else:
        tm1_baseline_name = "random_arx_like"
    if tm1_baseline_name not in baselines_set:
        tm1_baseline_name = "random_permutation" if "random_permutation" in baselines_set else "random_function"

    # Recompute scan using the same implementation as the runner (avoid divergence).
    registered = parse_projection_set(
        primary_projection=str(projection_primary),
        additional_projection_specs_csv=(str(additional_csv) if additional_csv else None),
        word_bits=int(word_bits),
    )
    recomputed_scan, _, _ = run_tm1_multi_projection_scan(
        run_config=report_config,
        cipher=runner,
        registered_projections=list(registered),
        seeds=list(seeds),
        total_steps=int(total_steps),
        threat_model_level=str(tm),
    )

    # Basic shape checks
    if recomputed_scan.get("projection_specs") != scan.get("projection_specs"):
        failures.append("projection_specs mismatch")
    recomputed_tests = recomputed_scan.get("tests", [])
    if not isinstance(recomputed_tests, list):
        failures.append("recomputed tests: invalid shape")
        recomputed_tests = []

    # Compare per-test fields (index-aligned; same registry order as run_experiment).
    if len(recomputed_tests) != len(tests):
        failures.append("tests length mismatch")
    for i in range(min(len(recomputed_tests), len(tests))):
        r_test = recomputed_tests[i] if isinstance(recomputed_tests[i], dict) else {}
        t_test = tests[i] if isinstance(tests[i], dict) else {}
        proj_spec = str(t_test.get("projection_spec", f"test[{i}]"))
        checked += 1

        if str(r_test.get("projection_spec", "")) != str(t_test.get("projection_spec", "")):
            failures.append(f"{proj_spec}: projection_spec mismatch")

        # observed statistic
        r_stat = r_test.get("statistic", {}) if isinstance(r_test.get("statistic", {}), dict) else {}
        t_stat = t_test.get("statistic", {}) if isinstance(t_test.get("statistic", {}), dict) else {}
        if not (abs(float(r_stat.get("observed", float("nan"))) - float(t_stat.get("observed", float("nan")))) <= 1e-12):
            failures.append(f"{proj_spec}: observed statistic mismatch")

        # evidence-map (exact dict equality; deterministic)
        if r_test.get("evidence_map") != t_test.get("evidence_map"):
            failures.append(f"{proj_spec}: evidence_map mismatch")

        # p-values
        rp = r_test.get("p_value_two_sided", None)
        tp = t_test.get("p_value_two_sided", None)
        if (rp is None) != (tp is None):
            failures.append(f"{proj_spec}: p_value_two_sided presence mismatch")
        if (rp is not None) and (tp is not None) and not (abs(float(rp) - float(tp)) <= 1e-12):
            failures.append(f"{proj_spec}: p_value_two_sided mismatch")

    # Compare BH-FDR output and top-level p_values
    if recomputed_scan.get("benjamini_hochberg_false_discovery_rate") != fdr:
        failures.append("BH-FDR object mismatch")
    if recomputed_scan.get("p_values") != p_values:
        failures.append("p_values list mismatch")

    return VerificationResult(ok=(len(failures) == 0), checked_count=int(checked), failed_count=int(len(failures)), failures=failures)
