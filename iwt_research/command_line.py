from __future__ import annotations

import argparse
import json
import os
import random
import sys

from .app.analyze import run_analyze_command
from .verify import (
    STREAM_HASH_EXPERIMENT_TYPES,
    load_report_json,
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


def _default_report_out_dir() -> str:
    cwd = os.getcwd()
    candidate = os.path.join(cwd, "iwt_research", "report_out")
    if os.path.isdir(os.path.join(cwd, "iwt_research")) and os.path.exists(
        os.path.join(cwd, "iwt_research", "command_line.py")
    ):
        return os.path.abspath(candidate)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_out")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iwt_research",
        description=(
            "IWT structural analyzer. External algorithms must execute through iwt_core atomic operators."
        ),
    )
    parser.add_argument(
        "--global-seed",
        type=int,
        default=None,
        help="Global RNG seed; default 0 if unset (ensures reproducible runs)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    analyze = sub.add_parser("analyze", help="run IWT structural analysis via iwt_core backend")
    analyze.add_argument(
        "--impl",
        required=True,
        help="adapter spec module:factory (factory defaults to create_adapter)",
    )
    analyze.add_argument(
        "--type",
        dest="crypto_type",
        required=True,
        choices=["block", "stream", "hash"],
        help="symmetric primitive class",
    )
    analyze.add_argument("--input-bits", required=True, type=int, help="input bit width")
    analyze.add_argument("--output-bits", required=True, type=int, help="output bit width")
    analyze.add_argument(
        "--threat-model",
        default="threat_model_2_instrumented",
        help="threat_model_1_black_box | threat_model_2_instrumented | threat_model_3_intervention",
    )
    analyze.add_argument("--seed", type=int, default=0)
    analyze.add_argument("--out", default=_default_report_out_dir(), help="output directory")

    verify = sub.add_parser("verify", help="verify report contracts and reproducibility obligations")
    verify.add_argument("--report", required=True, help="path to report.json to verify")

    return parser


def _run_verify(report_path: str) -> int:
    report = load_report_json(str(report_path))
    if report.get("experiment_type") in STREAM_HASH_EXPERIMENT_TYPES:
        r = verify_stream_and_hash_report(report)
        r_contract = verify_report_contracts(report)
        r_alignment = verify_todo_alignment_mapping(report)
        r_budget = verify_performance_budget_contract(report)
        ok = bool(r.ok) and bool(r_contract.ok) and bool(r_alignment.ok) and bool(r_budget.ok)
        out = {
            "success": ok,
            "stream_or_hash_verification": r.as_dict(),
            "report_contracts": r_contract.as_dict(),
            "todo_alignment_mapping": r_alignment.as_dict(),
            "performance_budget_contract": r_budget.as_dict(),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    r1 = verify_exhaustive_bijection_proof_artifacts(report)
    r2 = verify_tm1_multi_projection_scan(report)
    r3 = verify_tm3_workflow(report)
    r4 = verify_tm2_focused_probes(report)
    r5 = verify_evidence_aggregation_consistency(report)
    r_contract = verify_report_contracts(report)
    r6 = verify_todo_alignment_mapping(report)
    r7 = verify_performance_budget_contract(report)
    ok = bool(r1.ok and r2.ok and r3.ok and r4.ok and r5.ok and r_contract.ok and r6.ok and r7.ok)
    out = {
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
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    legacy_commands = {"run", "tm3", "calibrate", "stream", "hash", "suite"}
    maybe_cmd = ""
    i = 0
    while i < len(raw_argv):
        token = str(raw_argv[i]).strip()
        if token == "--global-seed":
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        maybe_cmd = token.lower()
        break
    if maybe_cmd in legacy_commands:
        print(
            "LEGACY_COMMAND_REMOVED: "
            f"'{maybe_cmd}' is removed. Use 'analyze --impl module:factory ...' or 'verify --report <report.json>'."
        )
        return 2

    args = build_parser().parse_args(raw_argv)
    global_seed = getattr(args, "global_seed", None)
    if global_seed is None:
        global_seed = int(os.environ.get("IWT_GLOBAL_SEED", "0"))
    random.seed(int(global_seed))

    if args.cmd == "analyze":
        return run_analyze_command(args)
    if args.cmd == "verify":
        return _run_verify(str(args.report))
    return 2
