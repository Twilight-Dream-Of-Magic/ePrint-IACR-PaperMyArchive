from __future__ import annotations

from typing import Any, Dict, List

from ..core.discrete_domain import compute_binary_hypercube_metrics
from ..evidence.objects import EvidenceObject, WitnessObject
from ..metrics.high_dimensional import (
    compute_cycle_decomposition_metrics_for_bijection,
    compute_empirical_reachability_metrics,
    compute_lane_coupling_matrix,
    compute_neighbor_separation_metrics,
    compute_reachability_evidence_for_bijection,
)
from ..run_helpers import parse_int_csv
from .config import RunConfig
from .types import ExhaustiveArtifacts, RunArtifacts


def compute_exhaustive_artifacts(
    *,
    run_config: RunConfig,
    cipher: Any,
    empirical_adjacency: Dict[Any, set[Any]] | None = None,
    empirical_sources: List[Any] | None = None,
) -> ExhaustiveArtifacts:
    high_dimensional: Dict[str, Any] = {}
    proof_evidence_objects: List[Dict[str, Any]] = []
    proof_witnesses: List[Dict[str, Any]] = []

    if run_config.cipher_preset in ("toy_arx", "toy_spn", "toy_substitution_permutation_network"):
        q_single = int(cipher.domain.q)
        if run_config.exhaustive and q_single <= int(run_config.max_exhaustive_modulus):
            def successor_of_index_single(i: int) -> int:
                states_run, _ = cipher.run(int(i))
                return int(states_run[-1].x)

            state_count_single = q_single
            cycle_single = compute_cycle_decomposition_metrics_for_bijection(
                successor_of_index=successor_of_index_single,
                state_count=state_count_single,
            ).as_dict()
            cycle_single["scope"] = "single_word"
            target_indices_single = (
                [0, 1, 2, 3, state_count_single // 2, state_count_single - 1]
                if state_count_single >= 4
                else list(range(state_count_single))
            )
            reach_single = compute_reachability_evidence_for_bijection(
                successor_of_index=successor_of_index_single,
                state_count=state_count_single,
                source_index=0,
                target_indices=target_indices_single,
                max_witness_steps=256,
            )
            high_dimensional = {
                "cycle_decomposition_exhaustive_single_word": cycle_single,
                "reachability_queries_exhaustive_single_word": reach_single,
                "scope": "single_word",
                "note": "Exhaustive cycle decomposition and reachability on Z_q (single-word state space).",
            }
        return ExhaustiveArtifacts(
            high_dimensional=high_dimensional,
            proof_evidence_objects=proof_evidence_objects,
            proof_witnesses=proof_witnesses,
        )

    if run_config.cipher_preset not in ("toy_spn_vector", "toy_substitution_permutation_network_vector"):
        return ExhaustiveArtifacts(
            high_dimensional=high_dimensional,
            proof_evidence_objects=proof_evidence_objects,
            proof_witnesses=proof_witnesses,
        )

    def successor_of_index(index: int) -> int:
        lanes = cipher.index_to_lanes(int(index))
        states_tmp, _ = cipher.run_from_lanes(lanes)
        final_lanes = tuple(states_tmp[-1].x)  # type: ignore[arg-type]
        return int(cipher.lanes_to_index(final_lanes))

    cycle_decomposition: Dict[str, Any] | None = None
    reachability_queries: Dict[str, Any] | None = None
    total_state_count = int(cipher.domain.q) ** int(run_config.lane_count)
    if run_config.exhaustive and total_state_count <= int(run_config.max_exhaustive_state_count):
        cycle_decomposition = compute_cycle_decomposition_metrics_for_bijection(
            successor_of_index=successor_of_index,
            state_count=total_state_count,
        ).as_dict()
        source_index = 0
        source_cycle_length = 0
        current = int(source_index)
        for step in range(1, int(total_state_count) + 2):
            current = int(successor_of_index(int(current)))
            if current == int(source_index):
                source_cycle_length = int(step)
                break
        if source_cycle_length > 0:
            source_strict_unreachable_fraction = 1.0 - (float(source_cycle_length) / float(total_state_count))
        else:
            source_strict_unreachable_fraction = None
        cycle_decomposition["source_index"] = int(source_index)
        cycle_decomposition["source_cycle_length"] = int(source_cycle_length) if source_cycle_length > 0 else None
        cycle_decomposition["source_strict_unreachable_fraction"] = source_strict_unreachable_fraction

        configured_targets = parse_int_csv(run_config.reachability_target_indices_csv)
        if configured_targets:
            target_indices = configured_targets
        else:
            target_indices = (
                [0, 1, 2, 3, total_state_count // 2, total_state_count - 1]
                if total_state_count >= 4
                else list(range(total_state_count))
            )
        reachability_queries = compute_reachability_evidence_for_bijection(
            successor_of_index=successor_of_index,
            state_count=total_state_count,
            source_index=0,
            target_indices=target_indices,
            max_witness_steps=256,
        )

    high_dimensional = {
        "neighbor_separation": compute_neighbor_separation_metrics(
            cipher=cipher,
            seed=run_config.seed ^ 0xC0A11E,
            pair_count=128,
        ).as_dict(),
        "lane_coupling": compute_lane_coupling_matrix(
            cipher=cipher,
            seed=run_config.seed ^ 0xC0A11F,
            samples_per_source_lane=64,
        ),
        "empirical_reachability": compute_empirical_reachability_metrics(
            adjacency=empirical_adjacency or {},
            sources=empirical_sources or [],
        ).as_dict(),
        "cycle_decomposition_exhaustive": cycle_decomposition,
        "reachability_queries_exhaustive": reachability_queries,
        "note": "High-dimensional signatures are computed on Omega^n (vector lanes), independent of the projection Pi unless stated otherwise.",
    }
    if bool(cipher.domain.is_binary):
        high_dimensional["binary_hypercube_geometry"] = compute_binary_hypercube_metrics(
            domain=cipher.domain,
            adjacency=empirical_adjacency or {},
            dimension=int(run_config.lane_count),
        ).as_dict()

    if isinstance(reachability_queries, dict) and isinstance(reachability_queries.get("targets", None), list):
        for item in reachability_queries["targets"]:
            if not isinstance(item, dict):
                continue
            t_idx = item.get("target_index", None)
            reachable = bool(item.get("reachable_by_forward_iteration", False))
            steps = item.get("steps_if_reachable", None)
            cert = item.get("cycle_certificate", None)
            path_w = item.get("path_witness", None)
            witness = WitnessObject(
                config={
                    "mode": "exhaustive_bijection_functional_graph",
                    "state_count": int(reachability_queries.get("state_count", 0) or 0),
                    "source_index": int(reachability_queries.get("source_index", 0) or 0),
                    "target_index": t_idx,
                },
                E={
                    "reachable_by_forward_iteration": bool(reachable),
                    "steps_if_reachable": steps,
                },
                Z={
                    "cycle_certificate": cert,
                    "path_witness": path_w,
                },
                evidence_map={
                    "cycle_certificate": cert,
                    "path_witness": path_w,
                    "note": "For bijections/permutations, unreachability is certified by cycle separation; reachability witness is the explicit forward-iteration path.",
                },
            ).as_dict()
            proof_witnesses.append(witness)
            proof_evidence_objects.append(
                EvidenceObject(
                    identifier=f"exhaustive_reachability::{t_idx}",
                    summary="Exhaustive reachability evidence on a bijection functional graph (cycle certificate + optional path witness).",
                    value={
                        "target_index": t_idx,
                        "reachable_by_forward_iteration": bool(reachable),
                        "steps_if_reachable": steps,
                    },
                    p_value=None,
                    witness=witness,
                    metadata={
                        "cipher_preset": str(run_config.cipher_preset),
                        "requires_exhaustive": True,
                        "note": "This is a proof artifact for small state spaces; not a TM-1 black-box claim.",
                    },
                ).as_dict()
            )
        high_dimensional["proof_evidence_objects_exhaustive"] = proof_evidence_objects
        high_dimensional["proof_witnesses_exhaustive"] = proof_witnesses

    return ExhaustiveArtifacts(
        high_dimensional=high_dimensional,
        proof_evidence_objects=proof_evidence_objects,
        proof_witnesses=proof_witnesses,
    )


def attach_exhaustive_analysis(artifacts: RunArtifacts) -> RunArtifacts:
    """
    Attach exhaustive-mode artifacts to the pipeline envelope.

    Computes exhaustive/high-dimensional diagnostics when not already
    materialized in artifacts.result, then normalizes typed views.
    """
    high_dimensional = artifacts.result.get("high_dimensional_metrics", {})
    if not isinstance(high_dimensional, dict) or not high_dimensional:
        cipher = artifacts.working.get("cipher", None)
        if cipher is not None:
            exhaustive = compute_exhaustive_artifacts(
                run_config=artifacts.run_config,
                cipher=cipher,
                empirical_adjacency=artifacts.working.get("empirical_adjacency", None),
                empirical_sources=artifacts.working.get("empirical_sources", None),
            )
            if exhaustive.high_dimensional:
                artifacts.result["high_dimensional_metrics"] = dict(exhaustive.high_dimensional)
                high_dimensional = artifacts.result["high_dimensional_metrics"]
            if exhaustive.proof_evidence_objects and isinstance(
                artifacts.result.get("evidence_objects"),
                list,
            ):
                artifacts.result["evidence_objects"].extend(exhaustive.proof_evidence_objects)
            if exhaustive.proof_witnesses and isinstance(
                artifacts.result.get("witnesses"),
                list,
            ):
                artifacts.result["witnesses"].extend(exhaustive.proof_witnesses)
    proof_evidence = []
    proof_witnesses = []
    if isinstance(high_dimensional, dict):
        raw_evidence = high_dimensional.get("proof_evidence_objects_exhaustive", [])
        raw_witnesses = high_dimensional.get("proof_witnesses_exhaustive", [])
        if isinstance(raw_evidence, list):
            proof_evidence = [x for x in raw_evidence if isinstance(x, dict)]
        if isinstance(raw_witnesses, list):
            proof_witnesses = [x for x in raw_witnesses if isinstance(x, dict)]

    artifacts.exhaustive = ExhaustiveArtifacts(
        high_dimensional=(high_dimensional if isinstance(high_dimensional, dict) else {}),
        proof_evidence_objects=proof_evidence,
        proof_witnesses=proof_witnesses,
    )
    return artifacts


__all__ = ["compute_exhaustive_artifacts", "attach_exhaustive_analysis"]
