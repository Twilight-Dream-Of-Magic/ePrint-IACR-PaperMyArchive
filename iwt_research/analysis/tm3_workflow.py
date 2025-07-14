from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Dict, List, Tuple

from ..evidence.objects import EvidenceObject, WitnessObject
from ..utils.event_summaries import count_op_families, region_id
from ..projections.projections import parse_projection
from ..ciphers.runner_factory import build_toy_cipher_from_config
from ..metrics.trajectory import (
    aggregate_winding_trajectory_reports,
    compute_winding_trajectory_report,
)
from ..analysis.performance_budget import compute_block_performance_budget_report
from ..alignment.todo_alignment import build_todo_alignment_section
from ..report import attach_report_contract_metadata
from .threat_model import ThreatModelLevel, apply_visibility_filter_to_report
from ..run_helpers import (
    build_trace_state_indices,
    run_trace_from_state_index,
    runner_uses_vector_state_space,
    state_index_space_size,
)


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(int(lo), min(int(hi), int(value)))


def _sha256_lines(text_lines: List[str]) -> str:
    import hashlib

    h = hashlib.sha256()
    for line in text_lines:
        h.update((str(line) + "\n").encode("utf-8"))
    return h.hexdigest()


def _select_focus_indices_from_tm1_scan(*, tm1_scan: Dict[str, Any], focus_topk: int) -> List[int]:
    focus_topk = max(1, int(focus_topk))
    fdr = tm1_scan.get("benjamini_hochberg_false_discovery_rate", {})
    if isinstance(fdr, dict):
        rejected = fdr.get("rejected_indices", [])
        if isinstance(rejected, list) and rejected:
            out = sorted({int(i) for i in rejected})
            return out[:focus_topk]

    tests = tm1_scan.get("tests", [])
    if not isinstance(tests, list) or not tests:
        return []
    scored: List[Tuple[float, int]] = []
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            continue
        pv = t.get("p_value_two_sided", None)
        if pv is None:
            continue
        try:
            scored.append((float(pv), int(i)))
        except Exception:
            continue
    scored.sort(key=lambda kv: kv[0])
    return [int(i) for _, i in scored[:focus_topk]]


def _build_cipher_from_run_config(run_config: Any) -> Any:
    return build_toy_cipher_from_config(run_config)


def run_tm3_workflow(*, run_config: Any, run_tm1: Any) -> Dict[str, Any]:
    """
    TM-3 workflow runner extracted from run_experiment.py.
    - run_tm1(tm1_run_config) must return a TM-1 report dict (typically run_toy_iwt on a tm1 config).
    """
    tm1_run_config = replace(run_config, threat_model_level=ThreatModelLevel.threat_model_1_black_box.value)
    tm1_screening_report = run_tm1(tm1_run_config)

    cipher = _build_cipher_from_run_config(run_config)
    trace_state_indices = build_trace_state_indices(runner=cipher, run_config=run_config)
    planning_seed_pool = list(int(s) for s in trace_state_indices[: min(len(trace_state_indices), 64)])

    tm1_scan = tm1_screening_report.get("threat_model_1_multi_projection_scan", {})
    if not isinstance(tm1_scan, dict):
        tm1_scan = {}
    focus_indices = _select_focus_indices_from_tm1_scan(tm1_scan=tm1_scan, focus_topk=int(run_config.threat_model_3_focus_topk))
    tests = tm1_scan.get("tests", [])
    if not isinstance(tests, list):
        tests = []

    focus_projection_specs: List[str] = []
    for idx in focus_indices:
        if 0 <= int(idx) < len(tests):
            t = tests[int(idx)]
            if isinstance(t, dict) and isinstance(t.get("projection_spec", None), str):
                focus_projection_specs.append(str(t["projection_spec"]))
    # dedup
    seen: set[str] = set()
    focus_projection_specs = [s for s in focus_projection_specs if not (s in seen or seen.add(s))]

    hotspot_points: List[Tuple[int, int]] = []
    hotspot_times: List[int] = []
    for idx in focus_indices:
        if 0 <= int(idx) < len(tests):
            t = tests[int(idx)]
            ev_map = t.get("evidence_map", {}) if isinstance(t, dict) else {}
            if not isinstance(ev_map, dict):
                continue
            for p in ev_map.get("top_shadow_points", []) if isinstance(ev_map.get("top_shadow_points", []), list) else []:
                if isinstance(p, dict) and p.get("time_index") is not None and p.get("observation_value") is not None:
                    hotspot_points.append((int(p["time_index"]), int(p["observation_value"])))
                    hotspot_times.append(int(p["time_index"]))
            for rt in ev_map.get("top_revisit_times", []) if isinstance(ev_map.get("top_revisit_times", []), list) else []:
                if isinstance(rt, dict) and rt.get("time_index") is not None:
                    hotspot_times.append(int(rt["time_index"]))

    focus_radius = max(0, int(run_config.threat_model_3_window_radius))
    focus_windows: List[Tuple[int, int]] = []
    for t in sorted({int(x) for x in hotspot_times}):
        focus_windows.append((max(0, t - focus_radius), t + focus_radius))
    focus_windows.sort()
    merged: List[Tuple[int, int]] = []
    for a, b in focus_windows:
        if not merged:
            merged.append((a, b))
        else:
            pa, pb = merged[-1]
            if a <= pb + 1:
                merged[-1] = (pa, max(pb, b))
            else:
                merged.append((a, b))
    focus_windows = merged[: max(1, int(run_config.threat_model_3_focus_topk))]

    # chosen-input planning (deterministic heuristic)
    seed_hit_scores: Dict[int, int] = {int(s): 0 for s in planning_seed_pool}
    budget = max(1, int(run_config.threat_model_3_intervention_budget))
    used = 0
    for proj_spec in focus_projection_specs:
        if used >= budget:
            break
        _, proj_fn = parse_projection(str(proj_spec), word_bits=int(run_config.word_bits))
        for s in planning_seed_pool:
            if used >= budget:
                break
            states, _ = run_trace_from_state_index(
                runner=cipher,
                state_index=int(s),
                run_config=run_config,
            )
            obs = [int(proj_fn(st)) for st in states]
            for (t, y) in hotspot_points[:32]:
                if 0 <= int(t) < len(obs) and int(obs[int(t)]) == int(y):
                    seed_hit_scores[int(s)] = int(seed_hit_scores.get(int(s), 0)) + 1
            used += 1

    ranked = sorted(seed_hit_scores.items(), key=lambda kv: (kv[1], -kv[0]), reverse=True)
    max_probes = max(1, int(run_config.threat_model_3_max_probes))
    chosen_seed_values = [int(s) for s, score in ranked if int(score) > 0][:max_probes] or [int(s) for s in planning_seed_pool[:max_probes]]
    candidate_x0_indices = [int(s) for s in chosen_seed_values]
    seen_x0: set[int] = set()
    chosen_x0_indices: List[int] = []
    for x0 in candidate_x0_indices:
        if x0 in seen_x0:
            continue
        seen_x0.add(int(x0))
        chosen_x0_indices.append(int(x0))

    stageB_plan = {
        "focus_projection_specs": list(focus_projection_specs),
        "focus_windows": [list(map(int, w)) for w in focus_windows],
        "chosen_seed_values": list(int(x) for x in chosen_seed_values),
        "chosen_x0_indices": list(int(x) for x in chosen_x0_indices),
        "chosen_state_indices": list(int(x) for x in chosen_x0_indices),
        "params": {
            "focus_topk": int(run_config.threat_model_3_focus_topk),
            "focus_radius": int(run_config.threat_model_3_window_radius),
            "max_probes": int(run_config.threat_model_3_max_probes),
            "intervention_budget": int(run_config.threat_model_3_intervention_budget),
        },
        "selection_rule": {
            "focus_windows_rule": "centered at evidence-map hotspot times with radius; merged; top-k kept",
            "chosen_inputs_rule": "score seed_pool by hotspot hits across focus projections; fallback to first seeds",
            "note": "chosen_x0_indices are deduplicated in state-index space (Omega^n for vector presets, Z_q for scalar presets).",
        },
    }

    tm2_witnesses: List[Dict[str, Any]] = []
    tm2_evidence_objects: List[Dict[str, Any]] = []
    winding_trajectory_reports: List[Dict[str, Any]] = []
    for probe_index, x0 in enumerate(chosen_x0_indices):
        states, events = run_trace_from_state_index(
            runner=cipher,
            state_index=int(x0),
            run_config=run_config,
        )
        winding_trajectory_reports.append(
            compute_winding_trajectory_report(states=states, events=events)
        )
        total_steps = max(0, len(states) - 1)
        projection_observations: Dict[str, List[int]] = {}
        for proj_spec in focus_projection_specs:
            try:
                _, proj_fn = parse_projection(str(proj_spec), word_bits=int(run_config.word_bits))
                projection_observations[str(proj_spec)] = [int(proj_fn(st)) for st in states]
            except Exception:
                projection_observations[str(proj_spec)] = []
        for (a0, b0) in focus_windows:
            a = _clamp_int(int(a0), 0, total_steps)
            b = _clamp_int(int(b0), 0, total_steps)
            ev_slice = events[a : max(a, min(len(events), b))]
            op_counts = count_op_families(ev_slice)
            floor_counts: Dict[str, int] = {}
            wrap_count = 0
            region_counts: Dict[str, Dict[str, int]] = {}
            for ev in ev_slice:
                floor_counts[str(ev.floor)] = int(floor_counts.get(str(ev.floor), 0)) + 1
                if bool(getattr(ev, "wrap", False)):
                    wrap_count += 1
                rid = region_id(ev)
                if rid not in region_counts:
                    region_counts[rid] = {"steps": 0, "wraps": 0}
                region_counts[rid]["steps"] += 1
                if bool(getattr(ev, "wrap", False)):
                    region_counts[rid]["wraps"] += 1
            ev_digest = _sha256_lines(
                [f"{ev.tc}|{ev.op}|{ev.floor}|{ev.x0}|{ev.x1}|{int(bool(getattr(ev, 'wrap', False)))}" for ev in ev_slice]
            )

            nsl_by_projection: Dict[str, int] = {}
            sl_by_projection: Dict[str, int] = {}
            for proj_spec, obs in projection_observations.items():
                if not obs or b >= len(obs):
                    continue
                nsl = 0
                sl = 0
                for t in range(a, b):
                    if int(obs[t + 1]) == int(obs[t]):
                        sl += 1
                        if states[t + 1].x != states[t].x:  # type: ignore[comparison-overlap]
                            nsl += 1
                sl_by_projection[str(proj_spec)] = int(sl)
                nsl_by_projection[str(proj_spec)] = int(nsl)
            top_regions = sorted(
                ((rid, float(v["wraps"]) / float(v["steps"]) if v["steps"] else 0.0, int(v["steps"])) for rid, v in region_counts.items()),
                key=lambda x: x[1],
                reverse=True,
            )[:8]

            witness = WitnessObject(
                config={
                    "threat_model_level": ThreatModelLevel.threat_model_2_instrumented.value,
                    "threat_model_3_probe_index": int(probe_index),
                    "initial_state_value": int(x0),
                    "focus_window": [int(a), int(b)],
                    "focus_projection_specs": list(focus_projection_specs),
                },
                E={
                    "event_digest_sha256": str(ev_digest),
                    "event_count": int(len(ev_slice)),
                    "wrap_count": int(wrap_count),
                    "op_family_counts": dict(op_counts),
                    "floor_counts": dict(floor_counts),
                    "sl_count_by_projection": dict(sl_by_projection),
                    "nsl_count_by_projection": dict(nsl_by_projection),
                    "top_regions_by_wrap_density": [{"region_id": rid, "wrap_density": dens, "steps": steps} for (rid, dens, steps) in top_regions],
                },
                Z={"events_head": [{"time_counter": ev.tc, "operation": ev.op, "building_label": ev.floor, "value_x_before": ev.x0, "value_x_after": ev.x1, "wrap_event": ev.wrap} for ev in ev_slice[: min(8, len(ev_slice))]]},
                evidence_map={"focus_window": [int(a), int(b)], "threat_model_1_hotspot_points_head": [{"time_index": int(t), "observation_value": int(y)} for (t, y) in hotspot_points[:16]]},
            ).as_dict()
            tm2_witnesses.append(witness)
            tm2_evidence_objects.append(
                EvidenceObject(
                    identifier=f"threat_model_3_stageC_threat_model_2_probe::probe:{int(probe_index)}::x0:{int(x0)}::w:{int(a)}-{int(b)}",
                    summary="Threat Model 3 Stage C focused Threat Model 2 probe evidence object (mechanism-aligned witness).",
                    value={"initial_state_value": int(x0), "focus_window": [int(a), int(b)], "event_count": int(len(ev_slice)), "wrap_count": int(wrap_count)},
                    p_value=None,
                    witness=witness,
                    metadata={"stage": "threat_model_3_stageC_threat_model_2", "cipher_preset": str(run_config.cipher_preset)},
                ).as_dict()
            )

    is_vector_state_space = runner_uses_vector_state_space(
        cipher,
        cipher_preset=str(run_config.cipher_preset),
    )
    space_size = state_index_space_size(
        runner=cipher,
        lane_count=int(run_config.lane_count),
        cipher_preset=str(run_config.cipher_preset),
    )
    out: Dict[str, Any] = {
        "config": asdict(run_config),
        "experiment_type": "block_cipher_tm3_workflow",
        "visibility": {"threat_model_level": ThreatModelLevel.threat_model_3_intervention.value},
        "sampling": {
            "mode": "exhaustive" if bool(run_config.exhaustive) else "random",
            "trace_count_effective": len(trace_state_indices),
            "state_index_space_size": int(space_size),
            "state_space_semantics": ("omega_power_n" if is_vector_state_space else "z_q"),
        },
        "threat_model_3_workflow": {
            "stageA_threat_model_1_summary": {
                "threat_model_level": "threat_model_1_black_box",
                "threat_model_1_multi_projection_scan": tm1_screening_report.get("threat_model_1_multi_projection_scan", None),
            },
            "stageB_intervention_plan": stageB_plan,
            "stageC_threat_model_2_witnesses": tm2_witnesses,
        },
        "threat_model_1_evidence_objects": tm1_screening_report.get("threat_model_1_evidence_objects", [])
        if isinstance(tm1_screening_report.get("threat_model_1_evidence_objects", None), list)
        else [],
        "threat_model_1_witnesses": tm1_screening_report.get("threat_model_1_witnesses", [])
        if isinstance(tm1_screening_report.get("threat_model_1_witnesses", None), list)
        else [],
        "threat_model_2_witnesses": tm2_witnesses,
        "evidence_objects": [],
        "witnesses": [],
        "winding_trajectory_profile": aggregate_winding_trajectory_reports(
            winding_trajectory_reports
        ),
    }
    if winding_trajectory_reports:
        out["winding_trajectory_example"] = winding_trajectory_reports[0]

    if isinstance(tm1_screening_report.get("evidence_objects", None), list):
        out["evidence_objects"].extend(tm1_screening_report["evidence_objects"])
    if isinstance(tm1_screening_report.get("witnesses", None), list):
        out["witnesses"].extend(tm1_screening_report["witnesses"])
    out["evidence_objects"].extend(tm2_evidence_objects)
    out["witnesses"].extend(tm2_witnesses)
    out["performance_budget"] = compute_block_performance_budget_report(
        run_config=run_config,
        sampling_mode=("exhaustive" if bool(run_config.exhaustive) else "random"),
        trace_count_effective=len(trace_state_indices),
    ).as_dict()

    filtered = apply_visibility_filter_to_report(out, level=ThreatModelLevel.threat_model_3_intervention)
    attach_report_contract_metadata(filtered)
    filtered["todo_alignment"] = build_todo_alignment_section(filtered)
    return filtered

