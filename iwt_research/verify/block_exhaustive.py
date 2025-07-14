from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from ..ciphers.runner_factory import build_toy_cipher_from_config
from .result import VerificationResult

def _sha256_lines_decimal(values: List[int]) -> str:
    h = hashlib.sha256()
    for v in values:
        h.update(f"{int(v)}\n".encode("utf-8"))
    return h.hexdigest()

def verify_exhaustive_bijection_proof_artifacts(report: Dict[str, Any]) -> VerificationResult:
    """
    Verify cycle commitments and path witnesses emitted by:
      high_dimensional_metrics.reachability_queries_exhaustive
      high_dimensional_metrics.proof_witnesses_exhaustive
      high_dimensional_metrics.cycle_decomposition_exhaustive_single_word
      high_dimensional_metrics.reachability_queries_exhaustive_single_word

    Scope:
    - toy_spn_vector: Omega^n bijection (cycle + path witness verification).
    - toy_arx / toy_spn: Z_q single-word exhaustive (cycle decomposition + optional reachability).
    """
    failures: List[str] = []
    checked = 0

    report_config = report.get("config", {}) if isinstance(report, dict) else {}
    preset = str(report_config.get("cipher_preset", "")).strip().lower()
    if not bool(report_config.get("exhaustive", False)):
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: not exhaustive"])

    high_dimensional_metrics = report.get("high_dimensional_metrics", {}) if isinstance(report, dict) else {}
    # Single-word (Z_q) exhaustive verification for toy_arx / toy_spn.
    if preset in ("toy_arx", "toy_spn", "toy_substitution_permutation_network"):
        cycle_single = high_dimensional_metrics.get("cycle_decomposition_exhaustive_single_word", {}) if isinstance(high_dimensional_metrics, dict) else {}
        reach_single = high_dimensional_metrics.get("reachability_queries_exhaustive_single_word", {}) if isinstance(high_dimensional_metrics, dict) else {}
        if not isinstance(cycle_single, dict) or not cycle_single.get("state_count", 0):
            return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: no single_word exhaustive data"])
        try:
            cipher = build_toy_cipher_from_config(report_config)
        except Exception:
            return VerificationResult(ok=False, checked_count=0, failed_count=1, failures=["single_word: failed to build cipher"])
        q_single = int(cipher.domain.q)

        def successor_of_index_single(i: int) -> int:
            states_run, _ = cipher.run(int(i))
            return int(states_run[-1].x)

        from ..metrics.high_dimensional import compute_cycle_decomposition_metrics_for_bijection
        recomputed = compute_cycle_decomposition_metrics_for_bijection(
            successor_of_index=successor_of_index_single,
            state_count=q_single,
        )
        if int(recomputed.cycle_count) != int(cycle_single.get("cycle_count", -1)):
            failures.append(f"single_word: cycle_count mismatch (got {recomputed.cycle_count}, report {cycle_single.get('cycle_count')})")
        if int(recomputed.max_cycle_length) != int(cycle_single.get("max_cycle_length", -1)):
            failures.append(f"single_word: max_cycle_length mismatch (got {recomputed.max_cycle_length}, report {cycle_single.get('max_cycle_length')})")
        if int(recomputed.fixed_point_count) != int(cycle_single.get("fixed_point_count", -1)):
            failures.append(f"single_word: fixed_point_count mismatch (got {recomputed.fixed_point_count}, report {cycle_single.get('fixed_point_count')})")
        checked += 1
        # Optionally verify reachability cycle certificates if present.
        if isinstance(reach_single, dict) and isinstance(reach_single.get("targets"), list):
            for item in reach_single["targets"]:
                if not isinstance(item, dict):
                    continue
                cert = item.get("cycle_certificate", None)
                if not isinstance(cert, dict):
                    continue
                for which in ("source_cycle_commitment", "target_cycle_commitment"):
                    cc = cert.get(which, None)
                    if not isinstance(cc, dict) or not isinstance(cc.get("commitment"), dict):
                        continue
                    cid = int(cc.get("cycle_id", -1))
                    clen = int(cc.get("cycle_length", -1))
                    if cid < 0 or clen <= 0 or cid >= q_single:
                        continue
                    nodes: List[int] = []
                    cur = cid
                    for _ in range(clen):
                        nodes.append(int(cur))
                        cur = int(successor_of_index_single(int(cur)))
                    digest_report = cc.get("commitment", {}).get("digest", None)
                    digest_recomputed = _sha256_lines_decimal(nodes)
                    if str(digest_report) != str(digest_recomputed):
                        failures.append(f"single_word target {item.get('target_index')} {which}: digest mismatch")
                    checked += 1
        return VerificationResult(ok=(len(failures) == 0), checked_count=checked, failed_count=len(failures), failures=failures)

    if preset not in ("toy_spn_vector", "toy_substitution_permutation_network_vector"):
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=["skip: preset not supported"])

    word_bits = int(report_config.get("word_bits", 0) or 0)
    lane_count = int(report_config.get("lane_count", 0) or 0)
    rounds = int(report_config.get("rounds", 0) or 0)
    seed = int(report_config.get("seed", 0) or 0)

    cipher = build_toy_cipher_from_config(
        {
            "cipher_preset": preset,
            "word_bits": int(word_bits),
            "lane_count": int(lane_count),
            "rounds": int(rounds),
            "seed": int(seed),
        }
    )

    def successor_of_index(index: int) -> int:
        lanes = cipher.index_to_lanes(int(index))
        states_tmp, _ = cipher.run_from_lanes(lanes)
        final_lanes = tuple(states_tmp[-1].x)  # type: ignore[arg-type]
        return int(cipher.lanes_to_index(final_lanes))

    total_state_count = int(cipher.domain.q) ** int(lane_count)

    def compute_cycle_nodes(cycle_id: int, cycle_len: int) -> List[int]:
        nodes: List[int] = []
        current = int(cycle_id)
        for _ in range(int(cycle_len)):
            nodes.append(int(current))
            current = int(successor_of_index(int(current)))
        return nodes

    high_dimensional_metrics = report.get("high_dimensional_metrics", {}) if isinstance(report, dict) else {}
    reach = high_dimensional_metrics.get("reachability_queries_exhaustive", {}) if isinstance(high_dimensional_metrics, dict) else {}
    targets = reach.get("targets", []) if isinstance(reach, dict) else []

    for item in targets:
        if not isinstance(item, dict):
            continue
        t = item.get("target_index", None)
        cert = item.get("cycle_certificate", None)
        pw = item.get("path_witness", None)

        if not isinstance(cert, dict):
            failures.append(f"target {t}: missing cycle_certificate")
            continue

        checked += 1
        for which in ("source_cycle_commitment", "target_cycle_commitment"):
            cc = cert.get(which, None)
            if not isinstance(cc, dict):
                failures.append(f"target {t}: missing {which}")
                continue
            cycle_id = int(cc.get("cycle_id", -1))
            cycle_len = int(cc.get("cycle_length", -1))
            digest = None
            if isinstance(cc.get("commitment", None), dict):
                digest = cc.get("commitment", {}).get("digest", None)
            if digest is None:
                failures.append(f"target {t}: missing digest in {which}")
                continue
            if cycle_id < 0 or cycle_len <= 0 or cycle_id >= total_state_count:
                failures.append(f"target {t}: invalid cycle_id/len in {which}")
                continue
            nodes = compute_cycle_nodes(cycle_id, cycle_len)
            recomputed = _sha256_lines_decimal(nodes)
            if str(recomputed) != str(digest):
                failures.append(f"target {t}: digest mismatch in {which}")

        reachable = bool(item.get("reachable_by_forward_iteration", False))
        if reachable:
            if not isinstance(pw, dict):
                failures.append(f"target {t}: reachable but missing path_witness")
                continue
            steps_total = int(pw.get("steps_total", -1))
            if steps_total < 0 or steps_total > total_state_count + 1:
                failures.append(f"target {t}: invalid steps_total")
                continue
            # Verify head path consistency.
            head = pw.get("path_indices_head", [])
            if not isinstance(head, list) or not head:
                failures.append(f"target {t}: missing path_indices_head")
                continue
            source_index = int(reach.get("source_index", 0) or 0)
            if int(head[0]) != int(source_index):
                failures.append(f"target {t}: head[0] != source_index")
            for i in range(len(head) - 1):
                a = int(head[i])
                b = int(head[i + 1])
                if int(successor_of_index(a)) != int(b):
                    failures.append(f"target {t}: head edge mismatch at i={i}")
                    break
            # Verify digest checkpoints.
            hc = pw.get("hash_checkpoints", None)
            if not isinstance(hc, dict):
                failures.append(f"target {t}: missing hash_checkpoints")
                continue
            digest_final = hc.get("digest_final", None)
            if digest_final is None:
                failures.append(f"target {t}: missing digest_final")
                continue
            # Recompute full path hash by iterating from source to target.
            current = int(source_index)
            full: List[int] = []
            for step in range(total_state_count + 2):
                full.append(int(current))
                if int(current) == int(t):
                    break
                current = int(successor_of_index(int(current)))
            if int(full[-1]) != int(t):
                failures.append(f"target {t}: could not reach target when recomputing")
                continue
            recomputed_final = _sha256_lines_decimal(full)
            if str(recomputed_final) != str(digest_final):
                failures.append(f"target {t}: digest_final mismatch")

    return VerificationResult(
        ok=(len(failures) == 0),
        checked_count=int(checked),
        failed_count=int(len(failures)),
        failures=failures,
    )
