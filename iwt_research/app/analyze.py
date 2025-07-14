from __future__ import annotations

import copy
import json
import os
from typing import Any

from ..algorithm_api.loader import load_analyze_adapter
from ..algorithm_api.protocols import AnalyzeRequest
from ..analysis.threat_model import parse_threat_model_level
from ..verify import (
    STREAM_HASH_EXPERIMENT_TYPES,
    verify_evidence_aggregation_consistency,
    verify_exhaustive_bijection_proof_artifacts,
    verify_performance_budget_contract,
    verify_report_contracts,
    verify_stream_and_hash_report,
    verify_tm1_multi_projection_scan,
    verify_tm2_focused_probes,
    verify_tm3_workflow,
    verify_todo_alignment_mapping,
)


def run_analyze_command(args: Any) -> int:
    out_dir = str(args.out)
    os.makedirs(out_dir, exist_ok=True)
    parse_threat_model_level(str(args.threat_model))

    adapter = load_analyze_adapter(str(args.impl))
    if str(getattr(adapter, "execution_backend", "")).strip().lower() != "iwt_core":
        print("IWT_CORE_REQUIRED: adapter.execution_backend must be 'iwt_core'")
        return 2

    request = AnalyzeRequest(
        impl=str(args.impl),
        crypto_type=str(args.crypto_type),
        input_bits=int(args.input_bits),
        output_bits=int(args.output_bits),
        threat_model=str(args.threat_model),
        out_dir=str(out_dir),
        seed=int(getattr(args, "seed", 0)),
    )
    report = adapter.analyze(request)
    if not isinstance(report, dict):
        print("IWT_CORE_REQUIRED: adapter analyze() must return a report dict")
        return 2
    if str(report.get("execution_backend", "")).strip().lower() != "iwt_core":
        print("IWT_CORE_REQUIRED: report.execution_backend must be 'iwt_core'")
        return 2
    native_capability = report.get("native_capability", {})
    if not isinstance(native_capability, dict) or not bool(native_capability.get("available", False)):
        print("IWT_CORE_REQUIRED: report.native_capability.available must be true")
        return 2
    symbols = native_capability.get("symbols", {})
    if not isinstance(symbols, dict) or not all(bool(v) for v in symbols.values()):
        print("IWT_CORE_REQUIRED: report.native_capability.symbols must all be true")
        return 2

    report_path = os.path.join(out_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(copy.deepcopy(report), f, ensure_ascii=False, indent=2, default=str)
    print(f"Wrote: {report_path}")

    # Always verify; analyze is considered successful only if report contracts pass.
    if report.get("experiment_type") in STREAM_HASH_EXPERIMENT_TYPES:
        r = verify_stream_and_hash_report(report)
        r_contract = verify_report_contracts(report)
        r_alignment = verify_todo_alignment_mapping(report)
        r_budget = verify_performance_budget_contract(report)
        ok = bool(r.ok and r_contract.ok and r_alignment.ok and r_budget.ok)
        result = {
            "success": ok,
            "stream_or_hash_verification": r.as_dict(),
            "report_contracts": r_contract.as_dict(),
            "todo_alignment_mapping": r_alignment.as_dict(),
            "performance_budget_contract": r_budget.as_dict(),
        }
    else:
        r1 = verify_exhaustive_bijection_proof_artifacts(report)
        r2 = verify_tm1_multi_projection_scan(report)
        r3 = verify_tm3_workflow(report)
        r4 = verify_tm2_focused_probes(report)
        r5 = verify_evidence_aggregation_consistency(report)
        r_contract = verify_report_contracts(report)
        r6 = verify_todo_alignment_mapping(report)
        r7 = verify_performance_budget_contract(report)
        ok = bool(
            r1.ok and r2.ok and r3.ok and r4.ok and r5.ok and r_contract.ok and r6.ok and r7.ok
        )
        result = {
            "success": ok,
            "exhaustive_bijection_proof_artifacts": r1.as_dict(),
            "threat_model_1_multi_projection_scan": r2.as_dict(),
            "threat_model_3_workflow": r3.as_dict(),
            "threat_model_2_focused_probes": r4.as_dict(),
            "evidence_aggregation_consistency": r5.as_dict(),
            "report_contracts": r_contract.as_dict(),
            "todo_alignment_mapping": r6.as_dict(),
            "performance_budget_contract": r7.as_dict(),
        }

    summary_path = os.path.join(out_dir, "analyze_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Wrote: {summary_path}")
    return 0 if bool(result.get("success", False)) else 1
