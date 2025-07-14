from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .result import VerificationResult

def verify_tm3_workflow(report: Dict[str, Any]) -> VerificationResult:
    """
    Verify TM-3 workflow reproducibility by re-running the deterministic TM-3 pipeline and comparing:
    - Stage B intervention plan (focus projections/windows/chosen inputs)
    - Stage C focused probe event digests (mechanism-aligned witness fingerprints)

    This intentionally does NOT treat TM-2 outputs as new screening signals; it only checks auditability.
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
    if tm is None or "threat_model_3" not in tm.lower():
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: not Threat Model 3"])

    tm3 = report.get("threat_model_3_workflow", None)
    if not isinstance(tm3, dict):
        return VerificationResult(ok=False, checked_count=0, failed_count=1, failures=["missing threat_model_3_workflow"])

    try:
        from ..run_experiment import RunConfig, run_tm3_workflow
    except Exception as e:
        return VerificationResult(ok=False, checked_count=0, failed_count=1, failures=[f"failed to import tm3 runner: {e!r}"])

    def build_run_config(config_dict: Dict[str, Any]) -> RunConfig:
        baselines_val = config_dict.get("baselines", ())
        if isinstance(baselines_val, list):
            baselines = tuple(str(x) for x in baselines_val)
        elif isinstance(baselines_val, tuple):
            baselines = tuple(str(x) for x in baselines_val)
        else:
            baselines = ()
        return RunConfig(
            cipher_preset=str(config_dict.get("cipher_preset", "toy_arx")),
            word_bits=int(config_dict.get("word_bits", 8) or 8),
            lane_count=int(config_dict.get("lane_count", 4) or 4),
            rounds=int(config_dict.get("rounds", 16) or 16),
            rotation_mode=str(config_dict.get("rotation_mode", "bits")),
            rotation_direction=str(config_dict.get("rotation_direction", "l")),
            trace_count=int(config_dict.get("trace_count", 200) or 200),
            seed=int(config_dict.get("seed", 0) or 0),
            projection=str(config_dict.get("projection", "lowbits:4")),
            cross_domain_modulus=(config_dict.get("cross_domain_modulus", None)),
            cross_every_rounds=int(config_dict.get("cross_every_rounds", 4) or 4),
            baselines=baselines,
            bootstrap_iters=int(config_dict.get("bootstrap_iters", 2000) or 2000),
            baseline_ensemble_samples=int(config_dict.get("baseline_ensemble_samples", 200) or 200),
            alpha=float(config_dict.get("alpha", 0.01) or 0.01),
            exhaustive=bool(config_dict.get("exhaustive", False)),
            max_exhaustive_modulus=int(config_dict.get("max_exhaustive_modulus", 4096) or 4096),
            max_exhaustive_state_count=int(config_dict.get("max_exhaustive_state_count", 65536) or 65536),
            max_empirical_trace_count=int(config_dict.get("max_empirical_trace_count", 4096) or 4096),
            threat_model_level="threat_model_3_intervention",
            additional_projection_specs_csv=(str(config_dict.get("additional_projection_specs_csv")) if config_dict.get("additional_projection_specs_csv", None) else None),
            false_discovery_rate=float(config_dict.get("false_discovery_rate", 0.10) or 0.10),
            reachability_target_indices_csv=(str(config_dict.get("reachability_target_indices_csv")) if config_dict.get("reachability_target_indices_csv", None) else None),
            threat_model_3_max_probes=int(config_dict.get("threat_model_3_max_probes", 8) or 8),
            threat_model_3_focus_topk=int(config_dict.get("threat_model_3_focus_topk", 4) or 4),
            threat_model_3_window_radius=int(config_dict.get("threat_model_3_window_radius", 2) or 2),
            threat_model_3_intervention_budget=int(config_dict.get("threat_model_3_intervention_budget", 64) or 64),
        )

    recomputed = run_tm3_workflow(run_config=build_run_config(report_config))
    tm3_re = recomputed.get("threat_model_3_workflow", None)
    if not isinstance(tm3_re, dict):
        return VerificationResult(ok=False, checked_count=0, failed_count=1, failures=["recomputed threat_model_3_workflow missing"])

    # Stage A scan comparison (key subset).
    stageA = tm3.get("stageA_threat_model_1_summary", None)
    stageA_re = tm3_re.get("stageA_threat_model_1_summary", None)
    if not isinstance(stageA, dict) or not isinstance(stageA_re, dict):
        failures.append("missing stageA_threat_model_1_summary")
    else:
        checked += 1
        scan = stageA.get("threat_model_1_multi_projection_scan", None)
        scan_re = stageA_re.get("threat_model_1_multi_projection_scan", None)
        if not isinstance(scan, dict) or not isinstance(scan_re, dict):
            failures.append("stageA threat_model_1_multi_projection_scan missing")
        else:
            for key in ("projection_specs", "p_values", "benjamini_hochberg_false_discovery_rate"):
                if scan.get(key) != scan_re.get(key):
                    failures.append(f"stageA threat_model_1_multi_projection_scan mismatch at key={key!r}")

    # Stage B plan comparison (key subset).
    plan = tm3.get("stageB_intervention_plan", None)
    plan_re = tm3_re.get("stageB_intervention_plan", None)
    if not isinstance(plan, dict) or not isinstance(plan_re, dict):
        failures.append("missing stageB_intervention_plan")
    else:
        checked += 1
        for key in ("focus_projection_specs", "focus_windows", "chosen_seed_values", "chosen_x0_indices"):
            if plan.get(key) != plan_re.get(key):
                failures.append(f"stageB_intervention_plan mismatch at key={key!r}")

    # Stage C witness digest comparison (multiset of (x0,window,digest)).
    def digest_triples(witnesses: Any) -> List[Tuple[int, str, str]]:
        out: List[Tuple[int, str, str]] = []
        if not isinstance(witnesses, list):
            return out
        for w in witnesses:
            if not isinstance(w, dict):
                continue
            cfgw = w.get("config", {})
            Ew = w.get("E", {})
            if not isinstance(cfgw, dict) or not isinstance(Ew, dict):
                continue
            initial_state_value = int(cfgw.get("initial_state_value", -1))
            window = cfgw.get("focus_window", None)
            digest = str(Ew.get("event_digest_sha256", ""))
            if window is None:
                continue
            out.append((initial_state_value, json.dumps(window, sort_keys=True), digest))
        out.sort()
        return out

    w1 = digest_triples(tm3.get("stageC_threat_model_2_witnesses", []))
    w2 = digest_triples(tm3_re.get("stageC_threat_model_2_witnesses", []))
    checked += 1
    if w1 != w2:
        failures.append("stageC_threat_model_2_witnesses digest triples mismatch")

    return VerificationResult(ok=(len(failures) == 0), checked_count=int(checked), failed_count=int(len(failures)), failures=failures)
