from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

from ..analysis.performance_budget import compute_block_performance_budget_report
from ..analysis.threat_model import ThreatModelLevel
from ..ciphers.runner_factory import build_toy_cipher_from_config
from ..metrics.high_dimensional import add_trace_to_empirical_adjacency
from ..metrics.non_degeneracy import compute_non_degeneracy_report
from ..metrics.observation_metrics import compute_observation_side_metrics
from ..metrics.winding_metrics import (
    bootstrap_ci,
    compute_mechanism_side_metrics,
    compute_pattern_side_metrics,
    compute_projection_metrics,
    compute_slice_shadow_metrics,
)
from ..metrics.trajectory import (
    aggregate_winding_trajectory_reports,
    compute_winding_trajectory_report,
)
from ..projections.registry import parse_projection_set
from ..run_helpers import (
    build_trace_state_indices,
    run_trace_from_state_index,
    runner_uses_vector_state_space,
    state_index_space_size,
    state_space_coverage_ratio,
)
from ..utils.event_summaries import aggregate_region_counts, count_op_families
from ..utils.stats import mean
from .config import RunConfig


@dataclass(slots=True)
class BlockCoreArtifacts:
    result: Dict[str, Any]
    cipher: Any
    registered_projections: List[Tuple[str, Any]] = field(default_factory=list)
    primary_projection_spec: str = ""
    projection: Any = None
    state_indices: List[int] = field(default_factory=list)
    total_steps: int = 0
    omega_core_size: int = 0
    empirical_adjacency: Dict[Any, set[Any]] | None = None
    empirical_sources: List[Any] | None = None
    edge_counts_total: Dict[str, int] = field(default_factory=dict)
    region_agg_total: Dict[str, Dict[str, float]] = field(default_factory=dict)
    ys_all: List[List[int]] = field(default_factory=list)
    max_abs_quotient_per_trace: List[float] = field(default_factory=list)
    snapshot_count_per_trace: List[int] = field(default_factory=list)


def observed_space_size_from_projection(run_config: RunConfig) -> int | None:
    spec = str(run_config.projection)
    if spec.startswith("lane:"):
        return 1 << run_config.word_bits
    if spec.startswith("lane_lowbits:"):
        k = int(spec.split(":", 2)[2])
        return 2**k
    if spec.startswith("lane_highbits:"):
        k = int(spec.split(":", 2)[2])
        return 2**k
    if spec.startswith("lane_bit:"):
        return 2
    if spec.startswith("lowbits:"):
        k = int(spec.split(":", 1)[1])
        return 2**k
    if spec.startswith("highbits:"):
        k = int(spec.split(":", 1)[1])
        return 2**k
    if spec.startswith("bit:"):
        return 2
    if spec == "core":
        return 1 << run_config.word_bits
    return None


def compute_block_core_artifacts(
    *,
    run_config: RunConfig,
    threat_model_level: ThreatModelLevel,
) -> BlockCoreArtifacts:
    registered_projections = parse_projection_set(
        primary_projection=str(run_config.projection),
        additional_projection_specs_csv=run_config.additional_projection_specs_csv,
        word_bits=int(run_config.word_bits),
    )
    primary_projection_spec, primary_projection = registered_projections[0]
    proj = primary_projection

    cipher = build_toy_cipher_from_config(run_config)
    is_vector_state_space = runner_uses_vector_state_space(
        cipher,
        cipher_preset=str(run_config.cipher_preset),
    )
    state_space_size = state_index_space_size(
        runner=cipher,
        lane_count=int(run_config.lane_count),
        cipher_preset=str(run_config.cipher_preset),
    )

    wrap_rates: List[float] = []
    sl_rates: List[float] = []
    nsl_rates: List[float] = []
    collision_rates: List[float] = []
    self_intersection_rates: List[float] = []
    observation_self_loop_rates: List[float] = []
    observation_self_intersection_rates: List[float] = []
    occupancy_rates: List[float] = []
    ys_all: List[List[int]] = []
    coverage_rates: List[float] = []
    ih_in_maxes: List[float] = []
    ih_in_finals: List[float] = []
    projection_unique_node_counts: List[int] = []
    projection_step_counts: List[int] = []
    example: Dict[str, Any] = {}

    q1 = 1 << run_config.word_bits
    if run_config.cipher_preset in ("toy_spn", "toy_substitution_permutation_network"):
        omega_core_size = q1
    elif run_config.cipher_preset in (
        "toy_spn_vector",
        "toy_substitution_permutation_network_vector",
    ):
        lane_count = int(run_config.lane_count)
        omega_core_size = int(q1) ** int(lane_count)
    else:
        q2 = int(run_config.cross_domain_modulus) if run_config.cross_domain_modulus else 0
        omega_core_size = q1 + (q2 if run_config.cross_domain_modulus else 0)

    winding_trajectory_reports: List[Dict[str, Any]] = []
    edge_counts_total: Dict[str, int] = {}
    region_agg_total: Dict[str, Dict[str, float]] = {}
    max_abs_quotient_per_trace: List[float] = []
    snapshot_count_per_trace: List[int] = []
    empirical_adjacency: Dict[Any, set[Any]] | None = None
    empirical_sources: List[Any] | None = None
    if run_config.cipher_preset in (
        "toy_spn_vector",
        "toy_substitution_permutation_network_vector",
    ):
        empirical_adjacency = {}
        empirical_sources = []

    state_indices = build_trace_state_indices(runner=cipher, run_config=run_config)
    for i, state_index in enumerate(state_indices):
        x0 = int(state_index)
        states, events = run_trace_from_state_index(
            runner=cipher,
            state_index=int(state_index),
            run_config=run_config,
        )
        ys_primary = [primary_projection(st) for st in states]
        ys = ys_primary
        observation_side = compute_observation_side_metrics(observations=ys_primary)
        projection_metrics = compute_projection_metrics(ys=ys_primary, observed_space_size=None)
        ys_all.append(ys_primary)
        projection_unique_node_counts.append(int(projection_metrics.unique_nodes))
        projection_step_counts.append(int(projection_metrics.steps))

        if threat_model_level != ThreatModelLevel.threat_model_1_black_box:
            ih_in_maxes.append(
                float(
                    max(
                        int(st.information_height.current_building_height)
                        for st in states
                    )
                )
            )
            ih_in_finals.append(
                float(int(states[-1].information_height.current_building_height))
            )

        observation_self_loop_rates.append(
            float(observation_side.observation_self_loop_rate)
        )
        observation_self_intersection_rates.append(
            float(observation_side.observation_self_intersection_rate)
        )

        if threat_model_level != ThreatModelLevel.threat_model_1_black_box:
            mechanism_side = compute_mechanism_side_metrics(states=states, events=events)
            pattern_side = compute_pattern_side_metrics(
                states=states,
                events=events,
                project=proj,
                observed_space_size=None,
            )
            wrap_rates.append(float(mechanism_side["wrap_event_rate"]))
            winding_trajectory_reports.append(
                compute_winding_trajectory_report(states=states, events=events)
            )
            sl_rates.append(float(pattern_side["self_loop"]["trivial_self_loop_event_rate"]))
            nsl_rates.append(
                float(pattern_side["self_loop"]["nontrivial_self_loop_event_rate"])
            )
        collision_rates.append(projection_metrics.as_dict()["collision_rate"])
        observed_space_size = observed_space_size_from_projection(run_config)
        if observed_space_size:
            occupancy_rates.append(projection_metrics.unique_nodes / float(observed_space_size))
        if threat_model_level != ThreatModelLevel.threat_model_1_black_box:
            coverage_rates.append(state_space_coverage_ratio(states, omega_core_size))

        if (
            threat_model_level != ThreatModelLevel.threat_model_1_black_box
            and empirical_adjacency is not None
            and empirical_sources is not None
        ):
            trace_nodes: List[Any] = []
            for st in states:
                x = st.x
                if isinstance(x, (tuple, list)):
                    trace_nodes.append(tuple(int(v) for v in x))
                else:
                    trace_nodes.append(int(x))
            if trace_nodes:
                empirical_sources.append(trace_nodes[0])
            add_trace_to_empirical_adjacency(
                adjacency=empirical_adjacency,
                trace_nodes=trace_nodes,
            )

        if threat_model_level != ThreatModelLevel.threat_model_1_black_box:
            edge_counts_this_trace = count_op_families(events)
            for k, v in edge_counts_this_trace.items():
                edge_counts_total[k] = edge_counts_total.get(k, 0) + v
            region_aggregate = aggregate_region_counts(
                states=states,
                events=list(events),
                project=proj,
            )
            for rid, region_data in region_aggregate.items():
                if rid not in region_agg_total:
                    region_agg_total[rid] = {
                        "step_count": 0.0,
                        "wrap_count": 0.0,
                        "nontrivial_self_loop_count": 0.0,
                    }
                region_agg_total[rid]["step_count"] += float(region_data["step_count"])
                region_agg_total[rid]["wrap_count"] += float(region_data["wrap_count"])
                region_agg_total[rid]["nontrivial_self_loop_count"] += float(
                    region_data["nontrivial_self_loop_count"]
                )

            max_abs_q = (
                max(
                    abs(int(st.information_height.cross_domain_reencoding_quotient))
                    for st in states
                )
                if states
                else 0
            )
            snap_count = (
                len(states[-1].information_height.building_exit_snapshots) if states else 0
            )
            max_abs_quotient_per_trace.append(float(max_abs_q))
            snapshot_count_per_trace.append(int(snap_count))

        seen = set()
        for t, y in enumerate(ys):
            if t == 0:
                seen.add(y)
                continue
            if y in seen:
                pass
            seen.add(y)
        if threat_model_level != ThreatModelLevel.threat_model_1_black_box:
            self_intersection_rates.append(float(pattern_side["self_intersection_rate"]))
        else:
            self_intersection_rates.append(
                float(observation_side.observation_self_intersection_rate)
            )

        if i == 0 and threat_model_level != ThreatModelLevel.threat_model_1_black_box:

            def ev_to_dict(e: Any) -> Dict[str, Any]:
                return {
                    "time_counter": e.tc,
                    "operation": e.op,
                    "building_label": e.floor,
                    "modulus_q": e.q,
                    "representative_w": e.w,
                    "value_x_before": e.x0,
                    "value_x_after": e.x1,
                    "preflight_raw_value": e.raw,
                    "building_height_delta": e.delta,
                    "wrap_event": e.wrap,
                    "carry_flag": e.carry,
                    "borrow_flag": e.borrow,
                    "meta": dict(e.meta),
                }

            cross_idx = None
            for j, e in enumerate(events):
                if str(e.op).startswith("cross_domain"):
                    cross_idx = j
                    break
            if cross_idx is None:
                cross_states = []
                cross_events = []
            else:
                a = max(0, cross_idx - 3)
                b = min(len(states), cross_idx + 5)
                cross_states = [st.as_public_dict() for st in states[a:b]]
                cross_events = [ev_to_dict(e) for e in events[a : min(len(events), b - 1)]]

            example = {
                "initial_state_value": int(x0),
                "initial_state_index": int(x0),
                "projection": run_config.projection,
                "note": "states_head/events_head are truncated windows (first 10 states/events), not full-trace maxima.",
                "observations_head": list(int(y) for y in ys_primary[:10]),
                "states_head": [st.as_public_dict() for st in states[:10]],
                "events_head": [ev_to_dict(e) for e in events[:10]],
                "cross_window": {
                    "cross_event_index": cross_idx,
                    "states": cross_states,
                    "events": cross_events,
                },
                "trace_summary": {
                    "information_height_in_building_max": int(
                        max(int(st.information_height.current_building_height) for st in states)
                    ),
                    "information_height_in_building_final": int(
                        states[-1].information_height.current_building_height
                    ),
                    "step_count_final": int(states[-1].tc),
                },
                "cross_domain_audit_example": {
                    "max_abs_quotient_along_trajectory": max_abs_q,
                    "snapshot_count_at_final": snap_count,
                    "quotient_at_final": int(
                        states[-1].information_height.cross_domain_reencoding_quotient
                    ),
                    "cross_building_event_count_final": int(
                        states[-1].information_height.cross_building_event_count
                    ),
                    "building_exit_snapshots": [
                        {
                            "building_label": r.floor,
                            "modulus_q": r.q,
                            "representative_w": r.w,
                            "time_counter": r.tc,
                            "value_x": r.x,
                            "state_value_encoding": getattr(
                                r,
                                "state_value_encoding",
                                "scalar",
                            ),
                            "lane_count": int(getattr(r, "lane_count", 1)),
                            "building_height_at_exit": r.building_height_at_exit,
                        }
                        for r in states[-1].information_height.building_exit_snapshots
                    ],
                    "note": "璺ㄦゼ鍙璁★細浣跨敤 cross_domain_reencoding_quotient 涓?building_exit_snapshots 鍏ㄩ噺",
                },
                "mechanism_side_metrics": mechanism_side
                if threat_model_level != ThreatModelLevel.threat_model_1_black_box
                else None,
                "pattern_side_metrics": pattern_side
                if threat_model_level != ThreatModelLevel.threat_model_1_black_box
                else None,
                "projection_metrics": projection_metrics.as_dict(),
            }
            if is_vector_state_space and callable(getattr(cipher, "index_to_lanes", None)):
                example["initial_state_lanes"] = list(
                    int(v) for v in cipher.index_to_lanes(int(x0))
                )

    _, evs0 = run_trace_from_state_index(
        runner=cipher,
        state_index=0,
        run_config=run_config,
    )
    total_steps = len(evs0)

    if threat_model_level == ThreatModelLevel.threat_model_1_black_box:
        confidence_intervals = {
            "projection_collision_rate": bootstrap_ci(
                collision_rates,
                seed=run_config.seed ^ 0xA11D1,
                iters=run_config.bootstrap_iters,
            ),
            "self_intersection_rate": bootstrap_ci(
                self_intersection_rates,
                seed=run_config.seed ^ 0xA11D2,
                iters=run_config.bootstrap_iters,
            ),
            "occupancy_rate": bootstrap_ci(
                occupancy_rates,
                seed=run_config.seed ^ 0xA11D3,
                iters=run_config.bootstrap_iters,
            )
            if occupancy_rates
            else {
                "mean": float("nan"),
                "lower_bound": float("nan"),
                "upper_bound": float("nan"),
            },
            "observation_self_loop_rate": bootstrap_ci(
                observation_self_loop_rates,
                seed=run_config.seed ^ 0xA11D7,
                iters=run_config.bootstrap_iters,
            ),
            "observation_self_intersection_rate": bootstrap_ci(
                observation_self_intersection_rates,
                seed=run_config.seed ^ 0xA11D8,
                iters=run_config.bootstrap_iters,
            ),
        }
    else:
        confidence_intervals = {
            "wrap_event_rate": bootstrap_ci(
                wrap_rates,
                seed=run_config.seed ^ 0xA11CE,
                iters=run_config.bootstrap_iters,
            )
            if wrap_rates
            else {
                "mean": float("nan"),
                "lower_bound": float("nan"),
                "upper_bound": float("nan"),
            },
            "trivial_self_loop_rate": bootstrap_ci(
                sl_rates,
                seed=run_config.seed ^ 0xA11CF,
                iters=run_config.bootstrap_iters,
            )
            if sl_rates
            else {
                "mean": float("nan"),
                "lower_bound": float("nan"),
                "upper_bound": float("nan"),
            },
            "nontrivial_self_loop_rate": bootstrap_ci(
                nsl_rates,
                seed=run_config.seed ^ 0xA11D0,
                iters=run_config.bootstrap_iters,
            )
            if nsl_rates
            else {
                "mean": float("nan"),
                "lower_bound": float("nan"),
                "upper_bound": float("nan"),
            },
            "projection_collision_rate": bootstrap_ci(
                collision_rates,
                seed=run_config.seed ^ 0xA11D1,
                iters=run_config.bootstrap_iters,
            ),
            "self_intersection_rate": bootstrap_ci(
                self_intersection_rates,
                seed=run_config.seed ^ 0xA11D2,
                iters=run_config.bootstrap_iters,
            ),
            "occupancy_rate": bootstrap_ci(
                occupancy_rates,
                seed=run_config.seed ^ 0xA11D3,
                iters=run_config.bootstrap_iters,
            ),
            "coverage_rate": bootstrap_ci(
                coverage_rates,
                seed=run_config.seed ^ 0xA11D4,
                iters=run_config.bootstrap_iters,
            ),
            "information_height_in_building_max": bootstrap_ci(
                ih_in_maxes,
                seed=run_config.seed ^ 0xA11D5,
                iters=run_config.bootstrap_iters,
            ),
            "information_height_in_building_final": bootstrap_ci(
                ih_in_finals,
                seed=run_config.seed ^ 0xA11D6,
                iters=run_config.bootstrap_iters,
            ),
            "observation_self_loop_rate": bootstrap_ci(
                observation_self_loop_rates,
                seed=run_config.seed ^ 0xA11D7,
                iters=run_config.bootstrap_iters,
            ),
            "observation_self_intersection_rate": bootstrap_ci(
                observation_self_intersection_rates,
                seed=run_config.seed ^ 0xA11D8,
                iters=run_config.bootstrap_iters,
            ),
        }

    result: Dict[str, Any] = {
        "config": asdict(run_config),
        "visibility": {"threat_model_level": threat_model_level.value},
        "sampling": {
            "mode": "exhaustive" if run_config.exhaustive else "random",
            "trace_count_effective": len(state_indices),
            "state_index_space_size": int(state_space_size),
            "state_space_semantics": ("omega_power_n" if is_vector_state_space else "z_q"),
        },
        "evidence_objects": [],
        "witnesses": [],
        "cipher": {
            "name": "ToyARX",
            "word_bits": run_config.word_bits,
            "rounds": run_config.rounds,
            "rotation_mode": run_config.rotation_mode,
            "rotation_direction": run_config.rotation_direction,
            "projection": run_config.projection,
            "cross_domain_modulus": run_config.cross_domain_modulus,
            "cross_every_rounds": run_config.cross_every_rounds,
        },
        "bootstrap_confidence_intervals": confidence_intervals,
        "example_trace": example,
        "evidence_interface": {
            "raw_trace_object_schema": "RawTraceObject(observations, projection_spec)",
            "extractor_family": "default_threat_model_1_extractor_family",
            "witness_object_schema": "WitnessObject(config, E, Z, evidence_map)",
        },
        "slice_shadow_metrics": compute_slice_shadow_metrics(ys_all).as_dict(),
        "non_degeneracy_report": compute_non_degeneracy_report(
            projection_unique_node_counts=projection_unique_node_counts,
            projection_step_counts=projection_step_counts,
            coverage_rates=coverage_rates,
        ).as_dict(),
    }
    result["performance_budget"] = compute_block_performance_budget_report(
        run_config=run_config,
        sampling_mode=("exhaustive" if run_config.exhaustive else "random"),
        trace_count_effective=len(state_indices),
    ).as_dict()

    if threat_model_level != ThreatModelLevel.threat_model_1_black_box:
        result["cross_domain_summary"] = {
            "total_atomic_steps_per_trace": total_steps,
            "cross_domain_enabled": bool(run_config.cross_domain_modulus),
        }
        result["core_coverage"] = {
            "omega_core_size": omega_core_size,
            "coverage_rate_mean": (sum(coverage_rates) / len(coverage_rates))
            if coverage_rates
            else float("nan"),
        }
        if max_abs_quotient_per_trace or snapshot_count_per_trace:
            result["cross_domain_audit"] = {
                "max_abs_quotient_mean": float(mean(max_abs_quotient_per_trace))
                if max_abs_quotient_per_trace
                else float("nan"),
                "max_abs_quotient_max": float(max(max_abs_quotient_per_trace))
                if max_abs_quotient_per_trace
                else float("nan"),
                "snapshot_count_mean": float(mean(snapshot_count_per_trace))
                if snapshot_count_per_trace
                else float("nan"),
                "snapshot_count_max": int(max(snapshot_count_per_trace))
                if snapshot_count_per_trace
                else 0,
                "trace_count": len(max_abs_quotient_per_trace),
                "note": "璺ㄦゼ鍙璁★細浣跨敤 cross_domain_reencoding_quotient 涓?building_exit_snapshots锛汸6 鐥呯伓鎹鏍℃簴",
            }
        if winding_trajectory_reports:
            result["winding_trajectory_profile"] = aggregate_winding_trajectory_reports(
                winding_trajectory_reports
            )
            result["winding_trajectory_example"] = winding_trajectory_reports[0]
        if (
            getattr(cipher, "substitution_table", None) is not None
            and getattr(cipher, "bit_permutation", None) is not None
        ):
            from ..metrics.structure_height import build_structure_evidence

            q = int(cipher.domain.q)
            w = int(cipher.domain.w)
            sbox_out = [w + int(cipher.substitution_table[t]) for t in range(q)]
            bit_perm = list(cipher.bit_permutation)

            def pbox_apply(x: int) -> int:
                x = int(x) & (q - 1)
                out = 0
                for j, pj in enumerate(bit_perm):
                    out |= ((x >> pj) & 1) << j
                return out

            pbox_out = [pbox_apply(t) for t in range(q)]
            ev_sbox = build_structure_evidence("sbox", sbox_out, q, w)
            ev_pbox = build_structure_evidence("pbox", pbox_out, q, w)
            result["structure_height_sbox"] = dict(ev_sbox.summary)
            result["structure_height_pbox"] = {
                **ev_pbox.summary,
                "inv_count": ev_pbox.tangle["inv_count"],
                "inversion_norm": ev_pbox.tangle["inversion_norm"],
                "inv_parity": ev_pbox.tangle["inv_parity"],
            }

    return BlockCoreArtifacts(
        result=result,
        cipher=cipher,
        registered_projections=list(registered_projections),
        primary_projection_spec=str(primary_projection_spec),
        projection=proj,
        state_indices=[int(x) for x in state_indices],
        total_steps=int(total_steps),
        omega_core_size=int(omega_core_size),
        empirical_adjacency=empirical_adjacency,
        empirical_sources=empirical_sources,
        edge_counts_total=dict(edge_counts_total),
        region_agg_total=dict(region_agg_total),
        ys_all=[list(int(v) for v in ys) for ys in ys_all],
        max_abs_quotient_per_trace=[float(v) for v in max_abs_quotient_per_trace],
        snapshot_count_per_trace=[int(v) for v in snapshot_count_per_trace],
    )


__all__ = [
    "BlockCoreArtifacts",
    "compute_block_core_artifacts",
    "observed_space_size_from_projection",
]
