from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List

from ..analysis.threat_model import threat_model_semantics_payload
from ..evidence.schema_version import EVIDENCE_SCHEMA_VERSION
from ..native import get_native_capability
from .schema_version import REPORT_SCHEMA_VERSION


def _infer_value_type(value: Any) -> str:
    if isinstance(value, (int, float)):
        return "scalar"
    if isinstance(value, dict):
        return "mapping"
    if isinstance(value, list):
        return "sequence"
    return "opaque"


def _ensure_evidence_entries(report: Dict[str, Any], key: str) -> None:
    value = report.get(key, None)
    if not isinstance(value, list):
        return
    for item in value:
        if not isinstance(item, dict):
            continue
        item.setdefault("schema_version", EVIDENCE_SCHEMA_VERSION)
        item.setdefault("value_type", _infer_value_type(item.get("value")))
        item.setdefault("witness_type", "generic_witness")


def _ensure_witness_entries(report: Dict[str, Any], key: str) -> None:
    value = report.get(key, None)
    if not isinstance(value, list):
        return
    for item in value:
        if not isinstance(item, dict):
            continue
        item.setdefault("schema_version", EVIDENCE_SCHEMA_VERSION)
        item.setdefault("witness_type", "structural_witness")


def _default_execution_backend(native_capability: Dict[str, Any]) -> str:
    available = bool(native_capability.get("available", False))
    symbols = native_capability.get("symbols", {})
    if not isinstance(symbols, dict):
        return "python_fallback"
    if available and all(bool(v) for v in symbols.values()):
        return "iwt_core"
    return "python_fallback"


def _compute_atomic_trace_digest(report: Dict[str, Any]) -> str:
    trace_payload: Any = None
    example_trace = report.get("example_trace", None)
    if isinstance(example_trace, dict) and isinstance(example_trace.get("events_head"), list):
        trace_payload = example_trace.get("events_head")
    if trace_payload is None and isinstance(report.get("winding_trajectory_example"), dict):
        trace_payload = report.get("winding_trajectory_example")
    if trace_payload is None:
        trace_payload = {
            "experiment_type": report.get("experiment_type"),
            "no_atomic_trace_payload": True,
        }
    raw = json.dumps(trace_payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_composition_structure_diagnosis(report: Dict[str, Any]) -> Dict[str, Any]:
    high_dimensional = report.get("high_dimensional_metrics", {})
    mechanism_side = report.get("mechanism_side_metrics", {})
    op_families = []
    if isinstance(mechanism_side, dict):
        family_counts = mechanism_side.get("operation_family_counts", {})
        if isinstance(family_counts, dict):
            op_families = sorted(str(k) for k in family_counts.keys())

    lattice_shape = "not_available"
    if isinstance(high_dimensional, dict):
        if "cycle_decomposition_exhaustive" in high_dimensional:
            lattice_shape = "functional_graph_exhaustive_cycle_decomposition"
        elif "empirical_reachability" in high_dimensional:
            lattice_shape = "empirical_reachability_digraph"

    judgement_status = "undetermined"
    if isinstance(report.get("lesions"), list):
        if any(bool(item.get("flag")) for item in report["lesions"] if isinstance(item, dict)):
            judgement_status = "anomalous_structure_detected"
        else:
            judgement_status = "no_lesion_triggered"
    elif isinstance(report.get("structural_diagnosis"), list):
        if any(bool(item.get("flag")) for item in report["structural_diagnosis"] if isinstance(item, dict)):
            judgement_status = "anomalous_structure_detected"
        else:
            judgement_status = "no_structural_warning"

    witness_count = 0
    for key in ("witnesses", "threat_model_1_witnesses", "threat_model_2_witnesses"):
        value = report.get(key, None)
        if isinstance(value, list):
            witness_count += len(value)

    return {
        "high_dimensional_lattice_shape": {
            "shape": lattice_shape,
        },
        "micro_function_connectivity": {
            "operator_families": op_families,
            "operator_family_count": len(op_families),
        },
        "judgement": {
            "status": judgement_status,
        },
        "witnesses": {
            "count": int(witness_count),
        },
    }


def attach_report_contract_metadata(
    report: Dict[str, Any],
    *,
    evidence_keys: Iterable[str] = ("evidence_objects", "threat_model_1_evidence_objects"),
    witness_keys: Iterable[str] = ("witnesses", "threat_model_1_witnesses", "threat_model_2_witnesses"),
) -> Dict[str, Any]:
    report["report_schema_version"] = REPORT_SCHEMA_VERSION
    report["evidence_schema_version"] = EVIDENCE_SCHEMA_VERSION
    native_capability = get_native_capability().as_dict()
    report["native_capability"] = native_capability

    for key in evidence_keys:
        _ensure_evidence_entries(report, key)
    for key in witness_keys:
        _ensure_witness_entries(report, key)

    report.setdefault("execution_backend", _default_execution_backend(native_capability))
    report.setdefault("atomic_trace_digest", _compute_atomic_trace_digest(report))
    report.setdefault("threat_model_semantics", threat_model_semantics_payload())
    report.setdefault(
        "composition_structure_diagnosis",
        _build_composition_structure_diagnosis(report),
    )
    return report
