from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..alignment.todo_alignment import validate_todo_alignment_section
from ..evidence.schema_version import EVIDENCE_SCHEMA_VERSION
from ..native.capability import REQUIRED_NATIVE_SYMBOLS
from ..report.schema_version import REPORT_SCHEMA_VERSION
from .result import VerificationResult


def verify_todo_alignment_mapping(report: Dict[str, Any]) -> VerificationResult:
    failures: List[str] = []
    checked = 0

    todo_alignment = report.get("todo_alignment", None)
    if not isinstance(todo_alignment, dict):
        return VerificationResult(
            ok=False,
            checked_count=0,
            failed_count=1,
            failures=["missing todo_alignment section"],
        )

    checked += 1
    failures.extend(validate_todo_alignment_section(todo_alignment, report.keys()))

    missing_mainlines = todo_alignment.get("missing_mainlines", None)
    if isinstance(missing_mainlines, list) and missing_mainlines:
        failures.append(
            f"todo_alignment has uncovered mainlines: {', '.join(str(x) for x in missing_mainlines)}"
        )
    checked += 1

    return VerificationResult(
        ok=(len(failures) == 0),
        checked_count=int(checked),
        failed_count=int(len(failures)),
        failures=failures,
    )


def verify_performance_budget_contract(report: Dict[str, Any]) -> VerificationResult:
    failures: List[str] = []
    checked = 0

    budget = report.get("performance_budget", None)
    if not isinstance(budget, dict):
        return VerificationResult(
            ok=False,
            checked_count=0,
            failed_count=1,
            failures=["missing performance_budget section"],
        )

    checked += 1
    branch = str(budget.get("branch", "")).strip().lower()
    within_budget = bool(budget.get("within_budget", False))
    if branch not in ("strict_exhaustive", "empirical_sampling"):
        failures.append(f"invalid performance_budget.branch: {branch!r}")
    if not within_budget:
        failures.append("performance_budget.within_budget is false")

    sampling = report.get("sampling", None)
    if isinstance(sampling, dict):
        checked += 1
        mode = str(sampling.get("mode", "")).strip().lower()
        if mode == "exhaustive" and branch != "strict_exhaustive":
            failures.append("sampling.mode=exhaustive but performance_budget.branch is not strict_exhaustive")
        if mode != "exhaustive" and branch != "empirical_sampling":
            failures.append("sampling.mode!=exhaustive but performance_budget.branch is not empirical_sampling")

    return VerificationResult(
        ok=(len(failures) == 0),
        checked_count=int(checked),
        failed_count=int(len(failures)),
        failures=failures,
    )


def _verify_schema_versions(report: Dict[str, Any], failures: List[str]) -> int:
    checked = 0
    report_schema_version = report.get("report_schema_version", None)
    checked += 1
    if report_schema_version != REPORT_SCHEMA_VERSION:
        failures.append(
            f"report_schema_version mismatch: expected {REPORT_SCHEMA_VERSION!r}, got {report_schema_version!r}"
        )

    evidence_schema_version = report.get("evidence_schema_version", None)
    checked += 1
    if evidence_schema_version != EVIDENCE_SCHEMA_VERSION:
        failures.append(
            f"evidence_schema_version mismatch: expected {EVIDENCE_SCHEMA_VERSION!r}, got {evidence_schema_version!r}"
        )
    return checked


def _verify_native_capability(report: Dict[str, Any], failures: List[str]) -> int:
    checked = 0
    native_capability = report.get("native_capability", None)
    checked += 1
    if not isinstance(native_capability, dict):
        failures.append("missing native_capability section")
        return checked

    for field in ("available", "module_name", "reason", "symbols"):
        checked += 1
        if field not in native_capability:
            failures.append(f"native_capability missing field: {field}")
    symbols = native_capability.get("symbols", None)
    if isinstance(symbols, dict):
        for symbol in REQUIRED_NATIVE_SYMBOLS:
            checked += 1
            if symbol not in symbols:
                failures.append(f"native_capability.symbols missing: {symbol}")
                continue
            if not isinstance(symbols.get(symbol), bool):
                failures.append(f"native_capability.symbols[{symbol!r}] must be bool")
    else:
        failures.append("native_capability.symbols must be a dict")
    return checked


def _verify_v3_required_fields(report: Dict[str, Any], failures: List[str]) -> int:
    checked = 0
    execution_backend = str(report.get("execution_backend", "")).strip().lower()
    checked += 1
    if execution_backend != "iwt_core":
        failures.append(
            f"execution_backend must be 'iwt_core', got {report.get('execution_backend')!r}"
        )

    native_capability = report.get("native_capability", None)
    checked += 1
    if isinstance(native_capability, dict):
        if not bool(native_capability.get("available", False)):
            failures.append("native_capability.available must be true")
        symbols = native_capability.get("symbols", None)
        checked += 1
        if not isinstance(symbols, dict) or not all(bool(v) for v in symbols.values()):
            failures.append("native_capability.symbols must all be true")

    digest = report.get("atomic_trace_digest", None)
    checked += 1
    if not isinstance(digest, str) or len(digest) != 64:
        failures.append("atomic_trace_digest must be a 64-char sha256 hex string")

    semantics = report.get("threat_model_semantics", None)
    checked += 1
    if not isinstance(semantics, dict):
        failures.append("missing threat_model_semantics section")
    else:
        models = semantics.get("threat_models", None)
        checked += 1
        if not isinstance(models, dict):
            failures.append("threat_model_semantics.threat_models must be a dict")
        else:
            for key in (
                "threat_model_1_black_box",
                "threat_model_2_instrumented",
                "threat_model_3_intervention",
            ):
                checked += 1
                if key not in models:
                    failures.append(f"threat_model_semantics.threat_models missing: {key}")

    composition = report.get("composition_structure_diagnosis", None)
    checked += 1
    if not isinstance(composition, dict):
        failures.append("missing composition_structure_diagnosis section")
    else:
        for key in (
            "high_dimensional_lattice_shape",
            "micro_function_connectivity",
            "judgement",
            "witnesses",
        ):
            checked += 1
            if key not in composition:
                failures.append(f"composition_structure_diagnosis missing field: {key}")

    return checked


def _check_typed_collection(
    *,
    report: Dict[str, Any],
    failures: List[str],
    key: str,
    required_fields: Iterable[str],
) -> int:
    checked = 0
    values = report.get(key, None)
    if values is None:
        return checked
    checked += 1
    if not isinstance(values, list):
        failures.append(f"{key} must be a list")
        return checked
    for i, item in enumerate(values):
        checked += 1
        if not isinstance(item, dict):
            failures.append(f"{key}[{i}] must be a dict")
            continue
        for field in required_fields:
            checked += 1
            if field not in item:
                failures.append(f"{key}[{i}] missing field: {field}")
        schema_value = item.get("schema_version", None)
        checked += 1
        if schema_value != EVIDENCE_SCHEMA_VERSION:
            failures.append(
                f"{key}[{i}].schema_version mismatch: expected {EVIDENCE_SCHEMA_VERSION!r}, got {schema_value!r}"
            )
    return checked


def verify_report_contracts(report: Dict[str, Any]) -> VerificationResult:
    failures: List[str] = []
    checked = 0
    checked += _verify_schema_versions(report, failures)
    checked += _verify_native_capability(report, failures)
    checked += _verify_v3_required_fields(report, failures)

    checked += _check_typed_collection(
        report=report,
        failures=failures,
        key="evidence_objects",
        required_fields=("identifier", "value_type", "witness_type", "value", "witness"),
    )
    checked += _check_typed_collection(
        report=report,
        failures=failures,
        key="witnesses",
        required_fields=("witness_type", "config", "E", "Z"),
    )
    checked += _check_typed_collection(
        report=report,
        failures=failures,
        key="threat_model_1_evidence_objects",
        required_fields=("identifier", "value_type", "witness_type", "value", "witness"),
    )
    checked += _check_typed_collection(
        report=report,
        failures=failures,
        key="threat_model_1_witnesses",
        required_fields=("witness_type", "config", "E", "Z"),
    )
    checked += _check_typed_collection(
        report=report,
        failures=failures,
        key="threat_model_2_witnesses",
        required_fields=("witness_type", "config", "E", "Z"),
    )

    return VerificationResult(
        ok=(len(failures) == 0),
        checked_count=int(checked),
        failed_count=int(len(failures)),
        failures=failures,
    )
