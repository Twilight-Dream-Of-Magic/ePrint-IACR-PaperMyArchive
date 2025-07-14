from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..evidence.map_utils import peak_slice_multiplicity_point, top_revisit_times, top_slice_multiplicity_points
from ..utils.event_summaries import count_op_families, op_family, region_id
from ..evidence.objects import EvidenceObject, WitnessObject
from ..projections.projections import parse_projection
from ..run_helpers import run_trace_from_state_index


def _run_config_get(run_config: Any, key: str, default: Any = None) -> Any:
    if isinstance(run_config, dict):
        return run_config.get(key, default)
    return getattr(run_config, key, default)


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(int(lo), min(int(hi), int(value)))


def _sha256_lines(text_lines: List[str]) -> str:
    import hashlib

    h = hashlib.sha256()
    for line in text_lines:
        h.update((str(line) + "\n").encode("utf-8"))
    return h.hexdigest()


def _merge_windows(windows: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    windows = sorted((int(a), int(b)) for (a, b) in windows)
    merged: List[Tuple[int, int]] = []
    for a, b in windows:
        if not merged:
            merged.append((a, b))
            continue
        pa, pb = merged[-1]
        if a <= pb + 1:
            merged[-1] = (pa, max(pb, b))
        else:
            merged.append((a, b))
    return merged


def _seed_pool_from_seeds(seeds: List[int], max_count: int = 64) -> List[int]:
    return list(int(s) for s in seeds[: min(len(seeds), int(max_count))])


def _collect_observations_by_trace(*, runner: Any, seed_pool: List[int], proj_fn: Any) -> List[List[int]]:
    out: List[List[int]] = []
    for state_index in seed_pool:
        states, _ = run_trace_from_state_index(
            runner=runner,
            state_index=int(state_index),
            run_config=None,
        )
        out.append([int(proj_fn(st)) for st in states])
    return out


def build_tm2_focus_plan_from_observations(
    *,
    run_config: Any,
    cipher: Any,
    registered_projections: List[Tuple[str, Any]],
    seeds: List[int],
) -> Dict[str, Any]:
    """
    TM-2 focused-probe plan:
    - use observation-only evidence-map (primary projection) to pick focus windows and hotspots
    - choose a small set of chosen inputs from the deterministic seed pool (limited intervention)
    """
    seed_pool = _seed_pool_from_seeds(list(seeds), max_count=64)
    focus_topk = max(1, int(_run_config_get(run_config, "threat_model_3_focus_topk", 4) or 4))
    focus_radius = max(0, int(_run_config_get(run_config, "threat_model_3_window_radius", 2) or 2))
    max_probes = max(1, int(_run_config_get(run_config, "threat_model_3_max_probes", 8) or 8))
    intervention_budget = max(1, int(_run_config_get(run_config, "threat_model_3_intervention_budget", 64) or 64))

    primary_projection_spec, primary_proj_fn = registered_projections[0]
    primary_observations = _collect_observations_by_trace(runner=cipher, seed_pool=seed_pool, proj_fn=primary_proj_fn)
    evidence_map_primary = {
        "max_shadow_point": peak_slice_multiplicity_point(primary_observations),
        "top_shadow_points": top_slice_multiplicity_points(observations_by_trace=primary_observations, top_k=8),
        "top_revisit_times": top_revisit_times(observations_by_trace=primary_observations, top_k=8),
        "note": "Threat Model 2 focus planning uses Threat Model 1-safe evidence-map derived from observations only.",
    }

    hotspot_points: List[Tuple[int, int]] = []
    hotspot_times: List[int] = []
    for p in evidence_map_primary.get("top_shadow_points", []) if isinstance(evidence_map_primary.get("top_shadow_points", []), list) else []:
        if not isinstance(p, dict):
            continue
        if p.get("time_index") is None or p.get("observation_value") is None:
            continue
        hotspot_points.append((int(p["time_index"]), int(p["observation_value"])))
        hotspot_times.append(int(p["time_index"]))
    for rt in evidence_map_primary.get("top_revisit_times", []) if isinstance(evidence_map_primary.get("top_revisit_times", []), list) else []:
        if not isinstance(rt, dict):
            continue
        if rt.get("time_index") is None:
            continue
        hotspot_times.append(int(rt["time_index"]))

    windows: List[Tuple[int, int]] = []
    for t in sorted({int(x) for x in hotspot_times}):
        windows.append((max(0, int(t) - int(focus_radius)), int(t) + int(focus_radius)))
    focus_windows = _merge_windows(windows)[:focus_topk]

    # chosen-input selection: score seed_pool by hotspot hits across a small set of focus projections.
    focus_projection_specs = [str(spec) for (spec, _) in registered_projections]
    seed_scores: Dict[int, int] = {int(s): 0 for s in seed_pool}
    used = 0
    for proj_spec in focus_projection_specs:
        if used >= intervention_budget:
            break
        _, proj_fn = parse_projection(str(proj_spec), word_bits=int(_run_config_get(run_config, "word_bits", 8) or 8))
        for s in seed_pool:
            if used >= intervention_budget:
                break
            states, _ = run_trace_from_state_index(
                runner=cipher,
                state_index=int(s),
                run_config=run_config,
            )
            obs = [int(proj_fn(st)) for st in states]
            for (t, y) in hotspot_points[:32]:
                if 0 <= int(t) < len(obs) and int(obs[int(t)]) == int(y):
                    seed_scores[int(s)] = int(seed_scores.get(int(s), 0)) + 1
            used += 1

    ranked_seeds = sorted(seed_scores.items(), key=lambda kv: (kv[1], -kv[0]), reverse=True)
    chosen_seed_values = [int(s) for s, score in ranked_seeds if int(score) > 0][:max_probes]
    if not chosen_seed_values:
        chosen_seed_values = [int(s) for s in seed_pool[:max_probes]]
    chosen_x0_raw = [int(s) for s in chosen_seed_values]
    seen_x0: set[int] = set()
    chosen_x0_indices: List[int] = []
    for x0 in chosen_x0_raw:
        if int(x0) in seen_x0:
            continue
        seen_x0.add(int(x0))
        chosen_x0_indices.append(int(x0))

    return {
        "primary_projection_spec": str(primary_projection_spec),
        "seed_pool_head": list(int(x) for x in seed_pool[:16]),
        "state_index_pool_head": list(int(x) for x in seed_pool[:16]),
        "evidence_map_primary": evidence_map_primary,
        "focus_projection_specs": list(focus_projection_specs),
        "focus_windows": [list(map(int, w)) for w in focus_windows],
        "hotspot_points_head": [{"time_index": int(t), "observation_value": int(y)} for (t, y) in hotspot_points[:16]],
        "chosen_seed_values": list(int(x) for x in chosen_seed_values),
        "chosen_x0_indices": list(int(x) for x in chosen_x0_indices),
        "chosen_state_indices": list(int(x) for x in chosen_x0_indices),
        "params": {
            "focus_topk": int(focus_topk),
            "focus_radius": int(focus_radius),
            "max_probes": int(max_probes),
            "intervention_budget": int(intervention_budget),
        },
        "selection_rule": {
            "focus_windows_rule": "centered at evidence-map hotspot times with radius; merged; top-k kept",
            "chosen_inputs_rule": "score seed_pool by hotspot hits across focus projections; fallback to first seeds",
            "note": "chosen_x0_indices are deduplicated in state-index space (Omega^n for vector presets, Z_q for scalar presets).",
        },
    }


def run_tm2_focused_probes(
    *,
    run_config: Any,
    cipher: Any,
    focus_plan: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    word_bits = int(_run_config_get(run_config, "word_bits", 8) or 8)
    focus_projection_specs = focus_plan.get("focus_projection_specs", [])
    if not isinstance(focus_projection_specs, list):
        focus_projection_specs = []
    focus_windows = focus_plan.get("focus_windows", [])
    if not isinstance(focus_windows, list):
        focus_windows = []
    hotspot_points = focus_plan.get("hotspot_points_head", [])
    if not isinstance(hotspot_points, list):
        hotspot_points = []
    chosen_x0_indices = focus_plan.get("chosen_x0_indices", [])
    if not isinstance(chosen_x0_indices, list):
        chosen_x0_indices = []

    tm2_witnesses: List[Dict[str, Any]] = []
    tm2_evidence_objects: List[Dict[str, Any]] = []

    for probe_index, x0 in enumerate(chosen_x0_indices):
        states, events = run_trace_from_state_index(
            runner=cipher,
            state_index=int(x0),
            run_config=run_config,
        )
        total_steps = max(0, len(states) - 1)

        projection_observations: Dict[str, List[int]] = {}
        for proj_spec in focus_projection_specs:
            try:
                _, proj_fn = parse_projection(str(proj_spec), word_bits=int(word_bits))
                projection_observations[str(proj_spec)] = [int(proj_fn(st)) for st in states]
            except Exception:
                projection_observations[str(proj_spec)] = []

        for w_idx, w in enumerate(focus_windows):
            if not isinstance(w, list) or len(w) != 2:
                continue
            a0, b0 = int(w[0]), int(w[1])
            a = _clamp_int(int(a0), 0, total_steps)
            b = _clamp_int(int(b0), 0, total_steps)
            if b < a:
                continue

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
                        if getattr(states[t + 1], "x", None) != getattr(states[t], "x", None):
                            nsl += 1
                sl_by_projection[str(proj_spec)] = int(sl)
                nsl_by_projection[str(proj_spec)] = int(nsl)

            top_regions = sorted(
                (
                    (rid, float(v["wraps"]) / float(v["steps"]) if v["steps"] > 0 else 0.0, int(v["steps"]))
                    for rid, v in region_counts.items()
                ),
                key=lambda x: x[1],
                reverse=True,
            )[:8]

            witness = WitnessObject(
                config={
                    "threat_model_level": "threat_model_2_instrumented",
                    "threat_model_2_probe_index": int(probe_index),
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
                Z={
                    "events_head": [
                        {"time_counter": ev.tc, "operation": ev.op, "building_label": ev.floor, "value_x_before": ev.x0, "value_x_after": ev.x1, "wrap_event": ev.wrap}
                        for ev in ev_slice[: min(8, len(ev_slice))]
                    ]
                },
                evidence_map={
                    "focus_window": [int(a), int(b)],
                    "threat_model_1_hotspot_points_head": list(hotspot_points),
                    "note": "Threat Model 2 focused probe witness (mechanism-aligned).",
                },
            ).as_dict()
            tm2_witnesses.append(witness)
            tm2_evidence_objects.append(
                EvidenceObject(
                    identifier=f"threat_model_2_focused_probe::probe:{int(probe_index)}::x0:{int(x0)}::w:{int(a)}-{int(b)}",
                    summary="Threat Model 2 focused probe evidence object (mechanism-aligned witness).",
                    value={"initial_state_value": int(x0), "focus_window": [int(a), int(b)], "event_count": int(len(ev_slice)), "wrap_count": int(wrap_count)},
                    p_value=None,
                    witness=witness,
                    metadata={"stage": "threat_model_2_focused_probe", "focus_window_index": int(w_idx)},
                ).as_dict()
            )

    return tm2_witnesses, tm2_evidence_objects

