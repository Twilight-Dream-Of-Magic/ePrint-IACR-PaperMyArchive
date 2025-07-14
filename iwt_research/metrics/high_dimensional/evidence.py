from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Tuple


def compute_reachability_evidence_for_bijection(
    *,
    successor_of_index: Callable[[int], int],
    state_count: int,
    source_index: int,
    target_indices: List[int],
    max_witness_steps: int = 256,
) -> Dict[str, Any]:
    """
    Evidence-grade reachability output for the bijection/permutation case (small exhaustive).

    Adds two directly-citable proof artifacts:
    - Unreachability certificate: (source_cycle_id, target_cycle_id, cycle lengths) showing "not in same cycle".
    - Path witness: explicit iteration sequence (possibly truncated) + SHA-256 hash checkpoints for auditing.

    In a bijection functional graph (a permutation), forward reachability from a source holds iff
    the target is on the same directed cycle as the source.
    Uses iwt_core (C++23) for iteration/cycle/path; Python builds SHA commitments and final dict.
    """
    n = int(state_count)
    source = int(source_index)
    if n <= 0:
        raise ValueError("state_count must be positive")
    if source < 0 or source >= n:
        raise ValueError("source_index out of range")

    max_witness_steps = max(0, int(max_witness_steps))

    try:
        from ...native import available as _native_available, iwt_core

        if _native_available and iwt_core is not None:
            successor_table = [int(successor_of_index(i)) for i in range(n)]
            core_results = iwt_core.compute_reachability_evidence_core(
                successor_table, n, source, [int(t) for t in target_indices], max_witness_steps,
            )
            targets_out = []
            for r in core_results:
                if r.target_index < 0 or r.target_index >= n:
                    targets_out.append({
                        "target_index": int(r.target_index),
                        "reachable_by_forward_iteration": False,
                        "steps_if_reachable": None,
                        "cycle_certificate": None,
                        "path_witness": None,
                    })
                    continue
                same_cycle = bool(r.reachable_by_forward_iteration)
                path_witness = None
                if same_cycle and r.path_indices_head:
                    digest = hashlib.sha256()
                    digest_at_cut = None
                    for step_index, node in enumerate(r.path_indices_head):
                        digest.update(f"{int(node)}\n".encode("utf-8"))
                        if step_index == max_witness_steps:
                            digest_at_cut = digest.hexdigest()
                    digest_final = digest.hexdigest()
                    steps_total = int(r.steps_if_reachable) if r.steps_if_reachable is not None else None
                    truncated = steps_total is not None and steps_total > max_witness_steps
                    path_witness = {
                        "reachable": True,
                        "steps_total": steps_total,
                        "path_indices_head": [int(x) for x in r.path_indices_head],
                        "truncated": truncated,
                        "cut_step": int(max_witness_steps) if truncated else None,
                        "hash_checkpoints": {
                            "algorithm": "sha256",
                            "encoding": "utf-8 lines of decimal indices with trailing newline",
                            "digest_at_cut": digest_at_cut if truncated else None,
                            "digest_final": digest_final,
                        },
                    }
                elif not same_cycle:
                    path_witness = {
                        "reachable": False,
                        "steps_total": None,
                        "path_indices_head": [int(x) for x in r.path_indices_head],
                        "truncated": False,
                        "cut_step": None,
                        "hash_checkpoints": None,
                    }

                def _commitment_from_cycle_nodes(nodes: List[int], cycle_id: int, cycle_length: int) -> Dict[str, Any]:
                    digest = hashlib.sha256()
                    for node in nodes:
                        digest.update(f"{int(node)}\n".encode("utf-8"))
                    return {
                        "cycle_id": int(cycle_id),
                        "cycle_length": int(cycle_length),
                        "commitment": {
                            "algorithm": "sha256",
                            "encoding": "utf-8 lines of decimal indices with trailing newline",
                            "digest": digest.hexdigest(),
                        },
                        "cycle_nodes_head": list(int(x) for x in nodes[: min(32, len(nodes))]),
                        "cycle_nodes_head_note": "head only; use commitment digest + (cycle_id,cycle_length) as a citable fingerprint",
                    }

                source_commitment = _commitment_from_cycle_nodes(
                    list(r.source_cycle_nodes), int(r.source_cycle_id), int(r.source_cycle_length),
                )
                target_commitment = _commitment_from_cycle_nodes(
                    list(r.target_cycle_nodes), int(r.target_cycle_id), int(r.target_cycle_length),
                )

                targets_out.append({
                    "target_index": int(r.target_index),
                    "reachable_by_forward_iteration": same_cycle,
                    "steps_if_reachable": int(r.steps_if_reachable) if r.steps_if_reachable is not None else None,
                    "cycle_certificate": {
                        "certificate_type": "cycle_separation_on_bijection",
                        "same_cycle": same_cycle,
                        "source_cycle_id": int(r.source_cycle_id),
                        "target_cycle_id": int(r.target_cycle_id),
                        "source_cycle_length": int(r.source_cycle_length),
                        "target_cycle_length": int(r.target_cycle_length),
                        "source_cycle_commitment": source_commitment,
                        "target_cycle_commitment": target_commitment,
                        "note": "On a bijection/permutation functional graph, forward reachability holds iff source and target are on the same directed cycle.",
                    },
                    "path_witness": path_witness,
                })
            return {"state_count": n, "source_index": source, "targets": targets_out}
    except Exception:
        pass

    cycle_info_cache: Dict[int, Tuple[int, int]] = {}

    def _cycle_info(index: int) -> Tuple[int, int]:
        idx = int(index)
        if idx in cycle_info_cache:
            return cycle_info_cache[idx]
        if idx < 0 or idx >= n:
            raise ValueError("index out of range")

        seen_at: Dict[int, int] = {}
        order: List[int] = []
        current = idx
        while True:
            if current < 0 or current >= n:
                raise ValueError("successor_of_index returned out-of-range index")
            if current in seen_at:
                cycle_start = int(seen_at[current])
                cycle_nodes = order[cycle_start:]
                if not cycle_nodes:
                    cycle_nodes = [current]
                cycle_id = int(min(cycle_nodes))
                cycle_len = int(len(cycle_nodes))
                for node in cycle_nodes:
                    cycle_info_cache[int(node)] = (cycle_id, cycle_len)
                if idx not in cycle_info_cache:
                    cycle_info_cache[idx] = (cycle_id, cycle_len)
                return cycle_info_cache[idx]
            seen_at[current] = int(len(order))
            order.append(int(current))
            current = int(successor_of_index(int(current)))

    source_cycle_id, source_cycle_len = _cycle_info(source)

    def _cycle_nodes_and_commitment(cycle_id: int, cycle_len: int) -> Dict[str, Any]:
        cid = int(cycle_id)
        clen = int(cycle_len)
        nodes: List[int] = []
        current = cid
        for _ in range(max(0, clen)):
            nodes.append(int(current))
            current = int(successor_of_index(int(current)))
        digest = hashlib.sha256()
        for node in nodes:
            digest.update(f"{int(node)}\n".encode("utf-8"))
        return {
            "cycle_id": int(cid),
            "cycle_length": int(clen),
            "commitment": {
                "algorithm": "sha256",
                "encoding": "utf-8 lines of decimal indices with trailing newline",
                "digest": digest.hexdigest(),
            },
            "cycle_nodes_head": list(int(x) for x in nodes[: min(32, len(nodes))]),
            "cycle_nodes_head_note": "head only; use commitment digest + (cycle_id,cycle_length) as a citable fingerprint",
        }

    def _path_witness_to_target(target: int) -> Dict[str, Any]:
        t = int(target)
        h = hashlib.sha256()
        digest_at_cut: str | None = None
        path_head: List[int] = []
        current = int(source)
        for step in range(n + 1):
            h.update(f"{current}\n".encode("utf-8"))
            if step <= max_witness_steps:
                path_head.append(int(current))
                if step == max_witness_steps:
                    digest_at_cut = h.hexdigest()
            if current == t:
                digest_final = h.hexdigest()
                truncated = bool(step > max_witness_steps)
                return {
                    "reachable": True,
                    "steps_total": int(step),
                    "path_indices_head": list(int(x) for x in path_head),
                    "truncated": truncated,
                    "cut_step": int(max_witness_steps) if truncated else None,
                    "hash_checkpoints": {
                        "algorithm": "sha256",
                        "encoding": "utf-8 lines of decimal indices with trailing newline",
                        "digest_at_cut": digest_at_cut if truncated else None,
                        "digest_final": digest_final,
                    },
                }
            current = int(successor_of_index(int(current)))
            if current == int(source):
                break
        return {
            "reachable": False,
            "steps_total": None,
            "path_indices_head": list(int(x) for x in path_head),
            "truncated": False,
            "cut_step": None,
            "hash_checkpoints": None,
        }

    targets_out: List[Dict[str, Any]] = []
    for target in target_indices:
        t = int(target)
        if t < 0 or t >= n:
            targets_out.append(
                {
                    "target_index": t,
                    "reachable_by_forward_iteration": False,
                    "steps_if_reachable": None,
                    "cycle_certificate": None,
                    "path_witness": None,
                }
            )
            continue

        target_cycle_id, target_cycle_len = _cycle_info(t)
        same_cycle = bool(int(target_cycle_id) == int(source_cycle_id))
        path_witness = _path_witness_to_target(t) if same_cycle else None
        source_cycle_commitment = _cycle_nodes_and_commitment(int(source_cycle_id), int(source_cycle_len))
        target_cycle_commitment = _cycle_nodes_and_commitment(int(target_cycle_id), int(target_cycle_len))
        targets_out.append(
            {
                "target_index": t,
                "reachable_by_forward_iteration": bool(same_cycle),
                "steps_if_reachable": int(path_witness["steps_total"]) if (path_witness and path_witness.get("reachable")) else None,
                "cycle_certificate": {
                    "certificate_type": "cycle_separation_on_bijection",
                    "same_cycle": bool(same_cycle),
                    "source_cycle_id": int(source_cycle_id),
                    "target_cycle_id": int(target_cycle_id),
                    "source_cycle_length": int(source_cycle_len),
                    "target_cycle_length": int(target_cycle_len),
                    "source_cycle_commitment": source_cycle_commitment,
                    "target_cycle_commitment": target_cycle_commitment,
                    "note": "On a bijection/permutation functional graph, forward reachability holds iff source and target are on the same directed cycle.",
                },
                "path_witness": path_witness,
            }
        )

    return {
        "state_count": int(n),
        "source_index": int(source),
        "targets": targets_out,
    }


__all__ = ["compute_reachability_evidence_for_bijection"]
