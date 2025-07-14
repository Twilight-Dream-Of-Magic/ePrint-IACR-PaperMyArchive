from __future__ import annotations

from typing import Any, Dict, List

from ..analysis.tm2_focused_probes import build_tm2_focus_plan_from_observations, run_tm2_focused_probes
from ..ciphers.runner_factory import build_toy_cipher_from_config
from ..projections.registry import parse_projection_set
from ..run_helpers import build_trace_state_indices
from .result import VerificationResult
from .stream_hash import STREAM_HASH_EXPERIMENT_TYPES

def verify_tm2_focused_probes(report: Dict[str, Any]) -> VerificationResult:
    """
    Verify TM-2 focused probe witnesses (standalone TM-2 mode).
    Recomputes the focus plan (windows/inputs) and the resulting event digests.
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
    if tm is None or "threat_model_2" not in tm.lower():
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: not Threat Model 2"])

    section = report.get("threat_model_2_focused_probes", None)
    if not isinstance(section, dict):
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: no threat_model_2_focused_probes"])
    reported_plan = section.get("plan", None)
    reported_witnesses = section.get("threat_model_2_witnesses", None)
    if not isinstance(reported_plan, dict) or not isinstance(reported_witnesses, list):
        return VerificationResult(ok=False, checked_count=0, failed_count=1, failures=["invalid threat_model_2_focused_probes shape"])

    runner = build_toy_cipher_from_config(report_config)
    seeds = build_trace_state_indices(runner=runner, run_config=report_config)
    registered = parse_projection_set(
        primary_projection=str(report_config.get("projection", "") or ""),
        additional_projection_specs_csv=(str(report_config.get("additional_projection_specs_csv")) if report_config.get("additional_projection_specs_csv", None) else None),
        word_bits=int(report_config.get("word_bits", 8) or 8),
    )

    recomputed_plan = build_tm2_focus_plan_from_observations(run_config=report_config, cipher=runner, registered_projections=list(registered), seeds=list(seeds))
    recomputed_witnesses, _ = run_tm2_focused_probes(run_config=report_config, cipher=runner, focus_plan=recomputed_plan)

    checked += 1
    if recomputed_plan.get("chosen_x0_indices") != reported_plan.get("chosen_x0_indices"):
        failures.append("chosen_x0_indices mismatch")
    if recomputed_plan.get("focus_windows") != reported_plan.get("focus_windows"):
        failures.append("focus_windows mismatch")
    if recomputed_plan.get("focus_projection_specs") != reported_plan.get("focus_projection_specs"):
        failures.append("focus_projection_specs mismatch")

    checked += 1
    if len(recomputed_witnesses) != len(reported_witnesses):
        failures.append("threat_model_2_witnesses length mismatch")
    else:
        for i, (a, b) in enumerate(zip(recomputed_witnesses, reported_witnesses)):
            if not isinstance(a, dict) or not isinstance(b, dict):
                failures.append(f"threat_model_2_witnesses[{i}] invalid shape")
                continue
            Ea = a.get("E", {}) if isinstance(a.get("E", {}), dict) else {}
            Eb = b.get("E", {}) if isinstance(b.get("E", {}), dict) else {}
            if str(Ea.get("event_digest_sha256", "")) != str(Eb.get("event_digest_sha256", "")):
                failures.append(f"threat_model_2_witnesses[{i}] event_digest_sha256 mismatch")

    return VerificationResult(ok=(len(failures) == 0), checked_count=int(checked), failed_count=int(len(failures)), failures=failures)

def verify_evidence_aggregation_consistency(report: Dict[str, Any]) -> VerificationResult:
    """
    Verify that top-level evidence aggregation is consistent:
    - evidence_objects contains tm1_evidence_objects when present
    - evidence_objects contains exhaustive proof evidence when present
    - witnesses contains tm1_witnesses when present
    """
    failures: List[str] = []
    checked = 0

    ev_top = report.get("evidence_objects", [])
    wi_top = report.get("witnesses", [])
    if not isinstance(ev_top, list):
        failures.append("evidence_objects is not a list")
        ev_top = []
    if not isinstance(wi_top, list):
        failures.append("witnesses is not a list")
        wi_top = []

    def identifiers(objs: List[Any]) -> set[str]:
        out: set[str] = set()
        for o in objs:
            if isinstance(o, dict) and isinstance(o.get("identifier", None), str):
                out.add(str(o["identifier"]))
        return out

    top_ids = identifiers(ev_top)
    top_wi = len(wi_top)

    tm1_ev = report.get("threat_model_1_evidence_objects", None)
    if isinstance(tm1_ev, list):
        checked += 1
        tm1_ids = identifiers(tm1_ev)
        missing = sorted(tm1_ids - top_ids)
        if missing:
            failures.append(f"evidence_objects missing {len(missing)} threat_model_1_evidence_objects identifiers")

    tm1_wi = report.get("threat_model_1_witnesses", None)
    if isinstance(tm1_wi, list):
        checked += 1
        # Witness objects don't have a stable identifier field; compare counts as a minimal invariant.
        if len(tm1_wi) > top_wi:
            failures.append("witnesses has fewer entries than threat_model_1_witnesses (expected aggregated superset)")

    high_dimensional_metrics = report.get("high_dimensional_metrics", None)
    if isinstance(high_dimensional_metrics, dict):
        proof = high_dimensional_metrics.get("proof_evidence_objects_exhaustive", None)
        if isinstance(proof, list):
            checked += 1
            proof_ids = identifiers(proof)
            missing = sorted(proof_ids - top_ids)
            if missing:
                failures.append(f"evidence_objects missing {len(missing)} proof_evidence_objects_exhaustive identifiers")

    # Block cipher TM-2/TM-3 must expose full trajectory (not only 1D state):
    # winding_trajectory_profile required.
    visibility = report.get("visibility", {}) or {}
    tm = str(
        visibility.get("threat_model_level", "")
        or report.get("config", {}).get("threat_model_level", "")
    )
    tm_norm = tm.lower()
    is_tm2_or_tm3 = (
        ("threat_model_2" in tm_norm)
        or ("tm2" in tm_norm)
        or ("threat_model_3" in tm_norm)
        or ("tm3" in tm_norm)
    )
    if is_tm2_or_tm3 and report.get("experiment_type") not in STREAM_HASH_EXPERIMENT_TYPES:
        checked += 1
        winding = report.get("winding_trajectory_profile")
        if not isinstance(winding, dict):
            failures.append("block cipher TM-2/TM-3 report missing winding_trajectory_profile (multi-dimensional trajectory)")
        else:
            checked += 1
            if not isinstance(winding.get("trajectory_semantics_summary"), dict):
                failures.append("block cipher TM-2/TM-3 report missing winding_trajectory_profile.trajectory_semantics_summary")
            checked += 1
            if not isinstance(winding.get("computation_backend_summary"), dict):
                failures.append("block cipher TM-2/TM-3 report missing winding_trajectory_profile.computation_backend_summary")

    return VerificationResult(ok=(len(failures) == 0), checked_count=int(checked), failed_count=int(len(failures)), failures=failures)
