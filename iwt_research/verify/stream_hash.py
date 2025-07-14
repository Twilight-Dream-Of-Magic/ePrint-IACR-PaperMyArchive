from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .report_contracts import verify_performance_budget_contract, verify_todo_alignment_mapping
from .result import VerificationResult

STREAM_HASH_EXPERIMENT_TYPES = (
    "stream_cipher_prg",
    "secure_hash_sponge",
    "secure_hash_direct_compression",
)

RHO_STRUCTURE_KEY_FIELDS = (
    "state_count",
    "image_count",
    "collision_count",
    "cycle_count",
    "total_cycle_nodes",
    "tail_node_count",
    "max_tail_length",
    "mean_tail_length",
    "max_in_degree",
    "tree_count",
)


def _verify_rho_structure_recomputation(report: Dict[str, Any]) -> Tuple[VerificationResult, bool]:
    """
    Rebuild direct/sponge from config, recompute rho_structure, compare with report.
    Returns (VerificationResult, is_hash_report). Caller only merges when is_hash_report.
    """
    failures: List[str] = []
    checked = 0
    experiment_type = report.get("experiment_type", None)
    if experiment_type not in ("secure_hash_direct_compression", "secure_hash_sponge"):
        return VerificationResult(ok=True, checked_count=0, failed_count=0, failures=[]), False

    reported_rho = report.get("rho_structure")
    if not isinstance(reported_rho, dict):
        return VerificationResult(
            ok=False,
            checked_count=0,
            failed_count=1,
            failures=["hash report missing rho_structure"],
        ), True

    report_config = report.get("config", {})
    if not isinstance(report_config, dict):
        return VerificationResult(
            ok=False,
            checked_count=0,
            failed_count=1,
            failures=["missing config for rho recomputation"],
        ), True

    try:
        if experiment_type == "secure_hash_direct_compression":
            from ..secure_hash.rho_analysis import compute_rho_structure
            from ..secure_hash.toy_sponge import DirectCompression, DirectCompressionConfig

            direct_compression_config = DirectCompressionConfig(
                word_bits=int(report_config.get("word_bits", 8)),
                shift_amount=int(report_config.get("shift_amount", 3)),
                sbox_seed=int(report_config.get("sbox_seed", 42)),
            )
            comp = DirectCompression(direct_compression_config)
            q = comp.state_space_size
            rho = compute_rho_structure(successor=comp.as_successor(), state_count=q)
        else:
            from ..secure_hash.rho_analysis import compute_rho_structure
            from ..secure_hash.toy_sponge import ToySponge, ToySpongeConfig

            sponge_config = ToySpongeConfig(
                cipher_preset=str(report_config.get("cipher_preset", "toy_spn")),
                word_bits=int(report_config.get("word_bits", 8)),
                rounds=int(report_config.get("rounds", 4)),
                cipher_seed=int(report_config.get("cipher_seed", 0)),
                lane_count=int(report_config.get("lane_count", 4)),
                rate_bits=int(report_config.get("rate_bits", 4)),
                capacity_bits=int(report_config.get("capacity_bits", 4)),
            )
            sponge = ToySponge(sponge_config)
            rate_q = sponge.rate_space_size
            fixed_msg = 0

            def successor(cv: int) -> int:
                return sponge.compression_function(cv, fixed_msg)

            rho = compute_rho_structure(successor=successor, state_count=rate_q)
    except Exception as e:
        failures.append(f"rho recomputation failed: {e!s}")
        return VerificationResult(ok=False, checked_count=0, failed_count=len(failures), failures=failures), True

    recomputed = rho.as_dict()
    for key in RHO_STRUCTURE_KEY_FIELDS:
        if key not in recomputed or key not in reported_rho:
            continue
        checked += 1
        rv = recomputed[key]
        ov = reported_rho[key]
        if key == "mean_tail_length":
            if abs(float(rv) - float(ov)) > 1e-6:
                failures.append(f"rho_structure.{key}: recomputed={rv!r} reported={ov!r}")
        else:
            if int(rv) != int(ov):
                failures.append(f"rho_structure.{key}: recomputed={rv!r} reported={ov!r}")

    return VerificationResult(
        ok=(len(failures) == 0),
        checked_count=int(checked),
        failed_count=int(len(failures)),
        failures=failures,
    ), True


def verify_stream_and_hash_report(report: Dict[str, Any]) -> VerificationResult:
    """
    Verify stream/hash report schema and sanity.
    Used when report.experiment_type is stream_cipher_prg or secure_hash_*.
    """
    failures: List[str] = []
    checked = 0

    experiment_type = report.get("experiment_type", None)
    if experiment_type not in STREAM_HASH_EXPERIMENT_TYPES:
        return VerificationResult(
            ok=False,
            checked_count=0,
            failed_count=1,
            failures=["unknown experiment_type for stream/hash verify"],
        )

    if not isinstance(report.get("config"), dict):
        failures.append("missing or invalid config")
    else:
        checked += 1

    if experiment_type == "stream_cipher_prg":
        for key in ("period_detection", "autocorrelation", "coverage", "seed_sensitivity"):
            if key not in report:
                failures.append(f"stream report missing key: {key}")
        if not failures:
            checked += 1
        if "winding_trajectory_profile" in report:
            checked += 1
    else:
        for key in ("rho_structure", "collision_metrics", "avalanche", "merge_depth"):
            if key not in report:
                failures.append(f"hash report missing key: {key}")
        if not failures:
            checked += 1
        if experiment_type == "secure_hash_sponge" and "winding_trajectory_profile" not in report:
            failures.append("sponge report missing winding_trajectory_profile")
        elif experiment_type == "secure_hash_sponge":
            checked += 1
        rho_result, is_hash = _verify_rho_structure_recomputation(report)
        if is_hash:
            checked += rho_result.checked_count
            failures.extend(rho_result.failures)

    if "structural_diagnosis" in report:
        sd = report["structural_diagnosis"]
        if not isinstance(sd, list):
            failures.append("structural_diagnosis must be a list")
        else:
            for i, item in enumerate(sd):
                if not isinstance(item, dict):
                    failures.append(f"structural_diagnosis[{i}] must be a dict")
                else:
                    if ("id" not in item) and ("identifier" not in item):
                        failures.append(f"structural_diagnosis[{i}] missing key: id/identifier")
                        continue
                    for k in ("flag", "value"):
                        if k not in item:
                            failures.append(f"structural_diagnosis[{i}] missing key: {k}")
                            break
            if not failures:
                checked += 1

    return VerificationResult(
        ok=(len(failures) == 0),
        checked_count=int(checked),
        failed_count=int(len(failures)),
        failures=failures,
    )


def load_report_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("report.json must be an object")
    return data
